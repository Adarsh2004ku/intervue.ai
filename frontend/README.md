# Intervue.ai Frontend

Production-ready React + TypeScript frontend for the Intervue.ai interview preparation experience. It includes four animated pages, responsive layouts, charts, and a Vite build pipeline.

## Pages

- `/` - Landing page with hero, feature cards, social proof, testimonials, and CTA
- `/login` - Split-screen login page with animated background and form state
- `/home` - Dashboard with sidebar navigation, stats, charts, recent interviews, and recommendations
- `/interview` - Interview room with video panels, live feedback, waveform, timer, controls, and notes

## Tech Stack

- React 18
- TypeScript
- Vite
- CSS Modules
- Framer Motion
- Recharts
- Lucide React

## Getting Started

```bash
npm install
npm run dev
```

The dev server runs on `http://localhost:3000` by default.
During development, Vite proxies `/api` and `/health` to `http://127.0.0.1:8000`.

To point the frontend at another backend, set:

```bash
VITE_API_BASE_URL=https://your-api.example.com/api/v1
VITE_WS_BASE_URL=wss://your-api.example.com/api/v1
```

## Scripts

```bash
npm run dev
npm run build
npm run preview
npm run type-check
```

## Project Layout

Vite expects `index.html` at the project root. Static assets belong in `public/`.

```text
frontend/
├── index.html
├── package.json
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── hooks/
│   ├── pages/
│   └── styles/
├── public/
├── tsconfig.json
└── vite.config.ts
```

## Backend Integration

The frontend API client lives in `src/services/api.ts` and connects to:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/signup`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/google`
- `GET /api/v1/auth/callback`
- `GET /api/v1/resume`
- `POST /api/v1/resume/upload`
- `GET /api/v1/interview/dashboard`
- `GET /api/v1/interview/history`
- `POST /api/v1/interview/start`
- `GET /api/v1/interview/{id}/status`
- `WS /api/v1/interview/{id}/session`

Supabase URL and service keys belong in `backend/.env`. The frontend does not
connect to Supabase directly; Google OAuth is started through the Python backend.
