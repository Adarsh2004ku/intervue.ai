# 🤖 Intervue.AI — Agentic AI Interview Platform

> **An AI-powered interview platform that parses resumes, conducts real-time voice + video interviews using a 5-agent LangGraph system, and generates detailed performance reports with improvement plans.**

---

## 🌟 Live Demo & Architecture

**Try it:** *[Your Vercel URL]* | **API Docs:** *[Your Render URL]/docs*

```mermaid
graph TD
    A[User: Next.js Frontend] -->|Upload Resume| B(FastAPI: REST API)
    B -->|Parse & Chunk| C(Gemini: Embeddings)
    C -->|Store Vectors| D[(Supabase: pgvector)]
    
    A -->|Start Interview| E(FastAPI: WebSocket)
    E <-->|Audio / Video Bytes| F{Gemini Native API}
    F -->|Transcribe + Evaluate| G[LangGraph: 5-Agent State Machine]
    
    G -->|Fetch Context| D
    G -->|Adaptive Questioning| E
    
    G -->|Final Report| H[Coach Agent]
    H -->|Save| I[(Supabase: Reports DB)]
    I -->|View Report| A
```

---

## ✨ Core Features

- **📄 RAG-Pipeline**: Upload a PDF/DOCX resume → AI parses it → Chunks & Embeds into pgvector → Semantic retrieval grounds interview questions in *your* actual resume.
- **🧠 5-Agent LangGraph System**: Planner → Retriever → Generator → Evaluator → Coach. Stateful, adaptive, and runs in a loop until the interview concludes.
- **🎙️ Real-Time Audio (Gemini Native)**: Speak via microphone → Audio streamed over WebSocket → Transcribed and evaluated by Gemini in a single API call (No heavy Whisper model needed, 100% Python backend).
- **📷 Real-Time Vision (Gemini Vision)**: Camera feed captured → Frames analyzed for engagement, eye contact, and posture → Live behavioral feedback.
- **📉 Weakness Tracking**: The system remembers your weak topics across sessions and intentionally biases future questions toward them.
- **📊 Comprehensive Reports**: Score breakdowns, chain-of-thought reasoning, improvement plans with resources, and PDF downloads.
- **🎭 Interview Personas**: Choose FAANG (Rigorous), Startup (Practical), or HR (Behavioural) modes.

---

## 🛠️ Tech Stack

### Backend (100% Python)
| Category | Tech |
| :--- | :--- |
| **API & Server** | FastAPI, Uvicorn, Gunicorn, WebSockets |
| **AI Orchestration** | LangGraph, LangChain |
| **LLM & Vision & Audio** | Gemini 2.5 Flash (via `google-generativeai`), Groq (Fallback) |
| **Vector Store** | Supabase PostgreSQL + pgvector |
| **Database & Auth** | Supabase, SQLAlchemy (QueuePool) |
| **Task Queue** | Celery, Redis |
| **Observability** | LangSmith, Structlog |

### Frontend
| Category | Tech |
| :--- | :--- |
| **Framework** | Next.js 14 (App Router), TypeScript |
| **Styling** | Tailwind CSS, shadcn/ui |
| **Real-time** | Native WebSocket API, MediaRecorder API, getUserMedia API |

### Infrastructure
| Category | Tech |
| :--- | :--- |
| **Containerization** | Docker, Docker Compose |
| **CI/CD** | GitHub Actions |
| **Hosting (API)** | Render.com |
| **Hosting (Frontend)**| Vercel |
| **Database Hosting** | Supabase |

---

## 📁 Project Structure

```text
intervue-ai/
├── backend/               # 100% Python FastAPI Backend
│   ├── main.py            # App entry, CORS, lifespan
│   ├── services/cache/    # Redis client, Celery app, and background tasks
│   ├── api/v1/            # Routes (auth, resume, interview, report)
│   ├── core/              # Config, Security (JWT), Middleware, Logging
│   ├── db/                # Supabase client, SQLAlchemy session, Migrations
│   ├── services/          # Business logic (RAG, Audio STT, Vision, LLM Router)
│   └── tests/             # Pytest suite
│
├── ai/                    # LangGraph Agents & AI Logic
│   ├── agents/            # Planner, Retriever, Generator, Evaluator, Coach
│   ├── graph/             # StateGraph builder
│   └── personas/          # FAANG, Startup, HR persona configs
│
├── frontend/              # Next.js Frontend
│   ├── app/               # Pages (Interview Room, Report, Dashboard)
│   ├── components/        # UI components (MicRecorder, CameraCapture)
│   └── lib/               # API client, WebSocket client, Types
│
├── docker-compose.yml     # Local dev environment (Backend + Redis + Frontend)
└── .github/workflows/     # GitHub Actions CI/CD
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- Supabase Account & Project
- Google AI Studio API Key (Gemini)

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/intervue-ai.git
cd intervue-ai
```

### 2. Setup Database (Supabase)
1. Go to your Supabase project's SQL Editor.
2. Copy the entire contents of `backend/db/migrations/001_initial.sql` and run it.
3. This creates all tables, the `match_chunks` function, indexes, and Row Level Security policies.

### 3. Environment Variables
Copy the example env file and fill in your keys:
```bash
cp backend/.env.example backend/.env
```
Edit `backend/.env`:
```env
GOOGLE_API_KEY=your_gemini_key          # Get from aistudio.google.com
GROQ_API_KEY=your_groq_key              # Get from console.groq.com
SUPABASE_URL=https://xxx.supabase.co    # From Supabase dashboard
SUPABASE_KEY=eyJhb...                   # From Supabase dashboard (anon key)
SUPABASE_SERVICE_KEY=eyJhb...           # From Supabase dashboard (service_role key)
JWT_SECRET=any_random_32_char_string
REDIS_URL=redis://localhost:6379/0      # Use rediss://default:password@host:6379 for Upstash
CELERY_ENABLED=false                    # Docker/Render set this to true when a worker is running
```

### 4. Run Locally with Docker (Recommended)
This starts the backend, Redis, Celery worker, and frontend together:
```bash
docker-compose up --build
```
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

### 5. Run Manually (Without Docker)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Celery Worker (in a separate terminal):**
```bash
cd backend
celery -A backend.services.cache.celery_app.celery_app worker --loglevel=INFO --concurrency=2
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Render Backend + Celery
`render.yaml` deploys the FastAPI web service and a separate Celery background worker. Set `REDIS_URL` to a Redis TCP/TLS URL such as `rediss://default:password@host:6379`; Upstash REST URL/token values are not compatible with Celery or `redis-py`. The worker uses Render's `starter` plan because Render does not offer the free instance type for background workers.

---

## 🧪 Testing

The backend uses `pytest` with mocked external services (Supabase, LLMs) so you can run tests without burning API keys.

```bash
cd backend
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

---

## 🔄 CI/CD Pipeline

GitHub Actions handles automated testing and deployment on every push to `main`:

1. **Backend Test**: Sets up Python 3.11, installs deps, runs Ruff linter, runs Pytest.
2. **Frontend Test**: Sets up Node 20, installs deps, runs Next.js build check.
3. **Deploy**: If tests pass, triggers Render.com deploy hook for backend and Vercel production deploy for frontend.

**Required GitHub Secrets:**
`GOOGLE_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, `RENDER_DEPLOY_HOOK`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.

---

## 💡 How the Real-Time Interview Works

1. **Start**: User selects resume, role, and mode (FAANG/Startup/HR). Frontend calls `POST /interview/start`.
2. **WebSocket Connect**: Frontend opens a persistent WebSocket connection to `/{id}/session`.
3. **Audio Capture**: User clicks the mic button. `MediaRecorder` captures audio.
4. **Transcription & Evaluation**: Audio bytes are sent over WebSocket. Backend sends them to **Gemini Native Audio API** which returns both the transcript and the evaluation score in one single call.
5. **Adaptive Generation**: The LangGraph Evaluator updates the state. If the score is low, the Generator asks a follow-up. If good, it moves to the next topic, prioritizing the user's historically weak areas.
6. **Vision Analysis**: Simultaneously, the frontend captures a video frame every 5 seconds, sending it to the backend. Gemini Vision analyzes engagement and eye contact, sending live feedback back to the UI.
7. **Report**: After 10 questions, the Coach Agent generates the final report, saves it to Supabase, and the user is redirected to the report page.

---

## 📜 License

This project is licensed under the MIT License.

---

Built with ❤️ by Adarsh Kumar | Powered by Gemini, LangGraph, and FastAPI
