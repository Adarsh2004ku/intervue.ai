import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Bell, Settings, LogOut, Search, Home, BookOpen, FileText, BarChart3, Bookmark } from 'lucide-react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useNavigate } from 'react-router-dom';
import {
  ApiError,
  CostsResponse,
  DashboardResponse,
  InterviewMode,
  MetricsResponse,
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

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse>(emptyDashboard);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [costs, setCosts] = useState<CostsResponse | null>(null);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [interviewHealth, setInterviewHealth] = useState<{ status: string; service: string } | null>(null);
  const [selectedResumeId, setSelectedResumeId] = useState('');
  const [jobRole, setJobRole] = useState('Frontend Developer');
  const [jobDescription, setJobDescription] = useState('');
  const [interviewMode, setInterviewMode] = useState<InterviewMode>('faang');
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [activeTab, setActiveTab] = useState<'overview' | 'interviews' | 'resumes' | 'reports' | 'practice'>('overview');

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
        const [adminResult, resumeResult, costsResult, metricsResult, healthResult, historyResult] = await Promise.allSettled([
          api.admin.dashboard(),
          api.resume.list(),
          api.admin.costs(7),
          api.admin.metrics(),
          api.interview.health(),
          api.interview.history(),
        ]);

        const adminData = adminResult.status === 'fulfilled'
          ? adminResult.value
          : {
              total_interviews: localInterviews.length,
              completed_interviews: localInterviews.filter((item) => item.status === 'completed').length,
              average_score: 0,
              total_users: 0,
              today_cost_inr: 0,
            };
        const resumeData = resumeResult.status === 'fulfilled'
          ? resumeResult.value
          : { resumes: [] };
        const costsData = costsResult.status === 'fulfilled'
          ? costsResult.value
          : null;
        const metricsData = metricsResult.status === 'fulfilled'
          ? metricsResult.value
          : null;
        const healthData = healthResult.status === 'fulfilled'
          ? healthResult.value
          : null;
        const interviewData = historyResult.status === 'fulfilled'
          ? historyResult.value.interviews
          : localInterviews;
        const dashboardData = normalizeDashboard(adminData, resumeData.resumes, interviewData);

        setProfile(me);
        setDashboard(dashboardData);
        setResumes(resumeData.resumes);
        setCosts(costsData);
        setMetrics(metricsData);
        setInterviewHealth(healthData);
        setSelectedResumeId(resumeData.resumes[0]?.id || dashboardData.resumes[0]?.id || '');
        if (
          adminResult.status === 'rejected'
          || resumeResult.status === 'rejected'
          || costsResult.status === 'rejected'
          || metricsResult.status === 'rejected'
          || healthResult.status === 'rejected'
          || historyResult.status === 'rejected'
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

  const chartData = dashboard.score_trend.length
    ? dashboard.score_trend
    : [{ name: 'No scores yet', score: 0 }];

  const barData = dashboard.activities.length
    ? dashboard.activities
    : [{ name: 'No activity yet', value: 0 }];

  const statCards = useMemo(() => [
    {
      label: 'Overall Readiness',
      value: `${dashboard.stats.overall_readiness || 0}%`,
      status: dashboard.stats.completed_interviews ? 'Based on completed interviews' : 'No completed interviews yet',
      trend: `${dashboard.stats.completed_interviews} completed`,
      color: '#10b981',
    },
    {
      label: 'Interviews Taken',
      value: String(dashboard.stats.total_interviews),
      status: 'All sessions',
      trend: `${dashboard.stats.resume_count} resumes uploaded`,
      color: '#6366f1',
    },
    {
      label: 'Average Score',
      value: String(dashboard.stats.average_score || 0),
      status: '/100',
      trend: dashboard.stats.average_score >= 75 ? 'Strong progress' : 'Keep practicing',
      color: '#f59e0b',
    },
    {
      label: 'AI Spend',
      value: `₹${(costs?.total_cost_inr ?? costs?.records.reduce((total, item) => total + (item.cost_inr || 0), 0) ?? 0).toFixed(2)}`,
      status: 'Last 7 days',
      trend: `${costs?.records.length || 0} calls · ${costs?.total_tokens || 0} tokens`,
      color: '#ec4899',
    },
    {
      label: 'API Health',
      value: interviewHealth?.status || metrics?.status || 'Checking',
      status: interviewHealth?.service ? `${interviewHealth.service} route connected` : 'Interview route pending',
      trend: metrics?.redis_connected
        ? `Redis ${metrics.redis_memory || 'connected'}`
        : metrics?.redis_error || 'Redis unavailable',
      color: '#0891b2',
    },
  ], [costs, dashboard, interviewHealth, metrics]);

  const handleLogout = () => {
    tokenStore.clear();
    navigate('/login');
  };

  const syncResumeDashboard = (nextResumes: Resume[]) => {
    setDashboard((current) => ({
      ...current,
      stats: {
        ...current.stats,
        resume_count: nextResumes.length,
      },
      activities: [
        ...current.activities.filter((item) => item.name !== 'Resumes'),
        { name: 'Resumes', value: nextResumes.length },
      ],
      resumes: nextResumes,
    }));
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
      syncResumeDashboard(freshResumes.resumes);
      setSelectedResumeId(result.resume_id);
      setStatus(result.message);
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
      syncResumeDashboard(freshResumes.resumes);
      setSelectedResumeId(freshResumes.resumes[0]?.id || '');
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
      const startedInterview: DashboardResponse['recent_interviews'][number] = {
        id: started.interview_id,
        resume_id: started.resume_id,
        job_role: started.job_role,
        interview_mode: started.interview_mode,
        status: 'in_progress',
        overall_score: null,
        created_at: started.created_at,
        completed_at: null,
      };
      interviewHistoryStore().upsert(startedInterview);
      setDashboard((current) => ({
        ...current,
        stats: {
          ...current.stats,
          total_interviews: Math.max(current.stats.total_interviews, current.recent_interviews.length + 1),
        },
        recent_interviews: [
          startedInterview,
          ...current.recent_interviews.filter((item) => item.id !== startedInterview.id),
        ].slice(0, 12),
      }));
      navigate(`/interview?interviewId=${started.interview_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to start interview.');
    } finally {
      setStarting(false);
    }
  };

  const handleDownloadReport = async (interviewId: string) => {
    try {
      setError('');
      setStatus('Preparing report download...');
      const blob = await api.report.downloadPdf(interviewId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `intervue-report-${interviewId.slice(0, 8)}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
      setStatus('Report downloaded.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Report is not ready yet.');
    }
  };

  const navItems = [
    { id: 'overview', label: 'Home', icon: Home },
    { id: 'interviews', label: 'Interviews', icon: BookOpen },
    { id: 'resumes', label: 'Resumes', icon: FileText },
    { id: 'reports', label: 'Reports', icon: BarChart3 },
    { id: 'practice', label: 'Practice', icon: Bookmark },
  ] as const;

  const tabCopy = {
    overview: {
      title: 'Dashboard',
      description: 'Your interview activity, readiness, and next best action.',
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
      description: 'Download reports for completed interviews when a backend report is available.',
    },
    practice: {
      title: 'Practice',
      description: 'Choose a resume, role, and interview style to start a realtime session.',
    },
  }[activeTab];

  const selectedResume = resumes.find((resume) => resume.id === selectedResumeId);
  const reportInterviews = dashboard.recent_interviews.filter((interview) => interview.status === 'completed');
  const displayedInterviews = activeTab === 'reports' ? reportInterviews : dashboard.recent_interviews;

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
                  onClick={() => setActiveTab(item.id)}
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
            <motion.button className={styles.iconBtn} whileHover={{ scale: 1.1 }} onClick={() => setActiveTab('practice')}>
              <Settings size={20} />
            </motion.button>
            <motion.div className={styles.userProfile} whileHover={{ scale: 1.05 }}>
              <div className={styles.avatar}>{profile?.full_name?.[0]?.toUpperCase() || '👤'}</div>
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

        {(activeTab === 'overview' || activeTab === 'practice') && <motion.div
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

        {(activeTab === 'overview' || activeTab === 'resumes' || activeTab === 'practice') && <motion.section
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

          <motion.form className={styles.launchCard} variants={itemVariants} onSubmit={handleStartInterview}>
            <div className={styles.sectionHeader}>
              <h3>Start Interview</h3>
            </div>
            <div className={styles.formRow}>
              <input value={jobRole} onChange={(event) => setJobRole(event.target.value)} placeholder="Job role" />
              <select value={interviewMode} onChange={(event) => setInterviewMode(event.target.value as InterviewMode)}>
                <option value="faang">FAANG</option>
                <option value="startup">Startup</option>
                <option value="hr">HR</option>
              </select>
              <button type="submit" disabled={starting || !selectedResumeId}>
                {starting ? 'Starting...' : 'Start'}
              </button>
            </div>
            <textarea
              value={jobDescription}
              onChange={(event) => setJobDescription(event.target.value)}
              placeholder="Paste the job description or key requirements for more targeted questions"
              rows={5}
            />
          </motion.form>
        </motion.section>}

        {activeTab === 'resumes' && (
          <section className={styles.resumePanel}>
            <div className={styles.sectionHeader}>
              <h3>Saved Resumes</h3>
              <span>{resumes.length} uploaded</span>
            </div>

            {resumes.length === 0 && (
              <p className={styles.emptyState}>No resumes saved yet. Upload a PDF or DOCX above and it will be stored in Supabase.</p>
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
          className={styles.chartsSection}
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
        >
          <motion.div className={styles.chart} variants={itemVariants}>
            <h3>Score Trend</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', color: '#fff' }} />
                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="#6366f1"
                  strokeWidth={3}
                  dot={{ fill: '#6366f1', r: 5 }}
                  activeDot={{ r: 7 }}
                  animationDuration={1000}
                />
              </LineChart>
            </ResponsiveContainer>
          </motion.div>

          <motion.div className={styles.chart} variants={itemVariants}>
            <h3>Practice Activities</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', color: '#fff' }} />
                <Bar
                  dataKey="value"
                  fill="#8b5cf6"
                  radius={[8, 8, 0, 0]}
                  animationDuration={1000}
                />
              </BarChart>
            </ResponsiveContainer>
          </motion.div>
        </motion.div>}

        {(activeTab === 'overview' || activeTab === 'interviews' || activeTab === 'reports') && <motion.div
          className={styles.bottomSection}
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
        >
          <motion.div className={styles.recentInterviews} variants={itemVariants}>
            <div className={styles.sectionHeader}>
              <h3>{activeTab === 'reports' ? 'Completed Reports' : 'Recent Interviews'}</h3>
              <button className={styles.linkButton} type="button" onClick={() => setActiveTab('interviews')}>View all</button>
            </div>

            {displayedInterviews.length === 0 && (
              <p className={styles.emptyState}>
                {activeTab === 'reports'
                  ? 'No completed reports yet. Complete an interview first.'
                  : 'No interviews yet. Start one from the practice tab.'}
              </p>
            )}

            {displayedInterviews.map((interview) => (
              <motion.div
                key={interview.id}
                className={styles.interviewItem}
                whileHover={{ x: 10 }}
                transition={{ duration: 0.3 }}
                onClick={() => navigate(`/interview?interviewId=${interview.id}`)}
              >
                <div className={styles.interviewInfo}>
                  <div className={styles.interviewIcon}>
                    <span>🎬</span>
                  </div>
                  <div className={styles.interviewDetails}>
                    <h4>{interview.job_role}</h4>
                    <p>{formatDate(interview.completed_at || interview.created_at)} · {interview.status}</p>
                  </div>
                </div>
                <div className={styles.interviewScore}>
                  {activeTab === 'reports' && (
                    <button
                      type="button"
                      className={styles.smallAction}
                      onClick={(event) => {
                        event.stopPropagation();
                        handleDownloadReport(interview.id);
                      }}
                    >
                      PDF
                    </button>
                  )}
                  <div className={styles.scoreCircle} style={{
                    background: `conic-gradient(#6366f1 ${(interview.overall_score || 0) * 3.6}deg, #e2e8f0 0deg)`,
                  }}>
                    <span>{interview.overall_score || 0}</span>
                  </div>
                </div>
              </motion.div>
            ))}
          </motion.div>

          <motion.div className={styles.recommendations} variants={itemVariants}>
            <h3>Recommended for you</h3>
            <motion.div
              className={styles.recommendationList}
              variants={containerVariants}
              initial="hidden"
              animate="visible"
            >
              {dashboard.recommendations.map((rec, index) => (
                <motion.div
                  key={`${rec.title}-${index}`}
                  className={styles.recommendationCard}
                  variants={itemVariants}
                  whileHover={{ scale: 1.05 }}
                  style={{ borderLeftColor: ['#6366f1', '#8b5cf6', '#ec4899'][index % 3] }}
                >
                  <span className={styles.recIcon}>{['🎯', '🗣️', '💻'][index % 3]}</span>
                  <h4>{rec.title}</h4>
                  <p>{rec.description}</p>
                  <motion.button
                    className={styles.exploreBtn}
                    whileHover={{ x: 5 }}
                    onClick={() => setActiveTab('practice')}
                  >
                    Practice →
                  </motion.button>
                </motion.div>
              ))}
            </motion.div>
          </motion.div>
        </motion.div>}
      </div>
    </div>
  );
};

export default HomePage;
