import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Circle, Clock, Mic, PhoneOff, Settings, Video, Volume2 } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { RadarScoreChart } from '../components/charts/SimpleCharts';
import { ImmersiveStage } from '../components/immersive/ImmersiveStage';
import { motion } from '../components/ui/staticMotion';
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
  createLocalQuestion,
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
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [showInterviewSettings, setShowInterviewSettings] = useState(false);

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
        const latestQuestion = status.questions[status.questions.length - 1];

        if (latestQuestion) {
          setCurrentQuestion(latestQuestion);
          setQuestionNumber((latestQuestion.order_idx || 0) + 1);
          activeInterviewStore().set({
            success: true,
            interview_id: status.interview.id,
            first_question: latestQuestion,
            persona_name: activeInterview?.persona_name || 'Intervue.ai Interview',
            opening_line: activeInterview?.opening_line || '',
            job_role: status.interview.job_role || activeInterview?.job_role || 'General',
            job_description: status.interview.job_description || activeInterview?.job_description || '',
            interview_mode: status.interview.interview_mode || activeInterview?.interview_mode || 'faang',
            resume_id: status.interview.resume_id,
            created_at: status.interview.created_at || new Date().toISOString(),
          });
        }

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

  const analyticsMetrics = useMemo(() => {
    const normalize = (value?: number | null, fallback = 0) => (
      Math.min(100, Math.max(0, Math.round(value ?? fallback)))
    );
    const baseScore = latestScore ?? 0;

    return [
      {
        label: 'Clarity',
        score: normalize(latestEvaluation?.clarity_score, baseScore),
        hint: 'Answer structure',
      },
      {
        label: 'Confidence',
        score: normalize(
          latestEvaluation?.confidence_score
            ?? latestBehavior?.confidence_score
            ?? behaviorSummary?.overall_confidence,
          connected ? 82 : 0,
        ),
        hint: 'Delivery signal',
      },
      {
        label: 'Engagement',
        score: normalize(
          latestBehavior?.engagement_score ?? behaviorSummary?.overall_engagement,
          connected ? 78 : 0,
        ),
        hint: 'Camera presence',
      },
      {
        label: 'Technical Depth',
        score: normalize(latestEvaluation?.depth_score, baseScore ? baseScore - 6 : 0),
        hint: 'Reasoning depth',
      },
    ];
  }, [behaviorSummary, connected, latestBehavior, latestEvaluation, latestScore]);

  const aiAnalysisUnavailable = useMemo(() => (
    /failed|error|unable|unavailable|quota|429|exhausted/i.test(sessionStatus)
  ), [sessionStatus]);

  const liveInsights = useMemo(() => [
    connected ? 'Realtime interview channel is connected.' : 'Waiting for realtime interview channel.',
    latestEvaluation ? `Latest answer score: ${latestEvaluation.score}/100.` : 'Submit an answer to unlock score analysis.',
    latestBehavior
      ? `Eye contact is ${latestBehavior.eye_contact ? 'detected' : 'not steady yet'} with ${latestBehavior.emotion || 'neutral'} affect.`
      : 'Camera behavior analysis starts once frames are processed.',
  ], [connected, latestBehavior, latestEvaluation]);

  const costRows = useMemo(() => (
    Object.entries(sessionCost?.by_call_type || {})
      .map(([name, amount]) => ({ name, amount }))
  ), [sessionCost]);

  const speechMetrics = useMemo(() => {
    const metrics = latestEvaluation?.speech_metrics;
    const stopwordCount = metrics?.stopword_count ?? latestEvaluation?.stopword_count ?? 0;
    const wordCount = metrics?.word_count ?? latestEvaluation?.word_count ?? 0;
    const wordsPerMinute = metrics?.words_per_minute ?? latestEvaluation?.words_per_minute ?? 0;

    return {
      stopwordCount,
      wordCount,
      wordsPerMinute,
    };
  }, [latestEvaluation]);

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
    utterance.onend = () => setSessionStatus(connected ? 'Live session connected' : 'Question audio played');
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
      interviewerAudioRef.current?.pause();
      if (interviewerAudioUrlRef.current) {
        URL.revokeObjectURL(interviewerAudioUrlRef.current);
      }

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
        source.onended = () => setSessionStatus(connected ? 'Live session connected' : 'Question audio played');
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
      audio.onended = () => setSessionStatus(connected ? 'Live session connected' : 'Question audio played');
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

  const speakText = async (text: string, enableFutureQuestions = false) => {
    const cleanText = text.trim();
    if (!cleanText) {
      setSessionStatus('No question available to speak yet');
      return;
    }

    if (enableFutureQuestions) {
      setVoiceEnabled(true);
    }

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
    if (voiceEnabled && currentQuestion.text) {
      speakText(currentQuestion.text);
    }
  }, [currentQuestion.text, voiceEnabled]);

  const handleSoundCheck = () => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: 'ping' }));
    }

    speakText(
      currentQuestion.text || 'Sound check is working. Your interviewer voice is enabled.',
      true,
    );
  };

  const sendAudioBlob = async (blob: Blob, durationSec?: number) => {
    const question = currentQuestion.text?.trim();
    if (!interviewId || !question) {
      setSessionStatus('No active question is available for evaluation');
      return;
    }

    try {
      setSessionStatus('Answer sent. Waiting for evaluation...');
      const result = await api.interview.analyzeAudio(
        interviewId,
        question,
        blob,
        durationSec,
        currentQuestion.id,
      );

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

      const nextOrder = questionNumber;
      const nextQuestion = result.next_question || createLocalQuestion(
          activeInterview?.interview_mode || 'faang',
          activeInterview?.job_role || 'General role',
          nextOrder,
          activeInterview?.job_description || '',
          interviewId,
        );
      setCurrentQuestion(nextQuestion);
      setQuestionNumber(nextOrder + 1);
      activeInterviewStore().update({
        first_question: nextQuestion,
      });
      setSessionStatus('Answer evaluated. Next question is ready.');
      if (voiceEnabled && nextQuestion.text) {
        window.setTimeout(() => speakText(nextQuestion.text || ''), 0);
      }
    } catch (err) {
      setSessionStatus(err instanceof ApiError ? err.message : 'Audio evaluation failed.');
    }
  };

  const handleRecordToggle = () => {
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
    stream.getAudioTracks().forEach((track) => {
      track.enabled = true;
    });
    setIsMuted(false);
    setIsRecording(true);
    setSessionStatus('Recording answer...');
  };

  const handleMicToggle = () => {
    const stream = mediaStreamRef.current;
    if (!stream) {
      setSessionStatus(mediaError || 'Microphone is not ready');
      return;
    }

    const nextMuted = !isMuted;
    stream.getAudioTracks().forEach((track) => {
      track.enabled = !nextMuted;
    });
    setIsMuted(nextMuted);
    setSessionStatus(nextMuted ? 'Microphone muted' : 'Microphone active');
  };

  const handleVideoToggle = () => {
    const next = !isVideoOn;
    mediaStreamRef.current?.getVideoTracks().forEach((track) => {
      track.enabled = next;
    });
    setIsVideoOn(next);
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
    if (speechTimeoutRef.current) {
      window.clearTimeout(speechTimeoutRef.current);
    }
    audioSourceRef.current?.stop();
    interviewerAudioRef.current?.pause();
    if (interviewerAudioUrlRef.current) {
      URL.revokeObjectURL(interviewerAudioUrlRef.current);
    }
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
      <ImmersiveStage variant="ambient" className={styles.sunriseAmbient} />
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

      </motion.header>

      <div className={styles.interviewContent}>
        <motion.div
          className={styles.leftPanel}
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6 }}
        >
          <motion.section
            className={`${styles.cameraStage} ${isRecording ? styles.cameraStageSpeaking : ''}`}
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55 }}
          >
            <div className={styles.cameraFrame}>
              {isVideoOn ? (
                <video ref={localVideoRef} className={styles.localVideo} autoPlay playsInline muted />
              ) : (
                <div className={styles.cameraOffState}>
                  <div className={styles.avatar}>You</div>
                  <span>Camera paused</span>
                </div>
              )}

              <div className={styles.cameraGradient} />
              <div className={styles.cameraTopBar}>
                <div className={styles.participantPill}>
                  <span className={styles.liveDot} />
                  <strong>You</strong>
                  <small>{isRecording ? 'Answering now' : isVideoOn ? 'Camera live' : 'Video off'}</small>
                </div>
                <div className={`${styles.recordingBadge} ${isRecording ? styles.isLive : ''}`}>
                  {isRecording ? 'Recording' : connected ? 'Live session' : 'Connecting'}
                </div>
              </div>

              <motion.div
                className={styles.cameraPip}
                initial={{ opacity: 0, scale: 0.92, y: -12 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ duration: 0.45, delay: 0.1 }}
              >
                <div className={styles.pipAvatar}>AI</div>
                <div>
                  <strong>{activeInterview?.persona_name || 'AI interviewer'}</strong>
                  <span>{connected ? 'Listening' : 'Offline'}</span>
                </div>
                <div className={styles.pipWave}>
                  <span />
                  <span />
                  <span />
                </div>
              </motion.div>

              <div className={styles.cameraAiPulse} />

            </div>
          </motion.section>
          {mediaError && <div className={styles.mediaNotice}>{mediaError}</div>}

          <motion.div
            className={styles.cameraControls}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: 0.15 }}
          >
            <motion.button
              type="button"
              className={`${styles.cameraControl} ${isMuted ? styles.cameraControlOff : styles.cameraControlActive}`}
              onClick={handleMicToggle}
              title={isMuted ? 'Unmute microphone' : 'Mute microphone'}
              aria-label={isMuted ? 'Unmute microphone' : 'Mute microphone'}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.94 }}
            >
              <Mic size={18} />
              <span>{isMuted ? 'Mic Off' : 'Mic On'}</span>
            </motion.button>

            <motion.button
              type="button"
              className={`${styles.cameraControl} ${isRecording ? styles.cameraControlActive : ''}`}
              onClick={handleRecordToggle}
              title={isRecording ? 'Stop recording and submit answer' : 'Record answer'}
              aria-label={isRecording ? 'Stop recording and submit answer' : 'Record answer'}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.94 }}
            >
              <Circle size={18} />
              <span>{isRecording ? 'Stop & Submit' : 'Record & Submit'}</span>
            </motion.button>

            <motion.button
              type="button"
              className={`${styles.cameraControl} ${isVideoOn ? styles.cameraControlActive : styles.cameraControlOff}`}
              onClick={handleVideoToggle}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.95 }}
              title="Toggle camera"
              aria-label="Toggle camera"
            >
              <Video size={18} />
              <span>{isVideoOn ? 'Camera On' : 'Camera Off'}</span>
            </motion.button>

            <motion.button
              type="button"
              className={styles.cameraControl}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.95 }}
              onClick={handleSoundCheck}
              title="Speak question"
              aria-label="Speak question"
            >
              <Volume2 size={18} />
              <span>Speak Question</span>
            </motion.button>

            <motion.button
              type="button"
              className={`${styles.cameraControl} ${showInterviewSettings ? styles.cameraControlActive : ''}`}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setShowInterviewSettings((current) => !current)}
              title="Interview settings"
              aria-label="Interview settings"
            >
              <Settings size={18} />
              <span>Settings</span>
            </motion.button>

            <motion.button
              type="button"
              className={`${styles.cameraControl} ${styles.cameraControlDanger}`}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.95 }}
              onClick={handleEndInterview}
              title="End interview"
              aria-label="End interview"
            >
              <PhoneOff size={18} />
              <span>End Interview</span>
            </motion.button>
          </motion.div>

          {showInterviewSettings && (
            <motion.div
              className={styles.interviewSettingsPanel}
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
            >
              <div>
                <strong>Interview settings</strong>
                <span>{connected ? 'Realtime channel connected' : 'Realtime channel connecting'}</span>
              </div>
              <label>
                <input
                  type="checkbox"
                  checked={voiceEnabled}
                  onChange={(event) => setVoiceEnabled(event.target.checked)}
                />
                Auto-read next questions
              </label>
            </motion.div>
          )}

          <motion.section
            className={`${styles.insightPanel} ${styles.analyticsDashboard}`}
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            <motion.div className={styles.analyticsHeader} variants={itemVariants}>
              <div>
                <span>Realtime AI Analytics</span>
                <h3>Interview performance</h3>
              </div>
              <div className={styles.analyticsLivePill}>
                <span />
                {connected ? 'Live' : 'Syncing'}
              </div>
            </motion.div>

            {aiAnalysisUnavailable && (
              <motion.div className={styles.aiWarningCard} variants={itemVariants}>
                <strong>AI analysis temporarily unavailable</strong>
                <span>We will keep the interview running and refresh insights when the next analysis succeeds.</span>
              </motion.div>
            )}

            <motion.div className={styles.analyticsTopGrid} variants={containerVariants}>
              <motion.div className={styles.analyticsGrid} variants={containerVariants}>
                {analyticsMetrics.map((item) => (
                  <motion.div
                    key={item.label}
                    className={styles.metricWidget}
                    variants={itemVariants}
                    whileHover={{ y: -4, scale: 1.01 }}
                  >
                    <div className={styles.metricWidgetTop}>
                      <span className={styles.metricPulse} />
                      <small>{item.hint}</small>
                    </div>
                    <strong>{item.label}</strong>
                    <div className={styles.metricValueRow}>
                      <span>{item.score}</span>
                      <small>/100</small>
                    </div>
                    <div className={styles.metricProgress}>
                      <motion.div
                        style={{ width: `${item.score}%` }}
                      />
                    </div>
                  </motion.div>
                ))}
                {[
                  { label: 'Stopwords', value: speechMetrics.stopwordCount, hint: 'Speech discipline', suffix: '' },
                  { label: 'Words/min', value: speechMetrics.wordsPerMinute, hint: 'Speaking pace', suffix: 'wpm' },
                  { label: 'Word count', value: speechMetrics.wordCount, hint: 'Answer length', suffix: 'words' },
                ].map((item) => (
                  <motion.div
                    key={item.label}
                    className={`${styles.metricWidget} ${styles.speechMetricWidget}`}
                    variants={itemVariants}
                    whileHover={{ y: -4, scale: 1.01 }}
                  >
                    <div className={styles.metricWidgetTop}>
                      <span className={styles.metricPulse} />
                      <small>{item.hint}</small>
                    </div>
                    <strong>{item.label}</strong>
                    <div className={styles.metricValueRow}>
                      <span>{item.value}</span>
                      {item.suffix && <small>{item.suffix}</small>}
                    </div>
                    <div className={styles.metricProgress}>
                      <motion.div
                        style={{ width: `${Math.min(100, Math.max(0, item.value))}%` }}
                      />
                    </div>
                  </motion.div>
                ))}
              </motion.div>

              <motion.div className={styles.radarCard} variants={itemVariants}>
                <div className={styles.analyticsCardHeader}>
                  <h3>Skill radar</h3>
                  <span>Realtime shape</span>
                </div>
                <RadarScoreChart data={analyticsMetrics} />
              </motion.div>
            </motion.div>

            <motion.div className={styles.analyticsDeepGrid} variants={containerVariants}>
              <motion.div className={styles.aiSummaryCard} variants={itemVariants}>
                <div className={styles.analyticsCardHeader}>
                  <h3>AI summary</h3>
                  <span>{latestEvaluation?.provider || 'Intervue AI'}</span>
                </div>
                <p>
                  {aiAnalysisUnavailable
                    ? 'AI analysis temporarily unavailable'
                    : latestReasoning || behaviorSummary?.behavior_summary || latestBehavior?.notes || 'AI summary appears after the first answer is evaluated.'}
                </p>
                <div className={styles.liveInsights}>
                  {liveInsights.map((insight) => (
                    <span key={insight}>{insight}</span>
                  ))}
                </div>
              </motion.div>

              <motion.div className={styles.behaviorSnapshotCard} variants={itemVariants}>
                <div className={styles.analyticsCardHeader}>
                  <h3>Behavior signals</h3>
                  <span>{latestBehavior ? 'Active' : 'Pending'}</span>
                </div>
                <div className={styles.behaviorGrid}>
                  <span>Engagement: {latestBehavior?.engagement_score ?? behaviorSummary?.overall_engagement ?? 0}</span>
                  <span>Eye contact: {behaviorSummary?.eye_contact_ratio ?? (latestBehavior?.eye_contact ? 100 : 0)}%</span>
                  <span>Emotion: {behaviorSummary?.dominant_emotion || latestBehavior?.emotion || 'neutral'}</span>
                </div>
                <p>{aiAnalysisUnavailable ? 'AI analysis temporarily unavailable' : behaviorSummary?.behavior_summary || latestBehavior?.notes || 'Camera behavior insights will appear after frame analysis.'}</p>
              </motion.div>
            </motion.div>

          </motion.section>

        </motion.div>

        <motion.div
          className={styles.rightPanel}
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6 }}
        >
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
              <p>{activeInterview?.opening_line || currentQuestion.why_asked || sessionStatus}</p>
            </div>

            <motion.div
              className={styles.suggestedAnswer}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.5 }}
            >
              <div className={styles.guideHeader}>
                <span>Interview dashboard guide</span>
                <small>{connected ? 'Live' : 'Connecting'}</small>
              </div>
              <div className={styles.guideGrid}>
                <p className={styles.checkItem}>Click Record & Submit to record your answer, then click it again to submit.</p>
                <p className={styles.checkItem}>Use Situation, Action, Result for experience answers.</p>
                <p className={styles.checkItem}>Clarify assumptions before technical or system design answers.</p>
              </div>
              <p className={styles.liveNote}>{latestReasoning || 'Answer scoring appears here after audio is sent.'}</p>
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
            <h3>Speaking Activity</h3>
            <div className={styles.analyticsWaveform} aria-hidden="true">
              {Array.from({ length: 36 }).map((_, index) => (
                <motion.span
                  key={index}
                  animate={{
                    height: isRecording || (connected && !isMuted) ? `${20 + ((index * 19) % 72)}%` : '18%',
                  }}
                  transition={{
                    duration: 0.45,
                    repeat: Infinity,
                    repeatType: 'reverse',
                    delay: index * 0.015,
                  }}
                />
              ))}
            </div>
            <div className={styles.waveformInfo}>
              <span>{isRecording ? 'Capturing speech' : connected ? 'Ready for answer' : 'Waiting for channel'}</span>
              <motion.span
                className={styles.liveStatusDot}
                animate={{ opacity: [1, 0.5, 1] }}
                transition={{ duration: 1, repeat: Infinity }}
              />
            </div>
            {latestTranscript && (
              <p className={styles.transcriptText}>{latestTranscript}</p>
            )}
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

        </motion.div>
      </div>
    </div>
  );
};

export default InterviewPage;
