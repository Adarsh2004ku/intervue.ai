# Intervue.AI

Intervue.AI is a full-stack AI interview preparation platform. It lets a user sign up, upload a resume, start a role-specific mock interview, answer with audio/video, receive AI scoring, and download a final report.

The project is split into a FastAPI backend, a Vite React frontend, and a shared `ai/` package that contains the LangGraph interview agents and interviewer personas.

## What It Does

- Authenticates users through Supabase Auth and issues app JWTs for API access.
- Parses PDF and DOCX resumes, stores parsed resume data, chunks resume text, and embeds chunks into Supabase Postgres with pgvector.
- Runs persona-based interviews for `faang`, `startup`, and `hr` modes.
- Uses a LangGraph agent flow: planner, retriever, generator, evaluator, and coach.
- Personalizes questions with the uploaded resume, selected job role, pasted job description, previous answers, and tracked weak topics.
- Evaluates recorded answers with ElevenLabs speech-to-text plus rubric-style scoring.
- Analyzes webcam frames with Gemini Vision for engagement, confidence, professionalism, eye contact, posture, and distraction signals.
- Tracks AI usage cost per interview in INR.
- Generates JSON reports and downloadable PDF reports.
- Supports Redis/Celery for background resume embedding and topic score updates.

## Tech Stack

| Area | Stack |
| --- | --- |
| Backend API | FastAPI, Uvicorn, Pydantic, Python |
| AI orchestration | LangGraph, LangChain Google GenAI |
| LLM, embeddings, vision | Gemini via `google-genai` / `langchain-google-genai` |
| Speech | ElevenLabs STT and TTS |
| Database and auth | Supabase Auth, Supabase Postgres, pgvector |
| Background jobs | Redis, Celery |
| Frontend | React 18, TypeScript, Vite, React Router, CSS Modules |
| UI helpers | Lucide React, browser media APIs |
| Deployment | Docker, Docker Compose, Render, Vercel, GitHub Actions |

## Repository Layout

```text
.
├── ai/                         # Interview state, agents, graph builder, personas
│   ├── agents/                 # Planner, retriever, generator, evaluator, coach
│   ├── graph/                  # LangGraph construction and question turn runner
│   └── personas/               # FAANG, startup, and HR interviewer profiles
├── backend/
│   ├── api/v1/                 # Auth, resume, interview, report, admin routes
│   ├── core/                   # Config, logging, middleware, health, security
│   ├── db/                     # Supabase client, SQLAlchemy helpers, migrations
│   ├── services/               # Resume parsing, RAG, interview, audio, vision, reports
│   ├── tests/                  # Pytest suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/              # Landing, login, dashboard, interview room
│   │   ├── components/         # Immersive background, charts, UI helpers
│   │   └── services/api.ts     # Typed REST/WebSocket client
│   ├── Dockerfile
│   └── package.json
├── backend/db/migrations/      # Supabase schema and follow-up migrations
├── docker-compose.yml          # Backend, worker, Redis, frontend nginx image
├── render.yaml                 # Render web service and worker
├── vercel.json                 # Root FastAPI deployment entrypoint
└── main.py                     # Vercel shim that exposes backend.main:app
```

## Prerequisites

- Python 3.11 or newer
- Node.js 18 or newer, Node 20+ recommended
- Docker and Docker Compose, optional but recommended
- Supabase project
- Google AI Studio API key
- ElevenLabs API key for speech features
- Redis if running Celery outside Docker

## Database Setup

Run the SQL migrations in Supabase SQL Editor:

1. `backend/db/migrations/001_initial.sql`
2. `backend/db/migrations/002_add_job_description_to_interviews.sql`

The initial migration creates users, resumes, resume chunks, interviews, questions, answers, reports, AI costs, topic profiles, pgvector indexes, and helper functions such as `match_chunks` and `upsert_topic_score`.

## Environment Variables

Create backend and frontend environment files from the examples:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Backend variables live in `backend/.env`:

```env
GOOGLE_API_KEY=
EMBEDDING_MODEL=gemini-embedding-001
GROQ_API_KEY=
ELEVENLABS_API_KEY=

SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_KEY=
DATABASE_URL=

REDIS_URL=redis://localhost:6379/0
CELERY_ENABLED=false
CELERY_BROKER_URL=
CELERY_RESULT_BACKEND=

JWT_SECRET=
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000
ENVIRONMENT=development
```

Frontend variables live in `frontend/.env`:

```env
VITE_API_BASE_URL=/api/v1
# VITE_WS_BASE_URL=wss://your-backend.example.com
```

For hosted frontend deployments, set `VITE_API_BASE_URL` to the backend URL including `/api/v1`, for example `https://api.example.com/api/v1`.

## Run With Docker

From the repository root:

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Backend docs: `http://localhost:8000/docs`
- Redis container port: `6379`
- Redis host port: `6380`

Docker Compose runs the backend, Celery worker, Redis, and a production-built frontend served by nginx.

## Run Manually

Start the backend from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal:

```bash
cd frontend
npm ci
npm run dev
```

The Vite dev server runs on `http://localhost:3000` and proxies `/api` and `/health` to `http://127.0.0.1:8000`.

Run a Celery worker only when you want queued background jobs:

```bash
celery -A backend.services.cache.celery_app.celery_app worker --loglevel=INFO --concurrency=2
```

Set `CELERY_ENABLED=true` and use a reachable `REDIS_URL` before starting the worker.

## Main API Routes

All backend routes are mounted under `/api/v1`.

| Feature | Routes |
| --- | --- |
| Health | `GET /health`, `GET /api/v1/health` |
| Auth | `POST /api/v1/auth/signup`, `POST /api/v1/auth/login`, `GET /api/v1/auth/google`, `GET /api/v1/auth/callback`, `GET /api/v1/auth/me` |
| Resumes | `GET /api/v1/resume`, `POST /api/v1/resume/upload`, `GET /api/v1/resume/{resume_id}`, `DELETE /api/v1/resume/{resume_id}` |
| Interviews | `POST /api/v1/interview/interview/start`, `GET /api/v1/interview/interview`, `GET /api/v1/interview/interview/{interview_id}`, `POST /api/v1/interview/interview/analyze-audio`, `POST /api/v1/interview/interview/analyze-frame`, `POST /api/v1/interview/interview/{interview_id}/complete` |
| Realtime | `WS /api/v1/interview/interview/ws/interview/{interview_id}` |
| Reports | `GET /api/v1/report/{interview_id}`, `GET /api/v1/report/{interview_id}/pdf` |
| Admin | `GET /api/v1/admin/dashboard`, `GET /api/v1/admin/costs`, `GET /api/v1/admin/metrics` |

The duplicated `interview/interview` path is intentional in the current codebase: the v1 router mounts the interview route group at `/interview`, and the interview router also has an `/interview` prefix.

## Interview Flow

1. The user signs up or logs in and receives an app JWT.
2. The user uploads a PDF or DOCX resume.
3. The backend extracts text, classifies resume sections, chunks content, and embeds chunks into pgvector.
4. The user starts an interview with a resume, job role, job description, and mode.
5. The backend creates an interview record, chooses a persona, builds an initial agent state, and returns the first question.
6. The interview room records audio answers and webcam frames.
7. Audio answers are transcribed and scored, then the LangGraph question turn generates the next question.
8. Webcam frames are analyzed and accumulated into a behavior summary.
9. Completing the interview writes the final report, updates topic scores, and exposes report JSON/PDF endpoints.

## Testing

Backend tests:

```bash
python -m pytest backend/tests -rs
```

Frontend checks:

```bash
cd frontend
npm run type-check
npm run build
```

The CI workflow runs backend pytest, frontend type-check/build, Docker builds for backend and frontend images, and optional Render/Vercel deploy steps when secrets are configured.

## Deployment Notes

### Render

`render.yaml` defines:

- `intervue-ai-backend`: FastAPI web service built from `backend/Dockerfile`
- `intervue-ai-worker`: Celery worker built from the same Dockerfile

Use a Redis TCP/TLS URL for `REDIS_URL`, such as `rediss://default:password@host:6379`. Upstash REST URLs are not compatible with Celery or `redis-py`.

### Vercel

The root `vercel.json` is configured for the FastAPI backend through `main.py`, which imports `backend.main:app`.

The frontend can be deployed separately from the `frontend/` directory. Set `VITE_API_BASE_URL` to the hosted backend URL ending in `/api/v1`, and include the frontend origin in backend `CORS_ORIGINS`.

## License

This project is licensed under the MIT License.
