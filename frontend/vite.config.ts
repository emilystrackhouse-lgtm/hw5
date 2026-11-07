import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dashboard runs on http://localhost:5173 (the origin the backend allows).
// It calls the FastAPI backend at http://localhost:8000 (see src/api.ts / .env.development).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
})
