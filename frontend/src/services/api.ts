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
  job_role: string;
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
  interview_id: string;
  first_question: InterviewQuestion;
  persona_name: string;
  opening_line: string;
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

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

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

const healthUrl = () => {
  const apiUrl = new URL(API_BASE_URL, window.location.origin);
  apiUrl.pathname = '/health';
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
    delete: (resumeId: string) =>
      request<{ message: string }>(`/resume/${resumeId}`, {
        method: 'DELETE',
      }),
  },
  interview: {
    dashboard: () => request<DashboardResponse>('/interview/dashboard'),
    history: () => request<{ interviews: InterviewRecord[] }>('/interview/history'),
    start: (resume_id: string, job_role: string, interview_mode: InterviewMode) =>
      request<StartInterviewResponse>('/interview/start', {
        method: 'POST',
        body: JSON.stringify({ resume_id, job_role, interview_mode }),
      }),
    status: (interviewId: string) =>
      request<InterviewStatusResponse>(`/interview/${interviewId}/status`),
    socketUrl: (interviewId: string) => buildWsUrl(`/interview/${interviewId}/session`),
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
    clear: () => sessionStorage.removeItem(key),
  };
}
