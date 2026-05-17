import React, { useEffect, useMemo, useState } from 'react';
import {
  BarChart3,
  Cpu,
  Database,
  Home,
  LogOut,
  FileText,
  Shield,
  Users,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
  AdminAccessResponse,
  AdminOverviewResponse,
  ApiError,
  api,
  formatDate,
  tokenStore,
} from '../services/api';
import { ImmersiveStage } from '../components/immersive/ImmersiveStage';
import styles from './AdminPage.module.css';

const emptyOverview: AdminOverviewResponse = {
  dashboard: {
    total_interviews: 0,
    completed_interviews: 0,
    average_score: 0,
    total_users: 0,
    today_cost_inr: 0,
  },
  costs: {
    days: 7,
    total_cost_inr: 0,
    total_tokens: 0,
    records: [],
  },
  metrics: {
    status: 'loading',
  },
  recent_users: [],
  recent_interviews: [],
  latest_reports: [],
};

const inr = (value: number | null | undefined) => `₹${(value || 0).toFixed(2)}`;

const AdminPage: React.FC = () => {
  const navigate = useNavigate();
  const [admin, setAdmin] = useState<AdminAccessResponse | null>(null);
  const [overview, setOverview] = useState<AdminOverviewResponse>(emptyOverview);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!tokenStore.get()) {
      navigate('/login');
      return;
    }

    let cancelled = false;

    const loadAdmin = async () => {
      try {
        setLoading(true);
        setError('');
        const [access, data] = await Promise.all([
          api.admin.me(),
          api.admin.overview(),
        ]);
        if (cancelled) {
          return;
        }
        setAdmin(access);
        setOverview(data);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          tokenStore.clear();
          navigate('/login');
          return;
        }
        if (err instanceof ApiError && err.status === 403) {
          navigate('/home');
          return;
        }
        setError(err instanceof ApiError ? err.message : 'Unable to load admin dashboard.');
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadAdmin();

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  const kpis = useMemo(() => [
    {
      label: 'Users',
      value: String(overview.dashboard.total_users),
      detail: 'registered accounts',
      icon: Users,
    },
    {
      label: 'Interviews',
      value: String(overview.dashboard.total_interviews),
      detail: `${overview.dashboard.completed_interviews} completed`,
      icon: BarChart3,
    },
    {
      label: 'Average Score',
      value: String(overview.dashboard.average_score || 0),
      detail: '/100 completed average',
      icon: Shield,
    },
    {
      label: 'AI Cost',
      value: inr(overview.costs.total_cost_inr || overview.dashboard.today_cost_inr),
      detail: `${overview.costs.total_tokens} tokens in ${overview.costs.days} days`,
      icon: FileText,
    },
  ], [overview]);

  const handleLogout = () => {
    tokenStore.clear();
    navigate('/login');
  };

  return (
    <div className={styles.adminPage}>
      <ImmersiveStage variant="ambient" />
      <main className={styles.shell}>
        <header className={styles.header}>
          <div>
            <span className={styles.eyebrow}>Private admin</span>
            <h1>intervue.ai control room</h1>
            <p>{admin?.email || 'Admin verification required'}</p>
          </div>
          <div className={styles.headerActions}>
            <button type="button" onClick={() => navigate('/home')}>
              <Home size={18} />
              Home
            </button>
            <button type="button" className={styles.logoutButton} onClick={handleLogout}>
              <LogOut size={18} />
              Log out
            </button>
          </div>
        </header>

        {loading && <div className={styles.notice}>Loading admin dashboard...</div>}
        {error && <div className={styles.error}>{error}</div>}

        {!loading && !error && (
          <>
            <section className={styles.kpiGrid}>
              {kpis.map((item) => {
                const Icon = item.icon;
                return (
                  <article className={styles.kpiCard} key={item.label}>
                    <div className={styles.kpiIcon}>
                      <Icon size={20} />
                    </div>
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                    <small>{item.detail}</small>
                  </article>
                );
              })}
            </section>

            <section className={styles.healthGrid}>
              <article className={styles.panel}>
                <div className={styles.panelHeader}>
                  <Database size={20} />
                  <h2>Database</h2>
                </div>
                <div className={styles.healthRows}>
                  <span>Supabase <strong>{overview.metrics.database?.supabase || 'unknown'}</strong></span>
                  <span>Redis <strong>{overview.metrics.database?.redis || (overview.metrics.redis_connected ? 'ok' : 'unknown')}</strong></span>
                  <span>Redis memory <strong>{overview.metrics.redis_memory || 'unknown'}</strong></span>
                </div>
              </article>

              <article className={styles.panel}>
                <div className={styles.panelHeader}>
                  <Cpu size={20} />
                  <h2>Cost Activity</h2>
                </div>
                <div className={styles.healthRows}>
                  <span>Recent calls <strong>{overview.costs.records.length}</strong></span>
                  <span>Total tokens <strong>{overview.costs.total_tokens}</strong></span>
                  <span>Total cost <strong>{inr(overview.costs.total_cost_inr)}</strong></span>
                </div>
              </article>
            </section>

            <section className={styles.tableGrid}>
              <article className={styles.panel}>
                <div className={styles.panelHeader}>
                  <Users size={20} />
                  <h2>Recent Users</h2>
                </div>
                <div className={styles.tableWrap}>
                  <table>
                    <thead>
                      <tr>
                        <th>Email</th>
                        <th>Plan</th>
                        <th>Difficulty</th>
                        <th>Joined</th>
                      </tr>
                    </thead>
                    <tbody>
                      {overview.recent_users.map((user) => (
                        <tr key={user.id}>
                          <td>{user.email}</td>
                          <td>{user.plan || 'free'}</td>
                          <td>{user.difficulty_profile || 'beginner'}</td>
                          <td>{formatDate(user.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>

              <article className={styles.panel}>
                <div className={styles.panelHeader}>
                  <BarChart3 size={20} />
                  <h2>Recent Interviews</h2>
                </div>
                <div className={styles.tableWrap}>
                  <table>
                    <thead>
                      <tr>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Score</th>
                        <th>Tokens</th>
                        <th>Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {overview.recent_interviews.map((interview) => (
                        <tr key={interview.id}>
                          <td>{interview.job_role || 'General'}</td>
                          <td>{interview.status}</td>
                          <td>{interview.overall_score ?? 0}</td>
                          <td>{interview.total_tokens || 0}</td>
                          <td>{formatDate(interview.completed_at || interview.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
            </section>

            <section className={styles.tableGrid}>
              <article className={styles.panel}>
                <div className={styles.panelHeader}>
                  <Shield size={20} />
                  <h2>Latest Reports</h2>
                </div>
                <div className={styles.reportList}>
                  {overview.latest_reports.map((report) => (
                    <div key={report.id} className={styles.reportItem}>
                      <strong>{report.grade || 'N/A'} / {report.overall_score ?? 0}</strong>
                      <span>{report.interview_readiness?.replace(/_/g, ' ') || 'readiness pending'}</span>
                      <small>{(report.next_session_focus || []).slice(0, 3).join(', ') || 'No focus saved'}</small>
                    </div>
                  ))}
                </div>
              </article>

              <article className={styles.panel}>
                <div className={styles.panelHeader}>
                  <FileText size={20} />
                  <h2>Recent AI Calls</h2>
                </div>
                <div className={styles.tableWrap}>
                  <table>
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Model</th>
                        <th>Cost</th>
                        <th>Latency</th>
                      </tr>
                    </thead>
                    <tbody>
                      {overview.costs.records.slice(0, 12).map((record, index) => (
                        <tr key={`${record.created_at}-${record.call_type}-${index}`}>
                          <td>{record.call_type.replace(/_/g, ' ')}</td>
                          <td>{record.model}</td>
                          <td>{inr(record.cost_inr)}</td>
                          <td>{record.latency_ms ?? 0}ms</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
            </section>
          </>
        )}
      </main>
    </div>
  );
};

export default AdminPage;
