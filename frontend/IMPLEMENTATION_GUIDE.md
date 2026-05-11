# Implementation Guide

## 1. Install Dependencies

```bash
npm install
```

## 2. Start Development

```bash
npm run dev
```

Open `http://localhost:3000`.

Run the FastAPI backend on `http://127.0.0.1:8000` so the Vite proxy can forward `/api` and `/health` requests.

## 3. Verify Routes

- Landing: `http://localhost:3000/`
- Login: `http://localhost:3000/login`
- Dashboard: `http://localhost:3000/home`
- Interview room: `http://localhost:3000/interview`

## 4. Build for Production

```bash
npm run build
```

The production output is written to `dist/`.

## 5. API Configuration

By default, the frontend uses same-origin `/api/v1` and the dev proxy forwards it to FastAPI.

For a deployed backend, set:

```bash
VITE_API_BASE_URL=https://your-api.example.com/api/v1
VITE_WS_BASE_URL=wss://your-api.example.com/api/v1
VITE_SUPABASE_URL=https://your-project.supabase.co
```

The main API client is `src/services/api.ts`.

Email signup/login uses Supabase Auth through the Python backend. Google login redirects through Supabase OAuth, so enable Google in Supabase Auth providers and add `http://localhost:3000/login` as an allowed redirect URL in Supabase.

## 6. Deployment

Any static host that supports Vite works well:

```bash
npm run build
npm run preview
```

Deploy the generated `dist/` folder to Vercel, Netlify, S3, or your preferred static hosting platform.
