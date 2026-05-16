import React, { useEffect, useMemo, useState } from 'react';
import { Bell, LogOut, Search, Home, BookOpen, FileText, BarChart3, Bookmark, FileDown } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { LineTrendChart } from '../components/charts/SimpleCharts';
import { ImmersiveStage } from '../components/immersive/ImmersiveStage';
import { motion } from '../components/ui/staticMotion';
import {
  ApiError,
  CostsResponse,
  DashboardResponse,
  InterviewMode,
  InterviewRecord,
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
        const [adminResult, resumeResult, interviewResult, costsResult] = await Promise.allSettled([
          api.admin.dashboard(),
          api.resume.list(),
          api.interview.list(),
          api.admin.costs(7),
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
        const recentInterviews = interviewResult.status === 'fulfilled'
          ? interviewResult.value.interviews
          : localInterviews;
        const costsData = costsResult.status === 'fulfilled'
          ? costsResult.value
          : null;
        const dashboardData = normalizeDashboard(adminData, resumeData.resumes, recentInterviews);

        setProfile(me);
        setDashboard(dashboardData);
        setResumes(resumeData.resumes);
        setCosts(costsData);
        setSelectedResumeId(resumeData.resumes[0]?.id || dashboardData.resumes[0]?.id || '');
        if (
          adminResult.status === 'rejected'
          || resumeResult.status === 'rejected'
          || interviewResult.status === 'rejected'
          || costsResult.status === 'rejected'
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

  const statCards = useMemo(() => [
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
    {
      label: 'Average Score',
      value: String(dashboard.stats.average_score || 0),
      status: '/100',
      trend: dashboard.stats.average_score >= 75 ? 'Strong progress' : 'Keep practicing',
      color: '#7C3AED',
    },
    {
      label: 'AI Spend',
      value: `₹${(costs?.total_cost_inr ?? costs?.records.reduce((total, item) => total + (item.cost_inr || 0), 0) ?? 0).toFixed(2)}`,
      status: 'Last 7 days',
      trend: `${costs?.records.length || 0} calls · ${costs?.total_tokens || 0} tokens`,
      color: '#8B5CF6',
    },
  ], [costs, dashboard]);

  const handleLogout = () => {
    tokenStore.clear();
    navigate('/login');
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
      description: 'Download reports for completed interviews when a backend report is available.',
    },
    practice: {
      title: 'Practice',
      description: 'Choose a resume, role, and interview style to start a realtime session.',
    },
  }[activeTab];

  const selectedResume = resumes.find((resume) => resume.id === selectedResumeId);
  const reportInterviews = dashboard.recent_interviews.filter((interview) => interview.status === 'completed');

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
          className={styles.chartsSection}
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
        >
          <motion.div className={styles.chart} variants={itemVariants}>
            <h3>Score Trend</h3>
            <LineTrendChart data={chartData} />
          </motion.div>
        </motion.div>}

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

            {dashboard.recent_interviews.length === 0 && (
              <p className={styles.emptyState}>No interviews yet. Start one from the practice tab.</p>
            )}

            {dashboard.recent_interviews.map((interview) => (
              <motion.div
                key={interview.id}
                className={styles.interviewItem}
                whileHover={{ x: 10 }}
                transition={{ duration: 0.3 }}
                onClick={() => navigate(`/interview?interviewId=${interview.id}`)}
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
                  style={{ borderLeftColor: ['#7C3AED', '#8B5CF6', '#DDD6FE'][index % 3] }}
                >
                  <span className={styles.recIcon}>{String(index + 1).padStart(2, '0')}</span>
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

        {activeTab === 'interviews' && (
          <motion.section
            className={styles.recentInterviews}
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            <div className={styles.sectionHeader}>
              <h3>All Interviews</h3>
              <span>{dashboard.recent_interviews.length} sessions</span>
            </div>

            {dashboard.recent_interviews.length === 0 && (
              <p className={styles.emptyState}>No interviews yet. Start one from the practice tab.</p>
            )}

            {dashboard.recent_interviews.map((interview) => (
              <motion.div
                key={interview.id}
                className={styles.interviewItem}
                variants={itemVariants}
                whileHover={{ x: 10 }}
                transition={{ duration: 0.3 }}
                onClick={() => navigate(`/interview?interviewId=${interview.id}`)}
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

            {reportInterviews.map((interview) => (
              <motion.div
                key={interview.id}
                className={styles.interviewItem}
                variants={itemVariants}
                whileHover={{ x: 10 }}
                transition={{ duration: 0.3 }}
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
                      Score {interview.overall_score || 0}/100
                      {interview.job_description ? ' · job description tailored' : ''}
                    </p>
                  </div>
                </div>
                <div className={styles.interviewScore}>
                  <button
                    type="button"
                    className={styles.pdfAction}
                    disabled={downloadingReportId === interview.id}
                    title="Download PDF report"
                    onClick={() => handleDownloadReport(interview)}
                  >
                    <FileDown size={16} />
                    <span>{downloadingReportId === interview.id ? 'Generating' : 'PDF report'}</span>
                  </button>
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
      </div>
    </div>
  );
};

export default HomePage;
