import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Mic, Video, Share2, Settings, Clock, Volume2 } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  ApiError,
  AudioEvaluation,
  BehaviorAnalysis,
  BehaviorSummary,
  CostRecord,
  CostSummary,
  InterviewQuestion,
  activeInterviewStore,
  api,
  interviewHistoryStore,
  tokenStore,
} from '../services/api';
import styles from './InterviewPage.module.css';

type SessionMessage = {
  type: 'pong' | 'vision' | 'summary' | 'audio' | 'error';
  data?: BehaviorAnalysis | BehaviorSummary | {
    success: boolean;
    audio_base64?: string;
    mime_type?: string;
    request_id?: string;
    text?: string;
    cost?: CostRecord | null;
    session_cost?: CostSummary;
    error?: string;
  };
  cost?: CostRecord | null;
  session_cost?: CostSummary;
  message?: string;
};

type BrowserAudioContext = AudioContext & {
  webkitAudioContext?: never;
};

type BrowserWindowWithAudio = Window & typeof globalThis & {
  webkitAudioContext?: typeof AudioContext;
};

const fallbackQuestion: InterviewQuestion = {
  text: 'Start an interview from the dashboard to receive your first backend-generated question.',
  topic: 'Interview setup',
  category: 'General',
  difficulty: 'medium',
  why_asked: 'No active session was found in this browser.',
  order_idx: 0,
};

const InterviewPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const socketRef = useRef<WebSocket | null>(null);
  const localVideoRef = useRef<HTMLVideoElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingStartedAtRef = useRef<number | null>(null);
  const interviewerAudioRef = useRef<HTMLAudioElement | null>(null);
  const interviewerAudioUrlRef = useRef<string | null>(null);
  const audioContextRef = useRef<BrowserAudioContext | null>(null);
  const audioSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const speechTimeoutRef = useRef<number | null>(null);
  const autoSpeechTimerRef = useRef<number | null>(null);
  const spokenQuestionKeyRef = useRef('');
  const pendingSpeechTextRef = useRef('');
  const pendingSpeechRequestRef = useRef('');
  const interviewId = searchParams.get('interviewId') || activeInterviewStore().get()?.interview_id || '';
  const activeInterview = activeInterviewStore().get();

  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOn, setIsVideoOn] = useState(true);
  const [isRecording, setIsRecording] = useState(false);
  const [mediaError, setMediaError] = useState('');
  const [timeLeft, setTimeLeft] = useState(1440);
  const [connected, setConnected] = useState(false);
  const [sessionStatus, setSessionStatus] = useState('Preparing session');
  const [currentQuestion, setCurrentQuestion] = useState<InterviewQuestion>(
    activeInterview?.first_question || fallbackQuestion,
  );
  const [questionNumber, setQuestionNumber] = useState((currentQuestion.order_idx || 0) + 1);
  const [latestScore, setLatestScore] = useState<number | null>(null);
  const [latestReasoning, setLatestReasoning] = useState('');
  const [latestTranscript, setLatestTranscript] = useState('');
  const [latestEvaluation, setLatestEvaluation] = useState<AudioEvaluation | null>(null);
  const [latestBehavior, setLatestBehavior] = useState<BehaviorAnalysis | null>(null);
  const [behaviorSummary, setBehaviorSummary] = useState<BehaviorSummary | null>(null);
  const [sessionCost, setSessionCost] = useState<CostSummary | null>(null);
  const [isSubmittingAnswer, setIsSubmittingAnswer] = useState(false);

  useEffect(() => {
    if (!tokenStore.get()) {
      navigate('/login');
      return;
    }

    if (!interviewId) {
      setSessionStatus('No active interview. Start one from the dashboard.');
      return;
    }

    const checkInterviewApi = async () => {
      try {
        await api.interview.health();
        const status = await api.interview.status(interviewId);
        const persistedQuestion = status.questions[status.questions.length - 1];
        if (persistedQuestion) {
          setCurrentQuestion(persistedQuestion);
          setQuestionNumber(
            typeof persistedQuestion.order_idx === 'number'
              ? persistedQuestion.order_idx + 1
              : status.questions.length,
          );
        }
        interviewHistoryStore().upsert(status.interview);
        setSessionStatus('Session ready');
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          tokenStore.clear();
          navigate('/login');
          return;
        }
        setSessionStatus(err instanceof ApiError ? err.message : 'Unable to reach interview API.');
      }
    };

    checkInterviewApi();
  }, [interviewId, navigate]);

  useEffect(() => {
    if (!interviewId) {
      return undefined;
    }

    const socket = new WebSocket(api.interview.socketUrl(interviewId));
    socketRef.current = socket;

    socket.onopen = () => {
      setConnected(true);
      setSessionStatus('Live session connected');
      socket.send(JSON.stringify({ type: 'ping' }));
    };

    socket.onclose = () => {
      setConnected(false);
      setSessionStatus((current) => current === 'Interview completed' ? current : 'Live session disconnected');
    };

    socket.onerror = () => {
      setConnected(false);
      setSessionStatus('WebSocket connection failed');
    };

    socket.onmessage = (event) => {
      const message = JSON.parse(event.data) as SessionMessage;

      if (message.type === 'pong') {
        setSessionStatus('Live session connected');
      }

      if (message.type === 'error') {
        setSessionStatus(message.message || 'Session error');
      }

      if (message.type === 'vision' && message.data) {
        setLatestBehavior(message.data as BehaviorAnalysis);
        if (message.session_cost) {
          setSessionCost(message.session_cost);
        }
        setSessionStatus('Vision analysis received');
      }

      if (message.type === 'summary' && message.data) {
        setBehaviorSummary(message.data as BehaviorSummary);
        if (message.session_cost) {
          setSessionCost(message.session_cost);
        }
        setSessionStatus('Behavior summary received');
      }

      if (message.type === 'audio' && message.data) {
        const audioData = message.data as {
          success: boolean;
          audio_base64?: string;
          mime_type?: string;
          request_id?: string;
          text?: string;
          cost?: CostRecord | null;
          session_cost?: CostSummary;
          error?: string;
        };

        if (speechTimeoutRef.current) {
          window.clearTimeout(speechTimeoutRef.current);
          speechTimeoutRef.current = null;
        }

        if (audioData.request_id && audioData.request_id !== pendingSpeechRequestRef.current) {
          return;
        }

        if (!audioData.success || !audioData.audio_base64) {
          const fallbackText = audioData.text || pendingSpeechTextRef.current || currentQuestion.text || '';
          setSessionStatus(audioData.error || 'ElevenLabs voice generation failed. Using browser voice.');
          if (fallbackText) {
            speakWithBrowser(fallbackText);
          }
          return;
        }

        playInterviewerAudio(
          audioData.audio_base64,
          audioData.mime_type || 'audio/mpeg',
          audioData.text || pendingSpeechTextRef.current || currentQuestion.text || '',
        );
        if (audioData.session_cost) {
          setSessionCost(audioData.session_cost);
        }
      }
    };

    return () => {
      socket.close();
    };
  }, [interviewId]);

  useEffect(() => {
    if (!tokenStore.get()) {
      return undefined;
    }

    let cancelled = false;

    const openMedia = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
          video: true,
        });

        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        mediaStreamRef.current = stream;
        if (localVideoRef.current) {
          localVideoRef.current.srcObject = stream;
        }
        setMediaError('');
      } catch (err) {
        setMediaError('Allow camera and microphone permissions to answer in realtime.');
      }
    };

    openMedia();

    return () => {
      cancelled = true;
      recorderRef.current?.stop();
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => {
    if (!interviewId || !isVideoOn) {
      return undefined;
    }

    let cancelled = false;

    const captureFrame = () => {
      const video = localVideoRef.current;
      if (!video || video.videoWidth === 0 || video.videoHeight === 0 || cancelled) {
        return;
      }

      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const context = canvas.getContext('2d');
      if (!context) {
        return;
      }

      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(async (blob) => {
        if (!blob || cancelled) {
          return;
        }

        try {
          const result = await api.interview.analyzeFrame(interviewId, blob);
          if (result.success && result.analysis) {
            setLatestBehavior(result.analysis);
            if (result.session_cost) {
              setSessionCost(result.session_cost);
            }
            setSessionStatus('Camera behavior analyzed');
          } else if (result.error) {
            setSessionStatus(result.error);
          }
        } catch (err) {
          setSessionStatus(err instanceof ApiError ? err.message : 'Camera analysis failed.');
        }
      }, 'image/jpeg', 0.78);
    };

    const firstRun = window.setTimeout(captureFrame, 2500);
    const interval = window.setInterval(captureFrame, 15000);

    return () => {
      cancelled = true;
      window.clearTimeout(firstRun);
      window.clearInterval(interval);
    };
  }, [interviewId, isVideoOn]);

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft((prev) => (prev > 0 ? prev - 1 : prev));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;

  const feedbackScores = useMemo(() => {
    if (latestEvaluation) {
      return [
        { label: 'Clarity', score: latestEvaluation.clarity_score || 0 },
        { label: 'Confidence', score: latestEvaluation.confidence_score || 0 },
        { label: 'Depth', score: latestEvaluation.depth_score || 0 },
        { label: 'Accuracy', score: latestEvaluation.accuracy_score || 0 },
      ];
    }

    const baseScore = latestScore ?? 0;
    return [
      { label: 'Clarity', score: Math.min(100, Math.max(0, baseScore || 0)) },
      { label: 'Confidence', score: latestBehavior?.confidence_score ?? (connected ? 85 : 20) },
      { label: 'Depth', score: baseScore ? Math.max(0, baseScore - 6) : 0 },
      { label: 'Engagement', score: latestBehavior?.engagement_score ?? (connected ? 80 : 0) },
    ];
  }, [connected, latestBehavior, latestEvaluation, latestScore]);

  const costRows = useMemo(() => (
    Object.entries(sessionCost?.by_call_type || {})
      .map(([name, amount]) => ({ name, amount }))
  ), [sessionCost]);
  const interviewerContext = currentQuestion.why_asked || activeInterview?.opening_line || sessionStatus;

  const stopQuestionAudio = (clearPendingSpeech = false) => {
    if (clearPendingSpeech && speechTimeoutRef.current) {
      window.clearTimeout(speechTimeoutRef.current);
      speechTimeoutRef.current = null;
    }

    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }

    try {
      audioSourceRef.current?.stop();
    } catch {
      // The source may already have ended.
    }
    audioSourceRef.current = null;

    interviewerAudioRef.current?.pause();
    interviewerAudioRef.current = null;
    if (interviewerAudioUrlRef.current) {
      URL.revokeObjectURL(interviewerAudioUrlRef.current);
      interviewerAudioUrlRef.current = null;
    }
  };

  const speakWithBrowser = (text: string) => {
    if (!('speechSynthesis' in window)) {
      setSessionStatus('Speech playback is not supported in this browser');
      return;
    }

    const cleanText = text.trim();
    if (!cleanText) {
      setSessionStatus('No question available to speak yet');
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 0.95;
    utterance.pitch = 1;
    utterance.volume = 1;
    utterance.onstart = () => setSessionStatus('Playing interviewer audio...');
    utterance.onend = () => setSessionStatus('Question audio played. Record when you are ready.');
    utterance.onerror = () => setSessionStatus('Unable to play interviewer audio');
    window.speechSynthesis.speak(utterance);
  };

  const unlockAudioOutput = async () => {
    const AudioContextCtor = window.AudioContext || (window as BrowserWindowWithAudio).webkitAudioContext;
    if (!AudioContextCtor) {
      return null;
    }

    const context = audioContextRef.current || new AudioContextCtor();
    audioContextRef.current = context as BrowserAudioContext;

    if (context.state === 'suspended') {
      await context.resume();
    }

    const source = context.createBufferSource();
    source.buffer = context.createBuffer(1, 1, 22050);
    source.connect(context.destination);
    source.start(0);

    return context;
  };

  const playInterviewerAudio = async (audioBase64: string, mimeType: string, fallbackText: string) => {
    try {
      stopQuestionAudio();

      const audioBlob = await fetch(`data:${mimeType};base64,${audioBase64}`)
        .then((response) => response.blob());
      const arrayBuffer = await audioBlob.arrayBuffer();
      const context = audioContextRef.current;

      if (context && context.state === 'running') {
        audioSourceRef.current?.stop();
        const audioBuffer = await context.decodeAudioData(arrayBuffer.slice(0));
        const source = context.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(context.destination);
        source.onended = () => setSessionStatus('Question audio played. Record when you are ready.');
        audioSourceRef.current = source;
        setSessionStatus('Playing ElevenLabs interviewer voice...');
        source.start(0);
        return;
      }

      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      interviewerAudioRef.current = audio;
      interviewerAudioUrlRef.current = audioUrl;
      audio.onplaying = () => setSessionStatus('Playing ElevenLabs interviewer voice...');
      audio.onended = () => setSessionStatus('Question audio played. Record when you are ready.');
      audio.onerror = () => {
        setSessionStatus('ElevenLabs audio could not play. Using browser voice.');
        if (fallbackText) {
          speakWithBrowser(fallbackText);
        }
      };
      await audio.play();
    } catch {
      setSessionStatus('Audio playback was blocked. Using browser voice.');
      if (fallbackText) {
        speakWithBrowser(fallbackText);
      }
    }
  };

  const speakText = async (text: string) => {
    const cleanText = text.trim();
    if (!cleanText) {
      setSessionStatus('No question available to speak yet');
      return;
    }

    stopQuestionAudio(true);
    pendingSpeechTextRef.current = cleanText;

    try {
      await unlockAudioOutput();
    } catch {
      // Browser voice fallback still works even if Web Audio cannot be unlocked.
    }

    if (socketRef.current?.readyState !== WebSocket.OPEN) {
      setSessionStatus('Live voice channel is not connected. Using browser voice.');
      speakWithBrowser(cleanText);
      return;
    }

    if (speechTimeoutRef.current) {
      window.clearTimeout(speechTimeoutRef.current);
    }

    const requestId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    pendingSpeechRequestRef.current = requestId;

    speechTimeoutRef.current = window.setTimeout(() => {
      setSessionStatus('No ElevenLabs voice response from backend. Using browser voice.');
      speakWithBrowser(cleanText);
    }, 12000);

    setSessionStatus('Generating ElevenLabs interviewer voice...');
    socketRef.current.send(JSON.stringify({
      type: 'speak',
      text: cleanText,
      request_id: requestId,
    }));
  };

  useEffect(() => {
    const cleanText = currentQuestion.text?.trim();
    if (!interviewId || !connected || !cleanText || cleanText === fallbackQuestion.text) {
      return undefined;
    }

    const speechKey = `${currentQuestion.order_idx ?? 'queued'}:${cleanText}`;
    if (spokenQuestionKeyRef.current === speechKey) {
      return undefined;
    }

    spokenQuestionKeyRef.current = speechKey;
    autoSpeechTimerRef.current = window.setTimeout(() => {
      autoSpeechTimerRef.current = null;
      speakText(cleanText);
    }, 350);

    return () => {
      if (autoSpeechTimerRef.current) {
        window.clearTimeout(autoSpeechTimerRef.current);
        autoSpeechTimerRef.current = null;
      }
    };
  }, [connected, currentQuestion.order_idx, currentQuestion.text, interviewId]);

  const handleReplayQuestion = () => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: 'ping' }));
    }

    if (autoSpeechTimerRef.current) {
      window.clearTimeout(autoSpeechTimerRef.current);
      autoSpeechTimerRef.current = null;
    }

    speakText(currentQuestion.text || 'No question is available to replay yet.');
  };

  const sendAudioBlob = async (blob: Blob, durationSec?: number) => {
    const question = currentQuestion.text?.trim();
    if (!interviewId || !question) {
      setSessionStatus('No active question is available for evaluation');
      return;
    }

    try {
      setIsSubmittingAnswer(true);
      setSessionStatus('Answer sent. Waiting for evaluation...');
      const result = await api.interview.analyzeAudio(interviewId, question, blob, durationSec);

      if (!result.success || !result.evaluation) {
        setSessionStatus(result.error || 'Audio evaluation failed');
        return;
      }

      const evaluation = result.evaluation;
      setLatestEvaluation(evaluation);
      setLatestScore(evaluation.score);
      setLatestReasoning(evaluation.reasoning);
      setLatestTranscript(evaluation.transcript);
      if (result.session_cost) {
        setSessionCost(result.session_cost);
      }
      interviewHistoryStore().update(interviewId, { overall_score: evaluation.score });

      if (result.next_question) {
        const nextQuestion = result.next_question;
        setCurrentQuestion(nextQuestion);
        setQuestionNumber((current) => (
          typeof nextQuestion.order_idx === 'number'
            ? nextQuestion.order_idx + 1
            : current + 1
        ));
        activeInterviewStore().update({
          first_question: nextQuestion,
        });
        setSessionStatus('Answer evaluated. Next question will play automatically.');
      } else {
        setSessionStatus('Answer evaluated. No more questions are queued.');
      }
    } catch (err) {
      setSessionStatus(err instanceof ApiError ? err.message : 'Audio evaluation failed.');
    } finally {
      setIsSubmittingAnswer(false);
    }
  };

  const handleRecordToggle = () => {
    if (isSubmittingAnswer) {
      setSessionStatus('Please wait while your answer is submitted.');
      return;
    }

    const stream = mediaStreamRef.current;
    if (!stream) {
      setSessionStatus(mediaError || 'Camera and microphone are not ready');
      return;
    }

    if (isRecording) {
      recorderRef.current?.stop();
      setIsRecording(false);
      return;
    }

    stopQuestionAudio(true);
    audioChunksRef.current = [];
    const audioStream = new MediaStream(stream.getAudioTracks());
    const recorder = new MediaRecorder(audioStream);
    recorderRef.current = recorder;

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunksRef.current.push(event.data);
      }
    };

    recorder.onstop = () => {
      const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/webm' });
      const durationSec = recordingStartedAtRef.current
        ? (Date.now() - recordingStartedAtRef.current) / 1000
        : undefined;
      recordingStartedAtRef.current = null;
      sendAudioBlob(blob, durationSec);
    };

    recorder.start();
    recordingStartedAtRef.current = Date.now();
    setIsMuted(false);
    setIsRecording(true);
    setSessionStatus('Recording answer...');
  };

  const handleVideoToggle = () => {
    const next = !isVideoOn;
    mediaStreamRef.current?.getVideoTracks().forEach((track) => {
      track.enabled = next;
    });
    setIsVideoOn(next);
  };

  const handleShare = async () => {
    await navigator.clipboard.writeText(window.location.href);
    setSessionStatus('Interview link copied');
  };

  const handleEndInterview = async () => {
    try {
      let finalBehaviorSummary = behaviorSummary;
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(JSON.stringify({ type: 'summary' }));
      }

      if (interviewId) {
        const summary = await api.interview.behaviorSummary(interviewId);
        if (summary.success && summary.summary) {
          finalBehaviorSummary = summary.summary;
          setBehaviorSummary(summary.summary);
        }
        const completed = await api.interview.complete(interviewId, latestScore, finalBehaviorSummary);
        setSessionCost(completed.session_cost);
        interviewHistoryStore().update(interviewId, {
          status: 'completed',
          overall_score: latestScore,
          completed_at: new Date().toISOString(),
        });
      }
    } catch {
      if (interviewId) {
        interviewHistoryStore().update(interviewId, {
          status: 'completed',
          overall_score: latestScore,
          completed_at: new Date().toISOString(),
        });
      }
    }
    socketRef.current?.close();
    stopQuestionAudio(true);
    audioContextRef.current?.close();
    activeInterviewStore().clear();
    navigate('/home');
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1, delayChildren: 0.2 },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 10 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
  };

  return (
    <div className={styles.interviewPage}>
      <motion.header
        className={styles.interviewHeader}
        initial={{ y: -50 }}
        animate={{ y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className={styles.headerLeft}>
          <h2>{activeInterview?.persona_name || 'Intervue.ai Interview'}</h2>
          <p>{sessionStatus}</p>
        </div>

        <div className={styles.timer}>
          <Clock size={20} />
          <span>
            {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
          </span>
        </div>

        <motion.button className={styles.endBtn} whileHover={{ scale: 1.05 }} onClick={handleEndInterview}>
          End Interview
        </motion.button>
      </motion.header>

      <div className={styles.interviewContent}>
        <motion.div
          className={styles.leftPanel}
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6 }}
        >
          <motion.div className={styles.videoGrid}>
            <motion.div
              className={styles.videoBox}
              whileHover={{ scale: 1.02 }}
              transition={{ duration: 0.3 }}
            >
              <div className={styles.videoPlaceholder}>
                <div className={styles.videoContent}>
                  <div className={styles.avatar}>👨‍💼</div>
                  <p>{activeInterview?.persona_name || 'Interviewer'}</p>
                </div>
                <div className={styles.talking}>
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
              <motion.div
                className={styles.statusBadge}
                animate={{ opacity: [1, 0.5, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                {connected ? 'Connected' : 'Offline'}
              </motion.div>
            </motion.div>

            <motion.div
              className={styles.videoBox}
              whileHover={{ scale: 1.02 }}
              transition={{ duration: 0.3 }}
            >
              <div className={styles.videoPlaceholder}>
                <div className={styles.videoContent}>
                  {isVideoOn ? (
                    <video ref={localVideoRef} className={styles.localVideo} autoPlay playsInline muted />
                  ) : (
                    <div className={styles.avatar}>👤</div>
                  )}
                  <p>You</p>
                </div>
              </div>
              <motion.div
                className={styles.statusBadge}
                animate={{ opacity: [0.5, 1, 0.5] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                {isRecording ? 'Recording' : isMuted ? 'Muted' : 'Ready'}
              </motion.div>
            </motion.div>
          </motion.div>
          {mediaError && <div className={styles.mediaNotice}>{mediaError}</div>}

          <motion.div
            className={styles.questionPanel}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            <div className={styles.questionHeader}>
              <span className={styles.questionNumber}>Question {questionNumber}</span>
              <span className={styles.difficulty}>{currentQuestion.difficulty || 'Adaptive'}</span>
            </div>

            <h3>{currentQuestion.text}</h3>

            <div className={styles.questionTags}>
              <span>{currentQuestion.category || 'Interview'}</span>
              <span>{currentQuestion.topic || 'General'}</span>
            </div>

            <div className={styles.aiStatus}>
              <div className={styles.thinking}>
                <span></span>
                <span></span>
                <span></span>
              </div>
              <p>{interviewerContext}</p>
            </div>

            <motion.div
              className={styles.suggestedAnswer}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.5 }}
            >
              <p className={styles.checkItem}>Backend session id: {interviewId || 'none'}</p>
              <p className={styles.checkItem}>{connected ? 'WebSocket connected' : 'Waiting for WebSocket'}</p>
              <p className={styles.checkItem}>{latestReasoning || 'Answer scoring appears here after audio is sent.'}</p>
            </motion.div>
          </motion.div>

          <motion.div
            className={styles.controls}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            <motion.button
              className={`${styles.controlBtn} ${isRecording ? styles.active : ''}`}
              onClick={handleRecordToggle}
              disabled={isSubmittingAnswer}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              title={isSubmittingAnswer ? 'Submitting answer' : isRecording ? 'Stop and send answer' : 'Record answer'}
            >
              <Mic size={20} />
            </motion.button>

            <motion.button
              className={`${styles.controlBtn} ${isVideoOn ? '' : styles.active}`}
              onClick={handleVideoToggle}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              title="Toggle camera"
            >
              <Video size={20} />
            </motion.button>

            <motion.button
              className={styles.controlBtn}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              onClick={handleShare}
              title="Copy interview link"
            >
              <Share2 size={20} />
            </motion.button>

            <motion.button
              className={styles.controlBtn}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => navigate('/home')}
              title="Back to dashboard"
            >
              <Settings size={20} />
            </motion.button>
            <button
              type="button"
              className={styles.answerAction}
              onClick={handleRecordToggle}
              disabled={isSubmittingAnswer}
            >
              {isSubmittingAnswer ? 'Submitting...' : isRecording ? 'Stop & Send' : 'Record Answer'}
            </button>
          </motion.div>
        </motion.div>

        <motion.div
          className={styles.rightPanel}
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6 }}
        >
          <motion.div
            className={styles.feedbackSection}
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            <motion.h3 variants={itemVariants}>Live Feedback</motion.h3>

            <motion.div className={styles.feedbackScores} variants={containerVariants}>
              {feedbackScores.map((item, index) => (
                <motion.div
                  key={item.label}
                  className={styles.feedbackItem}
                  variants={itemVariants}
                >
                  <div className={styles.feedbackLabel}>
                    <span>{item.label}</span>
                  </div>
                  <div className={styles.feedbackBar}>
                    <motion.div
                      className={styles.feedbackFill}
                      initial={{ width: 0 }}
                      animate={{ width: `${item.score}%` }}
                      transition={{ duration: 1, delay: index * 0.1 }}
                      style={{
                        background: `linear-gradient(90deg, #6366f1, ${
                          item.score > 80
                            ? '#10b981'
                            : item.score > 60
                            ? '#f59e0b'
                            : '#ef4444'
                        })`,
                      }}
                    />
                  </div>
                  <span className={styles.feedbackScore}>{item.score}</span>
                </motion.div>
              ))}
            </motion.div>
          </motion.div>

          <motion.div
            className={styles.costSection}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.25 }}
          >
            <h3>API Cost</h3>
            <div className={styles.costTotal}>
              ₹{(sessionCost?.total_cost_inr || 0).toFixed(4)}
            </div>
            <div className={styles.costMeta}>
              <span>{sessionCost?.calls || 0} calls</span>
              <span>{sessionCost?.total_tokens || 0} tokens</span>
            </div>
            <div className={styles.costBreakdown}>
              {costRows.length === 0 && <p>No paid API calls recorded yet.</p>}
              {costRows.map((item) => (
                <div key={item.name}>
                  <span>{item.name.replace(/_/g, ' ')}</span>
                  <strong>₹{item.amount.toFixed(4)}</strong>
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div
            className={styles.waveformSection}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            <h3>Your Answer</h3>
            <div className={styles.waveform}>
              {[...Array(40)].map((_, i) => (
                <motion.div
                  key={i}
                  className={styles.waveBar}
                  animate={{
                    height: isRecording ? `${20 + ((i * 17) % 80)}%` : '10%',
                  }}
                  transition={{
                    duration: 0.3,
                    repeat: Infinity,
                    repeatType: 'reverse',
                  }}
                />
              ))}
            </div>
            <div className={styles.waveformInfo}>
              <span>
                {isRecording
                  ? 'Recording answer'
                  : isSubmittingAnswer
                    ? 'Submitting answer'
                    : connected
                      ? 'Ready to record'
                      : 'Waiting for channel'}
              </span>
              {isRecording && (
                <motion.span
                  animate={{ opacity: [1, 0.5, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                >
                  🔴
                </motion.span>
              )}
            </div>
            {latestTranscript && (
              <p className={styles.transcriptText}>{latestTranscript}</p>
            )}
          </motion.div>

          <motion.div
            className={styles.behaviorSection}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.35 }}
          >
            <h3>Camera Behavior</h3>
            <div className={styles.behaviorGrid}>
              <span>Engagement: {latestBehavior?.engagement_score ?? behaviorSummary?.overall_engagement ?? 0}</span>
              <span>Eye contact: {behaviorSummary?.eye_contact_ratio ?? (latestBehavior?.eye_contact ? 100 : 0)}%</span>
              <span>Emotion: {behaviorSummary?.dominant_emotion || latestBehavior?.emotion || 'neutral'}</span>
            </div>
            <p>{behaviorSummary?.behavior_summary || latestBehavior?.notes || 'Camera snapshots are analyzed while the interview is open.'}</p>
          </motion.div>

          <motion.div
            className={styles.notesSection}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            <h3>Notes</h3>
            <textarea
              placeholder="Add notes for later review..."
              defaultValue={latestReasoning}
              className={styles.notesInput}
            />
          </motion.div>

          <motion.div
            className={styles.settingsSection}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
          >
            <motion.button
              className={styles.settingsBtn}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => navigate('/home')}
            >
              <Settings size={16} />
              Dashboard
            </motion.button>
            <motion.button
              className={styles.notesBtn}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={handleReplayQuestion}
            >
              <Volume2 size={16} />
              Replay Question
            </motion.button>
          </motion.div>
        </motion.div>
      </div>
    </div>
  );
};

export default InterviewPage;
