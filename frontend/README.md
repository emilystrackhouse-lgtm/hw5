# Campus Customs Ops Floor (dashboard)

React + Vite + TypeScript dashboard for the Campus Customs agent team.

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

It calls the FastAPI backend at `http://localhost:8000` (set in `.env.development` as `VITE_API_BASE`). Start the backend first, from `backend/`:

```bash
uvicorn main:app --reload --port 8000
```

Design notes: `../output/design.md`.
