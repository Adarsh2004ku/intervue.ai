# Intervue.ai Frontend - Complete Folder Structure

```
intervue-frontend/
├── public/
│   ├── index.html
│   ├── favicon.ico
│   └── assets/
│       ├── images/
│       │   ├── logo.svg
│       │   ├── hero-graphic.png
│       │   ├── user-avatar.jpg
│       │   └── company-logos/
│       └── icons/
│           ├── mic-on.svg
│           ├── camera-on.svg
│           ├── screen-share.svg
│           └── settings.svg
│
├── src/
│   ├── index.tsx
│   ├── App.tsx
│   ├── styles/
│   │   ├── globals.css
│   │   ├── animations.css
│   │   ├── theme.css
│   │   └── scrollEffects.css
│   │
│   ├── pages/
│   │   ├── LandingPage/
│   │   │   ├── LandingPage.tsx
│   │   │   ├── LandingPage.module.css
│   │   │   ├── components/
│   │   │   │   ├── Hero.tsx
│   │   │   ├── Hero.module.css
│   │   │   │   ├── Features.tsx
│   │   │   │   ├── Features.module.css
│   │   │   │   ├── TrustedBy.tsx
│   │   │   │   ├── TrustedBy.module.css
│   │   │   │   ├── Testimonial.tsx
│   │   │   │   └── Testimonial.module.css
│   │   │
│   │   ├── LoginPage/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── LoginPage.module.css
│   │   │   └── components/
│   │   │       ├── LoginForm.tsx
│   │   │       └── LoginForm.module.css
│   │   │
│   │   ├── HomePage/
│   │   │   ├── HomePage.tsx
│   │   │   ├── HomePage.module.css
│   │   │   └── components/
│   │   │       ├── Dashboard.tsx
│   │   │       ├── Dashboard.module.css
│   │   │       ├── StatsCard.tsx
│   │   │       ├── StatsCard.module.css
│   │   │       ├── RecentInterviews.tsx
│   │   │       ├── RecentInterviews.module.css
│   │   │       ├── ScoreTrend.tsx
│   │   │       ├── ScoreTrend.module.css
│   │   │       ├── Recommendations.tsx
│   │   │       └── Recommendations.module.css
│   │   │
│   │   ├── InterviewPage/
│   │   │   ├── InterviewPage.tsx
│   │   │   ├── InterviewPage.module.css
│   │   │   └── components/
│   │   │       ├── InterviewRoom.tsx
│   │   │       ├── InterviewRoom.module.css
│   │   │       ├── VideoGrid.tsx
│   │   │       ├── VideoGrid.module.css
│   │   │       ├── QuestionPanel.tsx
│   │   │       ├── QuestionPanel.module.css
│   │   │       ├── FeedbackAnalytics.tsx
│   │   │       └── FeedbackAnalytics.module.css
│   │
│   ├── components/
│   │   ├── Navigation/
│   │   │   ├── Navbar.tsx
│   │   │   └── Navbar.module.css
│   │   ├── Sidebar/
│   │   │   ├── Sidebar.tsx
│   │   │   └── Sidebar.module.css
│   │   ├── Button/
│   │   │   ├── Button.tsx
│   │   │   └── Button.module.css
│   │   ├── Card/
│   │   │   ├── Card.tsx
│   │   │   └── Card.module.css
│   │   └── Modal/
│   │       ├── Modal.tsx
│   │       └── Modal.module.css
│   │
│   ├── hooks/
│   │   ├── useScroll.ts
│   │   ├── useAnimation.ts
│   │   ├── useAuth.ts
│   │   └── useWindowSize.ts
│   │
│   ├── utils/
│   │   ├── api.ts
│   │   ├── formatters.ts
│   │   ├── storage.ts
│   │   └── animations.ts
│   │
│   ├── types/
│   │   ├── index.ts
│   │   ├── user.ts
│   │   ├── interview.ts
│   │   └── dashboard.ts
│   │
│   └── context/
│       ├── AuthContext.tsx
│       └── ThemeContext.tsx
│
├── .env.example
├── .gitignore
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md
```

## Setup Instructions

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Required packages:**
   - react 18+
   - react-dom 18+
   - react-router-dom
   - framer-motion (for advanced animations)
   - recharts (for analytics charts)
   - axios (for API calls)
   - typescript

3. **Start development:**
   ```bash
   npm run dev
   ```

4. **Build for production:**
   ```bash
   npm run build
   ```


   {
  "name": "intervue-ai-frontend",
  "version": "1.0.0",
  "description": "AI-powered interview preparation platform",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint src --ext ts,tsx",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "framer-motion": "^10.16.16",
    "recharts": "^2.10.3",
    "axios": "^1.6.2",
    "zustand": "^4.4.1",
    "clsx": "^2.0.0",
    "lucide-react": "^0.294.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.37",
    "@types/react-dom": "^18.2.15",
    "@types/node": "^20.9.0",
    "@vitejs/plugin-react": "^4.2.0",
    "typescript": "^5.2.2",
    "vite": "^5.0.2",
    "postcss": "^8.4.31",
    "autoprefixer": "^10.4.16"
  }
}