import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Award,
  BarChart3,
  CheckCircle2,
  FileDown,
  Home as HomeIcon,
  ListChecks,
  MessageSquare,
  Target,
  TrendingUp,
} from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ApiError,
  InterviewQuestion,
  InterviewRecord,
  Report,
  ReportFeedbackEntry,
  api,
  formatDate,
  tokenStore,
} from '../services/api';
import { ImmersiveStage } from '../components/immersive/ImmersiveStage';
import { motion } from '../components/ui/staticMotion';
import styles from './ResultPage.module.css';

type FeedbackItem = ReportFeedbackEntry & {
  topic: string;
};

const isRecord = (value: unknown): value is Record<string, unknown> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
);

const toScore = (value: unknown) => (
  typeof value === 'number' && Number.isFinite(value) ? Math.round(value) : 0
);

const uniqueTopics = (topics: string[]) => {
  const seen = new Set<string>();
  return topics.filter((topic) => {
    const cleanTopic = topic.trim();
    if (!cleanTopic || seen.has(cleanTopic.toLowerCase())) {
      return false;
    }
    seen.add(cleanTopic.toLowerCase());
    return true;
  });
};

const readinessLabel = (value?: string) => {
  if (!value) {
    return 'Readiness pending';
  }
  return value.replace(/_/g, ' ');
};

const scoreReadiness = (score: number) => {
  if (score >= 75) {
    return 'ready';
  }
  if (score >= 55) {
    return 'almost_ready';
  }
  return 'not_ready';
};

const reportFeedback = (report: Report | null): FeedbackItem[] => (
  Object.entries(report?.feedback_json || {})
    .map(([topic, details]) => {
      if (!isRecord(details)) {
        return null;
      }
      return {
        topic,
        ...(details as ReportFeedbackEntry),
      };
    })
    .filter((item): item is FeedbackItem => Boolean(item))
);

const behaviorSummary = (report: Report | null) => {
  const summary = report?.speech_summary?.behavior_summary;
  return isRecord(summary) ? summary : {};
};

const average = (values: number[]) => {
  const valid = values.filter((value) => value > 0);
  return valid.length ? Math.round(valid.reduce((total, value) => total + value, 0) / valid.length) : 0;
};

const ResultPage: React.FC = () => {
  const navigate = useNavigate();
  const { interviewId = '' } = useParams();
  const [interview, setInterview] = useState<InterviewRecord | null>(null);
  const [questions, setQuestions] = useState<InterviewQuestion[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!tokenStore.get()) {
      navigate('/login');
      return;
    }

    if (!interviewId) {
      setError('Interview result not found.');
      setLoading(false);
      return;
    }

    let cancelled = false;

    const loadResult = async () => {
      setLoading(true);
      setError('');
      setNotice('');

      const [statusResult, reportResult] = await Promise.allSettled([
        api.interview.status(interviewId),
        api.report.get(interviewId),
      ]);

      if (cancelled) {
        return;
      }

      const unauthorized = [statusResult, reportResult].some((result) => (
        result.status === 'rejected'
        && result.reason instanceof ApiError
        && result.reason.status === 401
      ));
      if (unauthorized) {
        tokenStore.clear();
        navigate('/login');
        return;
      }

      if (statusResult.status === 'fulfilled') {
        setInterview(statusResult.value.interview);
        setQuestions(statusResult.value.questions);
      }

      if (reportResult.status === 'fulfilled') {
        setReport(reportResult.value);
      } else if (reportResult.reason instanceof ApiError && reportResult.reason.status === 404) {
        setNotice('Report details are still being generated. Showing saved interview questions for now.');
      }

      if (statusResult.status === 'rejected' && reportResult.status === 'rejected') {
        setError(statusResult.reason instanceof ApiError ? statusResult.reason.message : 'Unable to load result.');
      }

      setLoading(false);
    };

    loadResult();

    return () => {
      cancelled = true;
    };
  }, [interviewId, navigate]);

  const feedback = useMemo(() => reportFeedback(report), [report]);
  const summary = useMemo(() => behaviorSummary(report), [report]);
  const overallScore = report?.overall_score ?? interview?.overall_score ?? 0;
  const readiness = readinessLabel(report?.interview_readiness || scoreReadiness(overallScore));
  const strongTopics = useMemo(() => uniqueTopics([
    ...(report?.strengths || []).filter((topic) => topic !== 'Completed a live mock interview'),
    ...feedback
      .filter((item) => typeof item.score === 'number' && Number(item.score) >= 75)
      .map((item) => item.topic),
  ]).slice(0, 6), [feedback, report]);
  const weakTopics = useMemo(() => uniqueTopics([
    ...feedback
      .filter((item) => typeof item.score === 'number' && Number(item.score) < 70)
      .map((item) => item.topic),
    ...(report?.next_session_focus || []),
  ]).slice(0, 6), [feedback, report]);
  const askedQuestions = useMemo(() => {
    if (questions.length) {
      return [...questions].sort((left, right) => (left.order_idx || 0) - (right.order_idx || 0));
    }
    return feedback
      .filter((item) => item.question)
      .map((item, index) => ({
        text: item.question,
        topic: item.topic,
        category: 'Interview',
        order_idx: index,
      }));
  }, [feedback, questions]);

  const engagement = toScore(summary.overall_engagement);
  const confidence = toScore(summary.overall_confidence);
  const professionalism = toScore(summary.overall_professionalism);
  const nervousness = toScore(summary.overall_nervousness);
  const behaviorScore = average([engagement, confidence, professionalism]);
  const scoreCards = [
    { label: 'Overall Score', value: `${overallScore}`, detail: '/100', icon: Award },
    { label: 'Readiness', value: readiness, detail: 'overall', icon: TrendingUp },
    { label: 'Questions Asked', value: `${askedQuestions.length}`, detail: 'saved', icon: ListChecks },
    { label: 'Behaviour Score', value: `${behaviorScore}`, detail: '/100', icon: BarChart3 },
  ];

  const saveReportBlob = (blob: Blob) => {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `intervue-report-${interviewId.slice(0, 8)}.pdf`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  const handleDownloadPdf = async () => {
    if (!interviewId) {
      return;
    }

    try {
      setDownloading(true);
      setError('');
      const blob = await api.report.downloadPdf(interviewId);
      saveReportBlob(blob);
      setNotice('PDF report downloaded.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to download PDF report.');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className={styles.resultPage}>
      <ImmersiveStage variant="ambient" />
      <main className={styles.resultShell}>
        <header className={styles.resultHeader}>
          <div>
            <span className={styles.eyebrow}>Interview result</span>
            <h1>{interview?.job_role || 'Completed interview'}</h1>
            <p>{formatDate(interview?.completed_at || interview?.created_at)}</p>
          </div>
          <div className={styles.headerActions}>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={handleDownloadPdf}
              disabled={downloading || loading}
            >
              <FileDown size={18} />
              {downloading ? 'Generating' : 'PDF Report'}
            </button>
            <button type="button" className={styles.homeButton} onClick={() => navigate('/home')}>
              <HomeIcon size={18} />
              Home
            </button>
          </div>
        </header>

        {loading && <div className={styles.notice}>Loading your result...</div>}
        {notice && !loading && <div className={styles.notice}>{notice}</div>}
        {error && !loading && <div className={styles.errorNotice}>{error}</div>}

        {!loading && !error && (
          <>
            <section className={styles.scoreGrid}>
              {scoreCards.map((card) => {
                const Icon = card.icon;
                return (
                  <motion.div key={card.label} className={styles.scoreCard} whileHover={{ y: -4 }}>
                    <div className={styles.cardIcon}><Icon size={20} /></div>
                    <span>{card.label}</span>
                    <strong>{card.value}</strong>
                    <small>{card.detail}</small>
                  </motion.div>
                );
              })}
            </section>

            <section className={styles.topicGrid}>
              <div className={styles.panel}>
                <div className={styles.panelHeader}>
                  <CheckCircle2 size={20} />
                  <h2>Strong Topics</h2>
                </div>
                <div className={styles.topicList}>
                  {(strongTopics.length ? strongTopics : ['No strong topic recorded yet']).map((topic) => (
                    <span key={topic}>{topic}</span>
                  ))}
                </div>
              </div>

              <div className={styles.panel}>
                <div className={styles.panelHeader}>
                  <AlertTriangle size={20} />
                  <h2>Weak Topics</h2>
                </div>
                <div className={styles.topicList}>
                  {(weakTopics.length ? weakTopics : ['No weak topic recorded yet']).map((topic) => (
                    <span key={topic}>{topic}</span>
                  ))}
                </div>
              </div>
            </section>

            <section className={styles.contentGrid}>
              <div className={styles.panel}>
                <div className={styles.panelHeader}>
                  <ListChecks size={20} />
                  <h2>Questions Asked</h2>
                </div>
                <div className={styles.questionList}>
                  {askedQuestions.length === 0 && <p>No saved questions were found for this interview.</p>}
                  {askedQuestions.map((question, index) => (
                    <article key={`${question.text}-${index}`}>
                      <span>Q{index + 1}</span>
                      <h3>{question.text}</h3>
                      <small>{question.category || 'Interview'} / {question.topic || 'General'}</small>
                    </article>
                  ))}
                </div>
              </div>

              <div className={styles.panel}>
                <div className={styles.panelHeader}>
                  <MessageSquare size={20} />
                  <h2>Live Feedback</h2>
                </div>
                <div className={styles.feedbackList}>
                  {feedback.length === 0 && <p>Answer feedback will appear once the report is available.</p>}
                  {feedback.map((item) => (
                    <article key={item.topic}>
                      <div>
                        <strong>{item.topic}</strong>
                        <span>{item.score ?? 0}/100</span>
                      </div>
                      <p>{item.reasoning || 'No detailed feedback was saved for this answer.'}</p>
                    </article>
                  ))}
                </div>
              </div>
            </section>

            <section className={styles.behaviorPanel}>
              <div className={styles.panelHeader}>
                <Target size={20} />
                <h2>Behaviour Signals</h2>
              </div>
              <div className={styles.behaviorGrid}>
                <span>Engagement <strong>{engagement}</strong></span>
                <span>Confidence <strong>{confidence}</strong></span>
                <span>Professionalism <strong>{professionalism}</strong></span>
                <span>Nervousness <strong>{nervousness}</strong></span>
              </div>
              <p>{typeof summary.behavior_summary === 'string' ? summary.behavior_summary : 'No behaviour summary was saved for this interview.'}</p>
            </section>
          </>
        )}
      </main>
    </div>
  );
};

export default ResultPage;
