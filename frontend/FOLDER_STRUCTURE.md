# Folder Structure

```text
frontend/
├── index.html
├── package.json
├── package-lock.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── README.md
├── IMPLEMENTATION_GUIDE.md
├── FOLDER_STRUCTURE.md
├── public/
│   └── favicon.svg
└── src/
    ├── App.tsx
    ├── main.tsx
    ├── index.css
    ├── vite-env.d.ts
    ├── hooks/
    │   └── useScroll.ts
    ├── pages/
    │   ├── HomePage.tsx
    │   ├── HomePage.module.css
    │   ├── InterviewPage.tsx
    │   ├── InterviewPage.module.css
    │   ├── LandingPage.tsx
    │   ├── LandingPage.module.css
    │   ├── LoginPage.tsx
    │   └── LoginPage.module.css
    └── styles/
        └── animations.css
```

## Notes

- `index.html` lives at the Vite project root, not inside `public/`.
- `public/` is reserved for static files copied directly into the production build.
- `src/styles/animations.css` contains shared animation keyframes and design tokens.
- Each page uses a colocated CSS Module for scoped layout and component styling.
