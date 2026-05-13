const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
const WS_BASE_URL = (import.meta.env.VITE_WS_BASE_URL || '').replace(/\/$/, '');
const TOKEN_KEY = 'intervue_access_token';

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
};

export type UserProfile = {
  id: string;
  email: string;
  full_name?: string;
  plan?: string;
  difficulty_profile?: string;
};

export type ParsedResume = {
  name?: string;
  email?: string;
  phone?: string;
  skills?: string[];
  experience?: string[];
  education?: string[];
  projects?: string[];
  summary?: string;
};

export type Resume = {
  id: string;
  file_name?: string;
  parsed_json?: ParsedResume;
  raw_text?: string;
  created_at?: string;
};

export type ResumeUploadResponse = {
  resume_id: string;
  parsed: ParsedResume;
  chunks_stored: number;
  message: string;
};

export type InterviewMode = 'faang' | 'startup' | 'hr';

export type InterviewRecord = {
  id: string;
  resume_id?: string;
  job_role?: string;
  interview_mode: InterviewMode;
  status: 'in_progress' | 'completed' | 'aborted';
  overall_score?: number | null;
  created_at?: string;
  completed_at?: string | null;
};

export type InterviewQuestion = {
  id?: string;
  text?: string;
  category?: string;
  topic?: string;
  difficulty?: string;
  why_asked?: string;
  is_weakness_focused?: boolean;
  order_idx?: number;
};

export type StartInterviewResponse = {
  success: boolean;
  interview_id: string;
  first_question: InterviewQuestion;
  persona_name: string;
  opening_line: string;
  job_role: string;
  interview_mode: InterviewMode;
  resume_id?: string;
  created_at: string;
};

export type DashboardResponse = {
  stats: {
    total_interviews: number;
    completed_interviews: number;
    average_score: number;
    overall_readiness: number;
    weakest_topic: string;
    resume_count: number;
  };
  score_trend: Array<{ name: string; score: number }>;
  activities: Array<{ name: string; value: number }>;
  recent_interviews: InterviewRecord[];
  recommendations: Array<{ title: string; description: string }>;
  resumes: Resume[];
};

export type InterviewStatusResponse = {
  interview: InterviewRecord;
  questions: InterviewQuestion[];
};

export type Report = {
  id: string;
  interview_id: string;
  overall_score?: number;
  grade?: string;
  interview_readiness?: string;
  feedback_json?: Record<string, unknown>;
  improvement_plan?: unknown[];
  speech_summary?: Record<string, unknown>;
  strengths?: string[];
  next_session_focus?: string[];
  created_at?: string;
};

export type AdminDashboardResponse = {
  total_interviews: number;
  completed_interviews: number;
  average_score: number;
  total_users: number;
  today_cost_inr: number;
};

export type CostRecord = {
  interview_id?: string | null;
  model: string;
  call_type: string;
  cost_inr: number;
  tokens_in: number;
  tokens_out: number;
  latency_ms?: number | null;
  created_at?: string;
};

export type CostSummary = {
  interview_id?: string;
  total_cost_inr: number;
  total_tokens: number;
  calls: number;
  by_call_type: Record<string, number>;
  records?: CostRecord[];
};

export type CostsResponse = {
  days: number;
  total_cost_inr: number;
  total_tokens: number;
  records: CostRecord[];
};

export type MetricsResponse = {
  status: string;
  redis_connected?: boolean;
  redis_memory?: string;
  redis_error?: string;
};

export type AudioEvaluation = {
  transcript: string;
  score: number;
  accuracy_score: number;
  clarity_score: number;
  depth_score: number;
  confidence_score: number;
  communication_score: number;
  reasoning: string;
  provider?: string;
  model?: string;
};

export type AnalyzeAudioResponse = {
  success: boolean;
  evaluation?: AudioEvaluation;
  cost?: CostRecord | null;
  session_cost?: CostSummary;
  error?: string;
};

export type BehaviorAnalysis = {
  engagement_score: number;
  confidence_score: number;
  nervousness_score: number;
  professionalism_score: number;
  eye_contact: boolean;
  looking_away: boolean;
  distracted: boolean;
  expression: string;
  emotion: string;
  posture: string;
  confidence_level: string;
  notes: string;
};

export type BehaviorSummary = {
  overall_engagement: number;
  overall_confidence: number;
  overall_professionalism: number;
  overall_nervousness: number;
  eye_contact_ratio: number;
  distraction_ratio: number;
  dominant_emotion: string;
  behavior_summary: string;
};

export type AnalyzeFrameResponse = {
  success: boolean;
  analysis?: BehaviorAnalysis;
  cost?: CostRecord | null;
  session_cost?: CostSummary;
  error?: string;
};

export type BehaviorSummaryResponse = {
  success: boolean;
  summary?: BehaviorSummary;
  error?: string;
};

type StartInterviewRouteResponse = {
  success: boolean;
  interview_id: string;
  created_at: string;
};

type GoogleAuthResponse = {
  url: string;
};

export type CompleteInterviewResponse = {
  success: boolean;
  interview_id: string;
  session_cost: CostSummary;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

const authHeaders = (): Record<string, string> => {
  const token = tokenStore.get();
  return token ? { Authorization: `Bearer ${token}` } : {};
};

async function parseError(response: Response) {
  try {
    const data = await response.json();
    if (typeof data?.detail === 'string') {
      return data.detail;
    }
    if (Array.isArray(data?.detail)) {
      return data.detail
        .map((item: { msg?: string; message?: string }) => item.msg || item.message)
        .filter(Boolean)
        .join(', ');
    }
    return data?.message || response.statusText;
  } catch {
    return response.statusText;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isFormData = init.body instanceof FormData;
  const headers = new Headers(init.headers);

  Object.entries(authHeaders()).forEach(([key, value]) => headers.set(key, value));
  if (!isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
    });
  } catch {
    throw new ApiError('Backend is not reachable. Make sure the API server is running on port 8000.', 0);
  }

  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

const buildWsUrl = (path: string) => {
  if (WS_BASE_URL) {
    return `${WS_BASE_URL}${path}`;
  }

  const apiUrl = new URL(API_BASE_URL, window.location.origin);
  apiUrl.protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  apiUrl.pathname = `${apiUrl.pathname.replace(/\/$/, '')}${path}`;
  apiUrl.search = '';
  return apiUrl.toString();
};

const interviewRouteBase = '/interview/interview';

const personaByMode: Record<InterviewMode, { name: string; openingLine: string; starter: string }> = {
  faang: {
    name: 'Alex (FAANG Interviewer)',
    openingLine: "Hi, I'm Alex. Today we'll go deep on your technical skills. Let's begin.",
    starter: 'Walk me through one technically challenging project from your resume. What trade-offs did you make, and how did you validate the result?',
  },
  startup: {
    name: 'Priya (Startup Founder)',
    openingLine: "Hey! I'm Priya. Tell me about something you built and shipped. I want to hear the real story.",
    starter: 'Tell me about a product or feature you shipped under constraints. What did you prioritize, and what would you improve now?',
  },
  hr: {
    name: 'Riya (HR Manager)',
    openingLine: "Hello! I'm Riya, and I'm excited to learn more about you today. Let's get started.",
    starter: 'Tell me about yourself and a recent experience that shows how you work with a team.',
  },
};

export const interviewQuestionBank: Record<InterviewMode, string[]> = {
  faang: [
    personaByMode.faang.starter,
    'Describe a difficult bug or performance issue you solved. How did you isolate the root cause?',
    'Pick a system you have built. How would you scale it if usage increased by 10x?',
    'Tell me about an edge case you almost missed and how you handled it.',
  ],
  startup: [
    personaByMode.startup.starter,
    'Tell me about a time you had to move fast with incomplete information. What did you do?',
    'What is one product decision you influenced, and how did you measure whether it worked?',
    'Describe a moment when you took ownership beyond your assigned role.',
  ],
  hr: [
    personaByMode.hr.starter,
    'Tell me about a time you handled conflict with a teammate or stakeholder.',
    'Describe a failure or setback. What did you learn, and what changed afterward?',
    'What kind of work environment helps you do your best work?',
  ],
};

const createQuestion = (
  mode: InterviewMode,
  jobRole: string,
  orderIdx = 0,
): InterviewQuestion => ({
  text: interviewQuestionBank[mode][orderIdx % interviewQuestionBank[mode].length],
  category: mode === 'hr' ? 'Behavioral' : 'Interview',
  topic: jobRole || 'General',
  difficulty: orderIdx === 0 ? 'warmup' : 'adaptive',
  why_asked: 'This frontend question is sent to the backend audio evaluator for scoring.',
  order_idx: orderIdx,
});

export function createLocalQuestion(mode: InterviewMode, jobRole: string, orderIdx: number) {
  return createQuestion(mode, jobRole, orderIdx);
}

export function normalizeDashboard(
  admin: AdminDashboardResponse,
  resumes: Resume[] = [],
  recentInterviews: InterviewRecord[] = [],
): DashboardResponse {
  const average = admin.average_score || 0;

  return {
    stats: {
      total_interviews: admin.total_interviews || recentInterviews.length,
      completed_interviews: admin.completed_interviews || recentInterviews.filter((item) => item.status === 'completed').length,
      average_score: average,
      overall_readiness: Math.round(average),
      weakest_topic: recentInterviews.length ? 'Review recent answer feedback' : 'Start with a mock interview',
      resume_count: resumes.length,
    },
    score_trend: recentInterviews
      .filter((item) => typeof item.overall_score === 'number')
      .slice(-6)
      .map((item, index) => ({
        name: item.created_at ? formatDate(item.created_at) : `Session ${index + 1}`,
        score: item.overall_score || 0,
      })),
    activities: [
      { name: 'Users', value: admin.total_users || 0 },
      { name: 'Resumes', value: resumes.length },
      { name: 'Completed', value: admin.completed_interviews || 0 },
    ],
    recent_interviews: recentInterviews,
    recommendations: [
      { title: 'Upload a resume', description: 'Personalize the practice flow with parsed resume data.' },
      { title: 'Record an answer', description: 'Send audio to the backend evaluator and review the transcript.' },
      { title: 'Check camera behavior', description: 'Let the backend summarize eye contact and engagement.' },
    ],
    resumes,
  };
}

const healthUrl = () => {
  const apiUrl = new URL(API_BASE_URL, window.location.origin);
  const path = apiUrl.pathname.replace(/\/$/, '');
  if (path.endsWith('/api/v1')) {
    apiUrl.pathname = `${path}/health`;
  } else {
    apiUrl.pathname = '/health';
  }
  apiUrl.search = '';
  return apiUrl.toString();
};

export const api = {
  health: () => fetch(healthUrl()).then((response) => response.ok),
  auth: {
    login: (email: string, password: string) =>
      request<TokenResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    signup: (email: string, password: string, full_name: string) =>
      request<TokenResponse>('/auth/signup', {
        method: 'POST',
        body: JSON.stringify({ email, password, full_name }),
      }),
    supabaseSession: (access_token: string) =>
      request<TokenResponse>('/auth/supabase-session', {
        method: 'POST',
        body: JSON.stringify({ access_token }),
      }),
    google: () => request<GoogleAuthResponse>('/auth/google'),
    me: () => request<UserProfile>('/auth/me'),
  },
  resume: {
    list: () => request<{ resumes: Resume[] }>('/resume'),
    upload: (file: File) => {
      const body = new FormData();
      body.append('file', file);
      return request<ResumeUploadResponse>('/resume/upload', {
        method: 'POST',
        body,
      });
    },
    get: (resumeId: string) => request<Resume>(`/resume/${resumeId}`),
    delete: (resumeId: string) =>
      request<{ message: string }>(`/resume/${resumeId}`, {
        method: 'DELETE',
      }),
  },
  interview: {
    health: () => request<{ status: string; service: string }>(`${interviewRouteBase}/health`),
    start: async (resume_id: string, job_role: string, interview_mode: InterviewMode) => {
      const result = await request<StartInterviewRouteResponse>(`${interviewRouteBase}/start`, {
        method: 'POST',
        body: JSON.stringify({ resume_id, job_role, interview_mode }),
      });
      const persona = personaByMode[interview_mode];

      return {
        ...result,
        first_question: createQuestion(interview_mode, job_role),
        persona_name: persona.name,
        opening_line: persona.openingLine,
        job_role,
        interview_mode,
        resume_id,
        created_at: result.created_at || new Date().toISOString(),
      } satisfies StartInterviewResponse;
    },
    analyzeFrame: (interviewId: string, file: Blob) => {
      const body = new FormData();
      body.append('interview_id', interviewId);
      body.append('file', file, 'frame.jpg');
      return request<AnalyzeFrameResponse>(`${interviewRouteBase}/analyze-frame`, {
        method: 'POST',
        body,
      });
    },
    analyzeAudio: (interviewId: string, question: string, file: Blob, durationSec?: number) => {
      const body = new FormData();
      body.append('interview_id', interviewId);
      body.append('question', question);
      if (typeof durationSec === 'number') {
        body.append('duration_sec', String(durationSec));
      }
      body.append('file', file, 'answer.webm');
      return request<AnalyzeAudioResponse>(`${interviewRouteBase}/analyze-audio`, {
        method: 'POST',
        body,
      });
    },
    behaviorSummary: (interviewId: string) =>
      request<BehaviorSummaryResponse>(`${interviewRouteBase}/behavior-summary/${interviewId}`),
    complete: (interviewId: string, overall_score?: number | null, behavior_summary?: BehaviorSummary | null) =>
      request<CompleteInterviewResponse>(`${interviewRouteBase}/${interviewId}/complete`, {
        method: 'POST',
        body: JSON.stringify({
          overall_score: typeof overall_score === 'number' ? overall_score : null,
          behavior_summary: behavior_summary || null,
        }),
      }),
    socketUrl: (interviewId: string) => buildWsUrl(`${interviewRouteBase}/ws/interview/${interviewId}`),
  },
  report: {
    get: (interviewId: string) => request<Report>(`/report/${interviewId}`),
    pdfUrl: (interviewId: string) => `${API_BASE_URL}/report/${interviewId}/pdf`,
    downloadPdf: async (interviewId: string) => {
      const response = await fetch(`${API_BASE_URL}/report/${interviewId}/pdf`, {
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new ApiError(await parseError(response), response.status);
      }
      return response.blob();
    },
  },
  admin: {
    dashboard: () => request<AdminDashboardResponse>('/admin/dashboard'),
    costs: (days = 7) => request<CostsResponse>(`/admin/costs?days=${days}`),
    metrics: () => request<MetricsResponse>('/admin/metrics'),
  },
};

export function formatDate(value?: string | null) {
  if (!value) {
    return 'Not available';
  }

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(value));
}

export function activeInterviewStore() {
  const key = 'intervue_active_interview';

  return {
    get: (): StartInterviewResponse | null => {
      const raw = sessionStorage.getItem(key);
      return raw ? JSON.parse(raw) as StartInterviewResponse : null;
    },
    set: (value: StartInterviewResponse) => sessionStorage.setItem(key, JSON.stringify(value)),
    update: (patch: Partial<StartInterviewResponse>) => {
      const raw = sessionStorage.getItem(key);
      const current = raw ? JSON.parse(raw) as StartInterviewResponse : null;
      if (current) {
        sessionStorage.setItem(key, JSON.stringify({ ...current, ...patch }));
      }
    },
    clear: () => sessionStorage.removeItem(key),
  };
}

export function interviewHistoryStore() {
  const key = 'intervue_browser_interviews';

  return {
    list: (): InterviewRecord[] => {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) as InterviewRecord[] : [];
    },
    upsert: (value: InterviewRecord) => {
      const current = interviewHistoryStore().list();
      const next = [value, ...current.filter((item) => item.id !== value.id)].slice(0, 12);
      localStorage.setItem(key, JSON.stringify(next));
    },
    update: (interviewId: string, patch: Partial<InterviewRecord>) => {
      const next = interviewHistoryStore().list().map((item) =>
        item.id === interviewId ? { ...item, ...patch } : item,
      );
      localStorage.setItem(key, JSON.stringify(next));
    },
  };
}
