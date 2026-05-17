import React, { useEffect, useMemo, useState } from 'react';
import { Bell, LogOut, Search, Home, BookOpen, FileText, BarChart3, Bookmark, FileDown, Shield } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { ImmersiveStage } from '../components/immersive/ImmersiveStage';
import { motion } from '../components/ui/staticMotion';
import {
  ApiError,
  DashboardResponse,
  InterviewMode,
  InterviewRecord,
  Report,
  ReportFeedbackEntry,
  Resume,
  UserProfile,
  activeInterviewStore,
  api,
  formatDate,
  interviewHistoryStore,
  normalizeDashboard,
  tokenStore,
} from '../services/api';
import styles from './HomePage.module.css';

const emptyDashboard: DashboardResponse = {
  stats: {
    total_interviews: 0,
    completed_interviews: 0,
    average_score: 0,
    overall_readiness: 0,
    weakest_topic: 'Start with a mock interview',
    resume_count: 0,
  },
  score_trend: [],
  activities: [],
  recent_interviews: [],
  recommendations: [
    { title: 'Upload a resume', description: 'Personalize questions from your experience.' },
    { title: 'Start a mock interview', description: 'Generate a first question from your selected role.' },
  ],
  resumes: [],
};

const REPORT_LIMIT = 10;
const EMBEDDING_STATUS_POLL_MS = 2000;
const EMBEDDING_STATUS_MAX_POLLS = 20;
type HomeTab = 'overview' | 'interviews' | 'resumes' | 'reports' | 'practice';

const reportTime = (interview: InterviewRecord) => (
  new Date(interview.completed_at || interview.created_at || 0).getTime()
);

const sortNewestInterviews = (interviews: InterviewRecord[]) => (
  [...interviews].sort((left, right) => reportTime(right) - reportTime(left))
);

const feedbackEntries = (report: Report) => (
  Object.entries(report.feedback_json || {})
    .map(([topic, details]) => {
      if (!details || typeof details !== 'object') {
        return null;
      }
      return {
        topic,
        ...(details as ReportFeedbackEntry),
      };
    })
    .filter((entry): entry is ReportFeedbackEntry & { topic: string } => Boolean(entry))
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

const weakTopicsFromReports = (reports: Report[]) => {
  const scoredWeakTopics = reports.flatMap((report) => (
    feedbackEntries(report)
      .filter((entry) => typeof entry.score === 'number' && Number(entry.score) < 70)
      .map((entry) => entry.topic)
  ));
  const fallbackFocus = reports.flatMap((report) => report.next_session_focus || []);
  return uniqueTopics([...scoredWeakTopics, ...fallbackFocus]).slice(0, 6);
};

const readinessLabel = (value?: string) => {
  if (!value) {
    return 'Readiness pending';
  }
  return value.replace(/_/g, ' ');
};

const wait = (ms: number) => new Promise((resolve) => {
  window.setTimeout(resolve, ms);
});

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse>(emptyDashboard);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [adminAccess, setAdminAccess] = useState(false);
  const [selectedResumeId, setSelectedResumeId] = useState('');
  const [jobRole, setJobRole] = useState('Frontend Developer');
  const [jobDescription, setJobDescription] = useState('');
  const [interviewMode, setInterviewMode] = useState<InterviewMode>('faang');
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [downloadingReportId, setDownloadingReportId] = useState('');
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [activeTab, setActiveTab] = useState<HomeTab>('overview');

  useEffect(() => {
    if (!tokenStore.get()) {
      navigate('/login');
      return;
    }

    const loadDashboard = async () => {
      try {
        setLoading(true);
        const localInterviews = interviewHistoryStore().list();
        const me = await api.auth.me();
        const [resumeResult, interviewResult, adminAccessResult] = await Promise.allSettled([
          api.resume.list(),
          api.interview.list(),
          api.admin.me(),
        ]);

        const resumeData = resumeResult.status === 'fulfilled'
          ? resumeResult.value
          : { resumes: [] };
        const recentInterviews = sortNewestInterviews(
          interviewResult.status === 'fulfilled'
            ? interviewResult.value.interviews
            : localInterviews,
        );
        const completedInterviews = recentInterviews.filter((item) => item.status === 'completed');
        const scoredInterviews = completedInterviews.filter((item) => typeof item.overall_score === 'number');
        const averageScore = scoredInterviews.length
          ? Math.round(scoredInterviews.reduce((total, item) => total + (item.overall_score || 0), 0) / scoredInterviews.length)
          : 0;
        const adminData = {
          total_interviews: recentInterviews.length,
          completed_interviews: completedInterviews.length,
          average_score: averageScore,
          total_users: 0,
          today_cost_inr: 0,
        };
        const dashboardData = normalizeDashboard(adminData, resumeData.resumes, recentInterviews);

        setProfile(me);
        setAdminAccess(adminAccessResult.status === 'fulfilled' && adminAccessResult.value.is_admin);
        setDashboard(dashboardData);
        setResumes(resumeData.resumes);
        setSelectedResumeId(resumeData.resumes[0]?.id || dashboardData.resumes[0]?.id || '');
        if (
          resumeResult.status === 'rejected'
          || interviewResult.status === 'rejected'
        ) {
          setStatus('Logged in. Some dashboard data is temporarily unavailable.');
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          tokenStore.clear();
          navigate('/login');
          return;
        }
        setError(err instanceof ApiError ? err.message : 'Unable to load dashboard data.');
      } finally {
        setLoading(false);
      }
    };

    loadDashboard();
  }, [navigate]);

  const sortedInterviews = useMemo(
    () => sortNewestInterviews(dashboard.recent_interviews),
    [dashboard.recent_interviews],
  );
  const reportInterviews = useMemo(
    () => sortedInterviews.filter((interview) => interview.status === 'completed').slice(0, REPORT_LIMIT),
    [sortedInterviews],
  );
  const reportInterviewIds = useMemo(
    () => reportInterviews.map((interview) => interview.id).join('|'),
    [reportInterviews],
  );
  const reportByInterviewId = useMemo(
    () => new Map(reports.map((report) => [report.interview_id, report])),
    [reports],
  );
  const weakTopics = useMemo(() => weakTopicsFromReports(reports), [reports]);
  const displayedWeakTopics = weakTopics.length
    ? weakTopics
    : [dashboard.stats.weakest_topic].filter(Boolean);

  useEffect(() => {
    if (!tokenStore.get() || reportInterviews.length === 0) {
      setReports([]);
      return undefined;
    }

    let cancelled = false;
    Promise.allSettled(reportInterviews.map((interview) => api.report.get(interview.id)))
      .then((results) => {
        if (cancelled) {
          return;
        }
        setReports(results.flatMap((result) => (result.status === 'fulfilled' ? [result.value] : [])));
      });

    return () => {
      cancelled = true;
    };
  }, [reportInterviews, reportInterviewIds]);

  const statCards = useMemo(() => [
    {
      label: 'Overall Score',
      value: String(dashboard.stats.average_score || 0),
      status: '/100 average',
      trend: dashboard.stats.completed_interviews ? 'From completed reports' : 'Complete an interview first',
      color: '#7C3AED',
    },
    {
      label: 'Overall Readiness',
      value: `${dashboard.stats.overall_readiness || 0}%`,
      status: dashboard.stats.completed_interviews ? 'Based on completed interviews' : 'No completed interviews yet',
      trend: `${dashboard.stats.completed_interviews} completed`,
      color: '#7C3AED',
    },
    {
      label: 'Interviews Taken',
      value: String(dashboard.stats.total_interviews),
      status: 'All sessions',
      trend: `${dashboard.stats.resume_count} resumes uploaded`,
      color: '#8B5CF6',
    },
  ], [dashboard]);

  const handleLogout = () => {
    tokenStore.clear();
    navigate('/login');
  };

  const pollResumeEmbedding = async (resumeId: string, taskId: string) => {
    for (let attempt = 0; attempt < EMBEDDING_STATUS_MAX_POLLS; attempt += 1) {
      await wait(EMBEDDING_STATUS_POLL_MS);

      try {
        const embedding = await api.resume.embeddingStatus(resumeId, taskId);

        if (embedding.embedding_status === 'completed') {
          const chunkCopy = embedding.chunks_stored
            ? ` ${embedding.chunks_stored} chunks embedded.`
            : '';
          setStatus(`Resume ready for personalized questions.${chunkCopy}`);
          return;
        }

        if (embedding.embedding_status === 'failed') {
          setError(embedding.error || 'Resume embeddings failed. Try uploading again.');
          return;
        }
      } catch (err) {
        if (attempt === EMBEDDING_STATUS_MAX_POLLS - 1) {
          setError(err instanceof ApiError ? err.message : 'Unable to check resume embedding status.');
        }
      }
    }

    setStatus('Resume parsed. Embeddings are still running in the background.');
  };

  const handleResumeUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    try {
      setUploading(true);
      setError('');
      setStatus('Uploading and parsing resume...');
      const result = await api.resume.upload(file);
      const freshResumes = await api.resume.list();
      setResumes(freshResumes.resumes);
      setSelectedResumeId(result.resume_id);
      setStatus(result.message);
      if (result.embedding_status === 'queued' && result.embedding_task_id) {
        void pollResumeEmbedding(result.resume_id, result.embedding_task_id);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Resume upload failed.');
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const handleSelectResume = async (resumeId: string) => {
    setSelectedResumeId(resumeId);

    if (!resumeId) {
      return;
    }

    try {
      const resume = await api.resume.get(resumeId);
      setResumes((current) => current.map((item) => (item.id === resumeId ? { ...item, ...resume } : item)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to load resume details.');
    }
  };

  const handleDeleteResume = async () => {
    if (!selectedResumeId) {
      return;
    }

    try {
      setError('');
      await api.resume.delete(selectedResumeId);
      const freshResumes = await api.resume.list();
      setResumes(freshResumes.resumes);
      setSelectedResumeId(freshResumes.resumes[0]?.id || '');
      setDashboard((current) => normalizeDashboard(
        {
          total_interviews: current.stats.total_interviews,
          completed_interviews: current.stats.completed_interviews,
          average_score: current.stats.average_score,
          total_users: Number(current.activities.find((item) => item.name === 'Users')?.value || 0),
          today_cost_inr: 0,
        },
        freshResumes.resumes,
        current.recent_interviews,
      ));
      setStatus('Resume deleted.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to delete resume.');
    }
  };

  const handleStartInterview = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!selectedResumeId) {
      setError('Upload or select a resume before starting an interview.');
      return;
    }

    try {
      setStarting(true);
      setError('');
      setStatus('Starting interview session...');
      const started = await api.interview.start(selectedResumeId, jobRole, interviewMode, jobDescription);
      activeInterviewStore().set(started);
      interviewHistoryStore().upsert({
        id: started.interview_id,
        resume_id: started.resume_id,
        job_role: started.job_role,
        job_description: started.job_description || jobDescription,
        interview_mode: started.interview_mode,
        status: 'in_progress',
        overall_score: null,
        created_at: started.created_at,
        completed_at: null,
      });
      navigate(`/interview?interviewId=${started.interview_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to start interview.');
    } finally {
      setStarting(false);
    }
  };

  const saveReportBlob = (blob: Blob, interviewId: string) => {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `intervue-report-${interviewId.slice(0, 8)}.pdf`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  const handleDownloadReport = async (interview: InterviewRecord) => {
    if (interview.status !== 'completed') {
      setError('Complete the interview before generating a PDF report.');
      return;
    }

    try {
      setError('');
      setDownloadingReportId(interview.id);
      setStatus('Preparing PDF report...');
      let blob: Blob;
      try {
        blob = await api.report.downloadPdf(interview.id);
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 404) {
          throw err;
        }
        setStatus('Generating PDF report...');
        await api.interview.complete(interview.id, interview.overall_score ?? null, null);
        blob = await api.report.downloadPdf(interview.id);
      }
      saveReportBlob(blob, interview.id);
      setStatus('Report downloaded.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to generate PDF report.');
    } finally {
      setDownloadingReportId('');
    }
  };

  const navItems = [
    { id: 'overview', label: 'Home', icon: Home },
    { id: 'interviews', label: 'Interviews', icon: BookOpen },
    { id: 'resumes', label: 'Resumes', icon: FileText },
    { id: 'reports', label: 'Reports', icon: BarChart3 },
    { id: 'practice', label: 'Practice', icon: Bookmark },
    ...(adminAccess ? [{ id: 'admin', label: 'Admin', icon: Shield }] : []),
  ] as const;

  const tabCopy = {
    overview: {
      title: 'Home',
      description: 'Your readiness, recent progress, and next best action.',
    },
    interviews: {
      title: 'Interviews',
      description: 'Open previous sessions or continue any interview still in progress.',
    },
    resumes: {
      title: 'Resumes',
      description: 'Upload, select, and inspect the resume used to personalize interviews.',
    },
    reports: {
      title: 'Reports',
      description: 'Your latest 10 completed interview reports.',
    },
    practice: {
      title: 'Practice',
      description: 'Choose a resume, role, and interview style to start a realtime session.',
    },
  }[activeTab];

  const selectedResume = resumes.find((resume) => resume.id === selectedResumeId);

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1, delayChildren: 0.2 },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.6 } },
  };

  return (
    <div className={styles.homePage}>
      <ImmersiveStage variant="ambient" />
      <motion.aside
        className={styles.sidebar}
        initial={{ x: -250 }}
        animate={{ x: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className={styles.sidebarContent}>
          <div className={styles.sidebarLogo}>
            <div className={styles.logoIcon}>⚡</div>
            <span>intervue.ai</span>
          </div>

          <nav className={styles.sidebarNav}>
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <motion.button
                  key={item.id}
                  type="button"
                  className={`${styles.navItem} ${activeTab === item.id ? styles.active : ''}`}
                  whileHover={{ x: 5 }}
                  onClick={() => {
                    if (item.id === 'admin') {
                      navigate('/admin');
                      return;
                    }
                    setActiveTab(item.id as HomeTab);
                  }}
                >
                  <Icon size={20} />
                  <span>{item.label}</span>
                </motion.button>
              );
            })}
          </nav>

          <div className={styles.sidebarFooter}>
            <motion.button className={styles.logoutBtn} whileHover={{ scale: 1.05 }} onClick={handleLogout}>
              <LogOut size={18} />
              <span>Log out</span>
            </motion.button>
          </div>
        </div>
      </motion.aside>

      <div className={styles.mainContent}>
        <motion.header
          className={styles.header}
          initial={{ y: -50, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.6 }}
        >
          <div className={styles.headerLeft}>
            <div className={styles.searchBar}>
              <Search size={20} />
              <input type="text" placeholder="Search interviews, topics..." />
            </div>
          </div>

          <div className={styles.headerRight}>
            <motion.button className={styles.iconBtn} whileHover={{ scale: 1.1 }} onClick={() => setActiveTab('interviews')}>
              <Bell size={20} />
              <span className={styles.badge}>{dashboard.stats.total_interviews}</span>
            </motion.button>
            <motion.div className={styles.userProfile} whileHover={{ scale: 1.05 }}>
              <div className={styles.avatar}>{profile?.full_name?.[0]?.toUpperCase() || 'U'}</div>
            </motion.div>
          </div>
        </motion.header>

        <motion.section
          className={styles.welcomeSection}
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          <motion.div variants={itemVariants}>
            <h1>Welcome back, {profile?.full_name || profile?.email || 'candidate'}</h1>
            <p>{loading ? 'Loading your interview workspace...' : 'Continue your interview journey with your latest backend data.'}</p>
          </motion.div>
        </motion.section>

        <section className={styles.tabHeader}>
          <div>
            <h2>{tabCopy.title}</h2>
            <p>{tabCopy.description}</p>
          </div>
          {activeTab !== 'practice' && (
            <button type="button" onClick={() => setActiveTab('practice')}>
              Start practice
            </button>
          )}
        </section>

        {(error || status) && (
          <div className={error ? styles.alertError : styles.alertSuccess}>
            {error || status}
          </div>
        )}

        {activeTab === 'overview' && <motion.div
          className={styles.statsGrid}
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          {statCards.map((stat) => (
            <motion.div
              key={stat.label}
              className={styles.statCard}
              variants={itemVariants}
              whileHover={{ y: -10 }}
              transition={{ duration: 0.3 }}
            >
              <div className={styles.statHeader}>
                <h3>{stat.label}</h3>
              </div>
              <div className={styles.statValue} style={{ color: stat.color }}>
                {stat.value}
              </div>
              <p className={styles.statStatus}>{stat.status}</p>
              <p className={styles.statTrend}>{stat.trend}</p>
            </motion.div>
          ))}
        </motion.div>}

        {activeTab === 'overview' && (
          <motion.section
            className={styles.weakTopicPanel}
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            <div className={styles.sectionHeader}>
              <h3>Weak Topics</h3>
              <span>{displayedWeakTopics.length} focus areas</span>
            </div>

            <div className={styles.topicPillGrid}>
              {displayedWeakTopics.map((topic) => (
                <span key={topic}>{topic}</span>
              ))}
            </div>
          </motion.section>
        )}

        {activeTab === 'practice' && <motion.section
          className={styles.launchPanel}
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          <motion.div className={styles.launchCard} variants={itemVariants}>
            <div className={styles.sectionHeader}>
              <h3>Resume</h3>
              <label className={styles.uploadButton}>
                {uploading ? 'Uploading...' : 'Upload PDF/DOCX'}
                <input type="file" accept=".pdf,.docx" onChange={handleResumeUpload} disabled={uploading} />
              </label>
            </div>
            <select value={selectedResumeId} onChange={(event) => handleSelectResume(event.target.value)}>
              <option value="">Select a resume</option>
              {resumes.map((resume) => (
                <option key={resume.id} value={resume.id}>
                  {resume.file_name || resume.id}
                </option>
              ))}
            </select>
          </motion.div>

          <motion.form className={`${styles.launchCard} ${styles.interviewForm}`} variants={itemVariants} onSubmit={handleStartInterview}>
            <div className={styles.sectionHeader}>
              <h3>Start Interview</h3>
            </div>
            <textarea
              className={styles.jobDescriptionInput}
              value={jobDescription}
              onChange={(event) => setJobDescription(event.target.value)}
              placeholder="Paste the job description, responsibilities, and requirements"
              rows={5}
            />
            <div className={styles.formRow}>
              <input value={jobRole} onChange={(event) => setJobRole(event.target.value)} placeholder="Job role" />
              <select value={interviewMode} onChange={(event) => setInterviewMode(event.target.value as InterviewMode)}>
                <option value="faang">FAANG technical interview</option>
                <option value="startup">Startup product interview</option>
                <option value="hr">HR behavioral interview</option>
              </select>
              <button type="submit" disabled={starting || !selectedResumeId}>
                {starting ? 'Starting...' : 'Start'}
              </button>
            </div>
          </motion.form>
        </motion.section>}

        {activeTab === 'resumes' && (
          <section className={styles.resumePanel}>
            <div className={styles.sectionHeader}>
              <h3>Saved Resumes</h3>
              <label className={styles.uploadButton}>
                {uploading ? 'Uploading...' : 'Upload PDF/DOCX'}
                <input type="file" accept=".pdf,.docx" onChange={handleResumeUpload} disabled={uploading} />
              </label>
            </div>
            <p className={styles.sectionMeta}>{resumes.length} uploaded · selected resumes personalize every interview.</p>

            {resumes.length === 0 && (
              <p className={styles.emptyState}>No resumes saved yet. Upload a PDF or DOCX to start personalizing interviews.</p>
            )}

            <div className={styles.resumeList}>
              {resumes.map((resume) => (
                <button
                  key={resume.id}
                  type="button"
                  className={`${styles.resumeItem} ${selectedResumeId === resume.id ? styles.selectedResume : ''}`}
                  onClick={() => handleSelectResume(resume.id)}
                >
                  <strong>{resume.file_name || 'Resume'}</strong>
                  <span>{formatDate(resume.created_at)}</span>
                </button>
              ))}
            </div>

            {selectedResume && (
              <div className={styles.resumeDetails}>
                <div className={styles.resumeDetailsHeader}>
                  <h4>{selectedResume.file_name || 'Selected resume'}</h4>
                  <button type="button" className={styles.smallAction} onClick={handleDeleteResume}>
                    Delete
                  </button>
                </div>
                <p>{selectedResume.parsed_json?.summary || 'Parsed resume data will appear here after upload.'}</p>
                <div className={styles.chipGroup}>
                  {(selectedResume.parsed_json?.skills || []).slice(0, 12).map((skill) => (
                    <span key={skill}>{skill}</span>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {activeTab === 'overview' && <motion.div
          className={styles.bottomSection}
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
        >
          <motion.div className={styles.recentInterviews} variants={itemVariants}>
            <div className={styles.sectionHeader}>
              <h3>Recent Interviews</h3>
              <button className={styles.linkButton} type="button" onClick={() => setActiveTab('interviews')}>View all</button>
            </div>

            {sortedInterviews.length === 0 && (
              <p className={styles.emptyState}>No interviews yet. Start one from the practice tab.</p>
            )}

            {sortedInterviews.map((interview) => (
              <motion.div
                key={interview.id}
                className={styles.interviewItem}
                whileHover={{ x: 10 }}
                transition={{ duration: 0.3 }}
                onClick={() => navigate(interview.status === 'completed'
                  ? `/interview/result/${interview.id}`
                  : `/interview?interviewId=${interview.id}`)}
              >
                <div className={styles.interviewInfo}>
                  <div className={styles.interviewIcon}>
                    <BookOpen size={18} />
                  </div>
                  <div className={styles.interviewDetails}>
                    <h4>{interview.job_role || 'Interview session'}</h4>
                    <p>
                      {formatDate(interview.completed_at || interview.created_at)}
                      {' · '}
                      {interview.status}
                      {interview.job_description ? ' · JD tailored' : ''}
                    </p>
                  </div>
                </div>
                <div className={styles.interviewScore}>
                  {interview.status === 'completed' && (
                    <button
                      type="button"
                      className={styles.pdfAction}
                      disabled={downloadingReportId === interview.id}
                      title="Download PDF report"
                      onClick={(event) => {
                        event.stopPropagation();
                        handleDownloadReport(interview);
                      }}
                    >
                      <FileDown size={16} />
                      <span>{downloadingReportId === interview.id ? 'Generating' : 'PDF report'}</span>
                    </button>
                  )}
                  <div className={styles.scoreCircle} style={{
                    background: `conic-gradient(#7C3AED ${(interview.overall_score || 0) * 3.6}deg, #E9EAF3 0deg)`,
                  }}>
                    <span>{interview.overall_score || 0}</span>
                  </div>
                </div>
              </motion.div>
            ))}
          </motion.div>

          <motion.div className={styles.recommendations} variants={itemVariants}>
            <h3>Weak topic summary</h3>
            <div className={styles.topicList}>
              {displayedWeakTopics.map((topic) => (
                <span key={topic}>{topic}</span>
              ))}
            </div>
            <button className={styles.exploreBtn} type="button" onClick={() => setActiveTab('practice')}>
              Practice these topics
            </button>
          </motion.div>
        </motion.div>}

        {activeTab === 'interviews' && (
          <motion.section
            className={styles.recentInterviews}
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            <div className={styles.sectionHeader}>
              <h3>All Interviews</h3>
              <span>{sortedInterviews.length} sessions</span>
            </div>

            {sortedInterviews.length === 0 && (
              <p className={styles.emptyState}>No interviews yet. Start one from the practice tab.</p>
            )}

            {sortedInterviews.map((interview) => (
              <motion.div
                key={interview.id}
                className={styles.interviewItem}
                variants={itemVariants}
                whileHover={{ x: 10 }}
                transition={{ duration: 0.3 }}
                onClick={() => navigate(interview.status === 'completed'
                  ? `/interview/result/${interview.id}`
                  : `/interview?interviewId=${interview.id}`)}
              >
                <div className={styles.interviewInfo}>
                  <div className={styles.interviewIcon}>
                    <BookOpen size={18} />
                  </div>
                  <div className={styles.interviewDetails}>
                    <h4>{interview.job_role || 'Interview session'}</h4>
                    <p>
                      {formatDate(interview.completed_at || interview.created_at)}
                      {' · '}
                      {interview.status}
                      {interview.job_description ? ' · job description tailored' : ''}
                    </p>
                  </div>
                </div>
                <div className={styles.interviewScore}>
                  <div className={styles.scoreCircle} style={{
                    background: `conic-gradient(#7C3AED ${(interview.overall_score || 0) * 3.6}deg, #E9EAF3 0deg)`,
                  }}>
                    <span>{interview.overall_score || 0}</span>
                  </div>
                </div>
              </motion.div>
            ))}
          </motion.section>
        )}

        {activeTab === 'reports' && (
          <motion.section
            className={styles.recentInterviews}
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            <div className={styles.sectionHeader}>
              <h3>Completed Reports</h3>
              <span>{reportInterviews.length} ready</span>
            </div>

            {reportInterviews.length === 0 && (
              <p className={styles.emptyState}>No completed reports yet. Complete an interview first.</p>
            )}

            {reportInterviews.map((interview) => {
              const report = reportByInterviewId.get(interview.id);
              return (
                <motion.div
                  key={interview.id}
                  className={styles.interviewItem}
                  variants={itemVariants}
                  whileHover={{ x: 10 }}
                  transition={{ duration: 0.3 }}
                  onClick={() => navigate(`/interview/result/${interview.id}`)}
                >
                  <div className={styles.interviewInfo}>
                    <div className={styles.interviewIcon}>
                      <BarChart3 size={18} />
                    </div>
                    <div className={styles.interviewDetails}>
                      <h4>{interview.job_role || 'Completed interview'}</h4>
                      <p>
                        {formatDate(interview.completed_at || interview.created_at)}
                        {' · '}
                        Score {report?.overall_score ?? interview.overall_score ?? 0}/100
                        {' · '}
                        {readinessLabel(report?.interview_readiness)}
                      </p>
                    </div>
                  </div>
                  <div className={styles.interviewScore}>
                    <button
                      type="button"
                      className={styles.pdfAction}
                      title="View result"
                      onClick={(event) => {
                        event.stopPropagation();
                        navigate(`/interview/result/${interview.id}`);
                      }}
                    >
                      Result
                    </button>
                    <button
                      type="button"
                      className={styles.pdfAction}
                      disabled={downloadingReportId === interview.id}
                      title="Download PDF report"
                      onClick={(event) => {
                        event.stopPropagation();
                        handleDownloadReport(interview);
                      }}
                    >
                      <FileDown size={16} />
                      <span>{downloadingReportId === interview.id ? 'Generating' : 'PDF report'}</span>
                    </button>
                    <div className={styles.scoreCircle} style={{
                      background: `conic-gradient(#7C3AED ${(report?.overall_score ?? interview.overall_score ?? 0) * 3.6}deg, #E9EAF3 0deg)`,
                    }}>
                      <span>{report?.overall_score ?? interview.overall_score ?? 0}</span>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </motion.section>
        )}
      </div>
    </div>
  );
};

export default HomePage;
