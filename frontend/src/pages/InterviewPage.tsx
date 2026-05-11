import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Mic, Video, Share2, Settings, Clock, Volume2 } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  ApiError,
  InterviewQuestion,
  Report,
  activeInterviewStore,
  api,
  tokenStore,
} from '../services/api';
import styles from './InterviewPage.module.css';

type SessionMessage = {
  type: 'pong' | 'next_question' | 'interview_complete' | 'error';
  question?: string;
  question_number?: number;
  topic?: string;
  why_asked?: string;
  previous_score?: number;
  previous_reasoning?: string;
  overall_score?: number;
  grade?: string;
  report?: Report;
  message?: string;
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
  const [report, setReport] = useState<Report | null>(null);
  const [voiceEnabled, setVoiceEnabled] = useState(false);

  useEffect(() => {
    if (!tokenStore.get()) {
      navigate('/login');
      return;
    }

    if (!interviewId) {
      setSessionStatus('No active interview. Start one from the dashboard.');
      return;
    }

    const loadStatus = async () => {
      try {
        const status = await api.interview.status(interviewId);
        const firstSavedQuestion = status.questions[0];
        if (firstSavedQuestion) {
          setCurrentQuestion(firstSavedQuestion);
          setQuestionNumber((firstSavedQuestion.order_idx || 0) + 1);
        }
        setSessionStatus(status.interview.status === 'completed' ? 'Interview completed' : 'Session ready');
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          tokenStore.clear();
          navigate('/login');
          return;
        }
        setSessionStatus(err instanceof ApiError ? err.message : 'Unable to load interview status.');
      }
    };

    loadStatus();
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

      if (message.type === 'next_question') {
        setCurrentQuestion({
          text: message.question,
          topic: message.topic,
          why_asked: message.why_asked,
          difficulty: 'adaptive',
          category: 'Live',
          order_idx: (message.question_number || 1) - 1,
        });
        setQuestionNumber(message.question_number || 1);
        setLatestScore(message.previous_score ?? null);
        setLatestReasoning(message.previous_reasoning || '');
        setSessionStatus('Next question received');
      }

      if (message.type === 'interview_complete') {
        setLatestScore(message.overall_score ?? null);
        setReport(message.report || null);
        setSessionStatus(`Interview completed${message.grade ? ` · ${message.grade}` : ''}`);
        activeInterviewStore().clear();
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
    const timer = setInterval(() => {
      setTimeLeft((prev) => (prev > 0 ? prev - 1 : prev));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;

  const feedbackScores = useMemo(() => {
    const baseScore = latestScore ?? report?.overall_score ?? 0;
    return [
      { label: 'Clarity', score: Math.min(100, Math.max(0, baseScore || 0)) },
      { label: 'Confidence', score: connected ? 85 : 20 },
      { label: 'Depth', score: baseScore ? Math.max(0, baseScore - 6) : 0 },
      { label: 'Pace', score: connected ? 80 : 0 },
    ];
  }, [connected, latestScore, report]);

  const speakText = (text: string, enableFutureQuestions = false) => {
    if (!('speechSynthesis' in window)) {
      setSessionStatus('Speech playback is not supported in this browser');
      return;
    }

    const cleanText = text.trim();
    if (!cleanText) {
      setSessionStatus('No question available to speak yet');
      return;
    }

    if (enableFutureQuestions) {
      setVoiceEnabled(true);
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

  const sendAudioBlob = async (blob: Blob) => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) {
      setSessionStatus('Live session is not connected');
      return;
    }

    const buffer = await blob.arrayBuffer();
    socketRef.current.send(buffer);
    setSessionStatus('Answer sent. Waiting for evaluation...');
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
      sendAudioBlob(blob);
    };

    recorder.start();
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

  const handleEndInterview = () => {
    socketRef.current?.close();
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
              <p>{activeInterview?.opening_line || currentQuestion.why_asked || sessionStatus}</p>
            </div>

            <motion.div
              className={styles.suggestedAnswer}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.5 }}
            >
              <p className={styles.checkItem}>✓ Backend session id: {interviewId || 'none'}</p>
              <p className={styles.checkItem}>✓ {connected ? 'WebSocket connected' : 'Waiting for WebSocket'}</p>
              <p className={styles.checkItem}>✓ {latestReasoning || 'Answer scoring appears here after audio is sent.'}</p>
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
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              title={isRecording ? 'Stop and send answer' : 'Record answer'}
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
            <button type="button" className={styles.answerAction} onClick={handleRecordToggle}>
              {isRecording ? 'Stop & Send' : 'Record Answer'}
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
                    height: connected && !isMuted ? `${20 + ((i * 17) % 80)}%` : '10%',
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
              <span>{connected ? 'Live channel ready' : 'Waiting for channel'}</span>
              <motion.span
                animate={{ opacity: [1, 0.5, 1] }}
                transition={{ duration: 1, repeat: Infinity }}
              >
                🔴
              </motion.span>
            </div>
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
              onClick={handleSoundCheck}
            >
              <Volume2 size={16} />
              Speak Question
            </motion.button>
          </motion.div>
        </motion.div>
      </div>
    </div>
  );
};

export default InterviewPage;
