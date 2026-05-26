# Intervue.AI

Intervue.AI is a full-stack AI interview preparation platform. Users sign up, upload a resume, start a role-specific mock interview, answer with audio/video, receive AI scoring, and download a final report.

The project is structured as a **monorepo** with three top-level modules:

| Directory | Purpose |
| --- | --- |
| `backend/` | FastAPI REST + WebSocket API (Python) |
| `frontend/` | Vite + React 18 SPA (TypeScript) |
| `ai/` | Shared LangGraph interview agents and interviewer personas |

Each of `backend/` and `frontend/` has its own `Dockerfile`, and a root `docker-compose.yml` orchestrates the full stack.

---

## What It Does

- Authenticates users through Supabase Auth and issues app JWTs for API access.
- Parses PDF and DOCX resumes, stores parsed data, chunks resume text, and embeds chunks into Supabase Postgres with pgvector.
- Runs persona-based interviews for `faang`, `startup`, and `hr` modes.
- Uses a LangGraph agent flow: planner → retriever → generator → evaluator → coach.
- Personalizes questions using the uploaded resume, selected job role, pasted job description, previous answers, and tracked weak topics.
- Evaluates recorded answers with ElevenLabs speech-to-text plus rubric-style scoring.
- Analyzes webcam frames with Gemini Vision for engagement, confidence, professionalism, eye contact, posture, and distraction signals.
- Tracks AI usage cost per interview in INR.
- Generates JSON reports and downloadable PDF reports.
- Supports Redis / Celery for background resume embedding and topic score updates.

---

## Tech Stack

| Area | Stack |
| --- | --- |
| Backend API | FastAPI, Uvicorn, Pydantic, Python |
| AI orchestration | LangGraph, LangChain Google GenAI |
| LLM, embeddings, vision | Gemini via `google-genai` / `langchain-google-genai` |
| LLM fallback | Groq (OpenAI-compatible, `llama-3.3-70b-versatile`) |
| Speech | ElevenLabs STT and TTS |
| Database & Auth | **Supabase** (Auth + Postgres + pgvector) — no SQLAlchemy |
| Background jobs | Redis, Celery |
| Frontend | React 18, TypeScript, Vite, React Router, Zustand, CSS Modules |
| UI helpers | Lucide React, Axios, browser media APIs |
| Python tooling | uv (fast Python package manager) |
| Deployment | Docker, Docker Compose, AWS (EC2 / ECS Fargate), GitHub Actions |

---

## Repository Layout

```text
.
├── ai/                            # Shared AI module (used by backend)
│   ├── agents/                    # Planner, retriever, generator, evaluator, coach, LLM, state
│   ├── graph/                     # LangGraph builder and question turn runner
│   ├── interview/                 # Interview helpers
│   └── personas/                  # FAANG, startup, and HR interviewer profiles
├── backend/
│   ├── api/v1/
│   │   ├── routes/                # auth, resume, interview, report, admin
│   │   └── websocket/             # Real-time interview WebSocket
│   ├── core/                      # Config, logging, middleware, health, security
│   ├── db/
│   │   ├── migrations/            # Raw SQL migrations (run in Supabase SQL Editor)
│   │   ├── models/                # Pydantic models (no ORM)
│   │   └── session.py             # Supabase client + Redis proxy
│   ├── services/
│   │   ├── audio/                 # ElevenLabs STT/TTS
│   │   ├── cache/                 # Redis client, Celery app, task queue
│   │   ├── embeddings/            # Gemini embedding service
│   │   ├── interview/             # Interview analysis and repository
│   │   ├── llm/                   # LLM provider abstraction
│   │   ├── reports/               # JSON/PDF report builder
│   │   ├── vision/                # Gemini Vision frame analysis
│   │   ├── cost_tracking.py       # AI cost tracking in INR
│   │   ├── rag_ingestion.py       # Resume chunk embedding pipeline
│   │   └── resume_parser.py       # PDF/DOCX resume extraction
│   ├── tests/                     # Pytest suite
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py                    # FastAPI app entrypoint
├── frontend/
│   ├── src/
│   │   ├── pages/                 # Landing, Login, Home, Interview, Result, Admin
│   │   ├── components/            # charts/, immersive/, ui/
│   │   └── services/api.ts        # Typed REST + WebSocket client
│   ├── Dockerfile
│   ├── nginx.conf                 # Production reverse-proxy config
│   ├── vite.config.ts
│   ├── vercel.json                # Frontend Vercel deployment config
│   └── package.json
├── docker-compose.yml             # Full stack: backend, worker, redis, frontend
├── render.yaml                    # Render web service + worker definitions
├── vercel.json                    # Root-level Vercel config (backend Python deploy)
└── main.py                        # Vercel shim — re-exports backend.main:app
```

---

## Prerequisites

- **Python** 3.12 (pinned via `.python-version`)
- **[uv](https://docs.astral.sh/uv/)** — fast Python package and project manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Node.js** 18 or newer (Node 20+ recommended)
- **Docker & Docker Compose** (optional, for containerised runs)
- **Supabase project** with pgvector enabled
- **Google AI Studio API key** (Gemini)
- **ElevenLabs API key** (for speech features)
- **Redis** (if running Celery workers outside Docker)
- **AWS account** (for production deployment)

---

## Database Setup

The project uses **Supabase** as the sole database layer (Supabase Python client → Postgres). There is **no SQLAlchemy or ORM** — all queries go through the Supabase SDK.

Run the SQL migrations in the **Supabase SQL Editor** in order:

1. `backend/db/migrations/001_initial.sql` — creates users, resumes, resume_chunks, interviews, questions, answers, reports, ai_costs, topic_profiles, pgvector indexes, and helper functions (`match_chunks`, `upsert_topic_score`).
2. `backend/db/migrations/002_add_job_description_to_interviews.sql` — adds the job description column.

---

## Environment Variables

### Backend (`backend/.env`)

Copy the example and fill in your keys:

```bash
cp backend/.env.example backend/.env
```

| Variable | Required | Description |
| --- | --- | --- |
| `GOOGLE_API_KEY` | ✅ | Google Gemini API key |
| `GROQ_API_KEY` | | Groq fallback API key |
| `ELEVENLABS_API_KEY` | | ElevenLabs STT/TTS key |
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_KEY` | ✅ | Supabase anonymous key |
| `SUPABASE_SERVICE_KEY` | ✅ | Supabase service role key (keep secret) |
| `DATABASE_URL` | | Direct Postgres connection string (optional) |
| `REDIS_URL` | | Redis TCP URL (default: `redis://localhost:6379/0`) |
| `CELERY_ENABLED` | | `true` to enable Celery background workers |
| `CELERY_BROKER_URL` | | Defaults to `REDIS_URL` if empty |
| `CELERY_RESULT_BACKEND` | | Defaults to `REDIS_URL` if empty |
| `JWT_SECRET` | ✅ | Secret key for app JWT signing |
| `FRONTEND_URL` | | Frontend origin for OAuth redirects (default: `http://localhost:3000`) |
| `CORS_ORIGINS` | | Comma-separated allowed origins (default: `http://localhost:3000`) |
| `ADMIN_EMAILS` | | Comma-separated admin email allowlist |
| `ENVIRONMENT` | | `development`, `staging`, or `production` |

### Frontend (`frontend/.env`)

```bash
cp frontend/.env.example frontend/.env
```

| Variable | Required | Description |
| --- | --- | --- |
| `VITE_API_BASE_URL` | ✅ | API base path. Use `/api/v1` for local dev (Vite proxy handles it). For deployed frontend, set to full backend URL e.g. `https://api.yourdomain.com/api/v1` |
| `VITE_WS_BASE_URL` | | WebSocket base URL. Auto-derived from API URL if unset |

---

## How to Run the Project

Both `backend/` and `frontend/` have their own `Dockerfile`. The project uses **Docker** as the primary way to build and run both services.

> **Important — Build Context:** Both Dockerfiles expect the **repository root** as the build context (the backend image copies the shared `ai/` directory). Always run `docker build` from the repo root and use `-f` to point to the Dockerfile.

---

### Backend (Docker)

```bash
# Build the backend image
docker build -t intervue-backend -f backend/Dockerfile .

# Run the backend container
docker run -d \
  --name intervue-backend \
  -p 8000:8000 \
  --env-file backend/.env \
  intervue-backend
```

| Endpoint | URL |
| --- | --- |
| API | `http://localhost:8000` |
| Swagger Docs | `http://localhost:8000/docs` |
| Health Check | `http://localhost:8000/health` |

> If `CELERY_ENABLED=true` in your `.env`, you also need a Redis instance running and `REDIS_URL` set accordingly.

---

### Frontend (Docker)

The frontend Dockerfile builds a production Vite bundle and serves it via **Nginx**. Pass the backend API URL as a build argument:

```bash
# Build the frontend image
docker build \
  -t intervue-frontend \
  -f frontend/Dockerfile \
  --build-arg VITE_API_BASE_URL=http://localhost:8000/api/v1 \
  .

# Run the frontend container
docker run -d \
  --name intervue-frontend \
  -p 3000:80 \
  intervue-frontend
```

Frontend will be at `http://localhost:3000`. The Nginx config inside the container reverse-proxies `/api/*` and `/health` to the backend.

> For production, replace `VITE_API_BASE_URL` with your actual backend URL (e.g. `https://api.yourdomain.com/api/v1`).

---

### Full Stack — Docker Compose

To spin up **everything at once** (backend, Celery worker, Redis, and frontend) using the root `docker-compose.yml`:

```bash
# From the repository root
docker compose up --build
```

| Service | URL |
| --- | --- |
| Frontend | `http://localhost:3000` (Nginx) |
| Backend API | `http://localhost:8000` |
| Swagger Docs | `http://localhost:8000/docs` |
| Redis | `localhost:6380` (mapped from container `6379`) |

Docker Compose automatically wires the services together — the frontend Nginx proxies API requests to the backend container, and the Celery worker connects to the Redis container.

To stop everything:

```bash
docker compose down
```

To rebuild after code changes:

```bash
docker compose up --build -d
```

---

### Local Development (Without Docker)

For faster iteration with hot-reload, you can run the services directly on your machine.

#### Backend

```bash
# From the repository root
uv venv
source .venv/bin/activate
uv pip install -r backend/requirements.txt

uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

> `uv venv` picks up Python 3.12 from `.python-version`. `uv pip install` is a drop-in replacement for `pip install` but significantly faster.

#### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Dev server runs at `http://localhost:3000` with Vite proxying `/api` and `/health` to `http://127.0.0.1:8000`.

#### Celery Worker (Optional)

```bash
# From the repository root, with venv activated
celery -A backend.services.cache.celery_app.celery_app worker --loglevel=INFO --concurrency=2
```

---

## Deployment (AWS)

The recommended production architecture on AWS:

```text
┌─────────────┐      ┌──────────────────┐      ┌────────────────────┐
│  CloudFront  │─────▶│  S3 (Frontend)   │      │  Supabase (hosted) │
│  CDN         │      │  Static SPA      │      │  Auth + Postgres   │
└─────────────┘      └──────────────────┘      │  + pgvector        │
                                                └────────────────────┘
┌─────────────┐      ┌──────────────────┐              ▲
│  ALB         │─────▶│  ECS Fargate     │──────────────┘
│  (HTTPS)     │      │  backend service │
└─────────────┘      │  worker service  │──────┐
                      └──────────────────┘      │
                                                ▼
                      ┌──────────────────┐
                      │  ElastiCache     │
                      │  (Redis)         │
                      └──────────────────┘
```

| AWS Service | Purpose |
| --- | --- |
| **ECR** | Private Docker image registry |
| **ECS Fargate** | Runs backend API container + Celery worker container (serverless, no EC2 to manage) |
| **ALB** | Application Load Balancer — HTTPS termination, routes to backend ECS tasks |
| **ElastiCache (Redis)** | Managed Redis for Celery broker and caching |
| **S3 + CloudFront** | Hosts the frontend static build with global CDN |
| **Supabase** | Remains externally hosted (Auth + Postgres + pgvector) |

---

### Step 1 — Push Docker Images to ECR

Create ECR repositories and push both images:

```bash
# Authenticate Docker with ECR
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin <AWS_ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com

# Create repositories (one-time)
aws ecr create-repository --repository-name intervue-ai/backend --region ap-south-1
aws ecr create-repository --repository-name intervue-ai/frontend --region ap-south-1

# Build and push backend
docker build -t intervue-backend -f backend/Dockerfile .
docker tag intervue-backend:latest <AWS_ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/intervue-ai/backend:latest
docker push <AWS_ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/intervue-ai/backend:latest

# Build and push frontend
docker build -t intervue-frontend -f frontend/Dockerfile \
  --build-arg VITE_API_BASE_URL=https://api.yourdomain.com/api/v1 .
docker tag intervue-frontend:latest <AWS_ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/intervue-ai/frontend:latest
docker push <AWS_ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/intervue-ai/frontend:latest
```

---

### Step 2 — Set Up ElastiCache (Redis)

1. Go to **ElastiCache → Create Redis OSS Cluster**.
2. Choose **Serverless** or a `cache.t3.micro` node.
3. Place it in the **same VPC** as your ECS tasks.
4. Note the **Primary Endpoint** (e.g. `redis://intervue-redis.xxxxx.apse1.cache.amazonaws.com:6379`).
5. Use this as `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` in the backend environment.

---

### Step 3 — Deploy Backend on ECS Fargate

1. **Create an ECS Cluster:**
   ```bash
   aws ecs create-cluster --cluster-name intervue-ai --region ap-south-1
   ```

2. **Create a Task Definition** for the backend API (`intervue-backend-task`):
   - Image: `<AWS_ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/intervue-ai/backend:latest`
   - Port mapping: `8000`
   - CPU: 512, Memory: 1024 (adjust as needed)
   - Environment variables: set all backend `.env` vars, with `CELERY_ENABLED=true`, `REDIS_URL` pointing to ElastiCache, `ENVIRONMENT=production`
   - Health check: `CMD-SHELL, curl -f http://127.0.0.1:8000/health || exit 1`

3. **Create a Task Definition** for the Celery worker (`intervue-worker-task`):
   - Same image as the backend
   - **Override command:** `celery,-A,backend.services.cache.celery_app.celery_app,worker,--loglevel=INFO,--concurrency=2`
   - No port mapping needed
   - Same environment variables as the backend

4. **Create an Application Load Balancer (ALB):**
   - Listeners: HTTPS (:443) with your SSL certificate (ACM)
   - Target group pointing to port `8000`, health check path `/health`

5. **Create ECS Services:**
   ```bash
   # Backend API service (behind ALB)
   aws ecs create-service \
     --cluster intervue-ai \
     --service-name intervue-backend \
     --task-definition intervue-backend-task \
     --desired-count 2 \
     --launch-type FARGATE \
     --load-balancers targetGroupArn=<TARGET_GROUP_ARN>,containerName=backend,containerPort=8000 \
     --network-configuration "awsvpcConfiguration={subnets=[<SUBNET_IDS>],securityGroups=[<SG_ID>],assignPublicIp=ENABLED}"

   # Celery worker service (no ALB)
   aws ecs create-service \
     --cluster intervue-ai \
     --service-name intervue-worker \
     --task-definition intervue-worker-task \
     --desired-count 1 \
     --launch-type FARGATE \
     --network-configuration "awsvpcConfiguration={subnets=[<SUBNET_IDS>],securityGroups=[<SG_ID>],assignPublicIp=ENABLED}"
   ```

6. Point your domain's API subdomain (e.g. `api.yourdomain.com`) to the ALB via Route 53.

---

### Step 4 — Deploy Frontend to S3 + CloudFront

The frontend is a static Vite build — no server required.

```bash
# Build locally
cd frontend
npm ci
VITE_API_BASE_URL=https://api.yourdomain.com/api/v1 npm run build

# Create S3 bucket
aws s3 mb s3://intervue-ai-frontend --region ap-south-1

# Enable static website hosting
aws s3 website s3://intervue-ai-frontend --index-document index.html --error-document index.html

# Upload the build
aws s3 sync dist/ s3://intervue-ai-frontend --delete
```

Then create a **CloudFront distribution**:

1. Origin: the S3 bucket (use OAC — Origin Access Control).
2. **Default root object:** `index.html`.
3. **Custom error responses:** 403 and 404 → return `/index.html` with status 200 (required for SPA client-side routing).
4. Attach your SSL certificate (ACM) and set alternate domain name (e.g. `app.yourdomain.com`).
5. Point `app.yourdomain.com` to the CloudFront distribution via Route 53.

---

### Step 5 — Configure CORS & Environment

On the **backend** ECS task definition, set:

```env
FRONTEND_URL=https://app.yourdomain.com
CORS_ORIGINS=https://app.yourdomain.com
ENVIRONMENT=production
```

On the **frontend** build, set:

```env
VITE_API_BASE_URL=https://api.yourdomain.com/api/v1
VITE_WS_BASE_URL=wss://api.yourdomain.com
```

---

### Alternative — Deploy on a Single EC2 Instance

For simpler setups or lower cost, you can run everything on one EC2 instance using Docker Compose:

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ec2-user@<EC2_PUBLIC_IP>

# Install Docker & Docker Compose
sudo yum update -y
sudo yum install -y docker
sudo service docker start
sudo usermod -aG docker ec2-user
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone repo and set up env files
git clone https://github.com/your-username/intervue.ai.git
cd intervue.ai
cp backend/.env.example backend/.env
# Edit backend/.env with production values

# Run the full stack
docker compose up -d --build
```

- Open ports `80` and `443` in the EC2 Security Group.
- Use **Nginx** or **Caddy** as a reverse proxy in front with SSL (Let's Encrypt).
- Recommended instance: `t3.medium` or larger.

---

### CI/CD (GitHub Actions)

The `.github/workflows/ci-cd.yml` pipeline runs on every push/PR to `main`:

| Job | What it does |
| --- | --- |
| `backend` | Installs Python deps, runs `pytest backend/tests` |
| `frontend` | Runs `npm run type-check` and `npm run build` |
| `docker` | Builds both Docker images, pushes to GHCR on `main` |
| `deploy` | Triggers deployment (configurable for AWS) |

To automate AWS deployment, add these **GitHub Secrets**:

| Secret | Purpose |
| --- | --- |
| `AWS_ACCESS_KEY_ID` | IAM user access key for ECR + ECS |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret key |
| `AWS_REGION` | e.g. `ap-south-1` |
| `ECR_REGISTRY` | `<ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com` |
| `ECS_CLUSTER` | ECS cluster name |
| `ECS_BACKEND_SERVICE` | Backend ECS service name |
| `ECS_WORKER_SERVICE` | Worker ECS service name |
| `S3_FRONTEND_BUCKET` | S3 bucket name for frontend |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution ID (for cache invalidation) |

A typical deploy step pushes new images to ECR, updates the ECS services to force a new deployment, syncs the frontend build to S3, and invalidates the CloudFront cache.

---

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

---

## Interview Flow

1. The user signs up or logs in and receives an app JWT.
2. The user uploads a PDF or DOCX resume.
3. The backend extracts text, classifies resume sections, chunks content, and embeds chunks into pgvector via Supabase.
4. The user starts an interview with a resume, job role, job description, and mode.
5. The backend creates an interview record, chooses a persona, builds an initial agent state, and returns the first question.
6. The interview room records audio answers and webcam frames.
7. Audio answers are transcribed and scored, then the LangGraph question turn generates the next question.
8. Webcam frames are analyzed and accumulated into a behavior summary.
9. Completing the interview writes the final report, updates topic scores, and exposes report JSON/PDF endpoints.

---

## Testing

Backend tests:

```bash
# Using uv (from repo root, with venv activated)
uv run pytest backend/tests -rs
```

Frontend type-check and build validation:

```bash
cd frontend
npm run type-check
npm run build
```

---

## License

This project is licensed under the MIT License.
