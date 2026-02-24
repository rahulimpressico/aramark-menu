# Frontend structure

```
src/
├── components/       # Shared UI components
│   ├── AramarkLogo.tsx
│   ├── AramarkRouteLoader.tsx
│   └── Footer.tsx
├── pages/            # Route-level page components
│   ├── CategoryAnalysisPage.tsx
│   ├── HomePage.tsx
│   └── MenuAnalysisPage.tsx
├── routes/           # Route configuration and loader
│   └── AppRoutes.tsx
├── App.tsx           # Root app (BrowserRouter)
├── App.css           # App-level styles
├── main.tsx          # Entry point
├── index.css         # Global styles, Tailwind, design tokens
└── vite-env.d.ts     # Vite types
```

## Usage

- **components/** – Reusable pieces (logo, footer, route loader).
- **pages/** – One component per main route (home, grill/menu, category analysis).
- **routes/** – Route list and navigation loader logic.
