# Frontend

React + Vite UI for the contract redlining/search API. See the
[project README](../README.md) for setup, the API reference, and design
rationale.

```bash
npm install
npm run dev      # http://localhost:5173 — expects the backend on :8000
npm run build    # production build
npm run lint     # oxlint
```

No router or state-management library — views are switched with simple
conditional rendering (`src/App.jsx`), and all API access is plain
`fetch` (`src/api.js`).
