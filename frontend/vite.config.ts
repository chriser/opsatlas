import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The control panel talks to the platform backend (FastAPI) under /api.
// In dev, proxy those calls to the local backend so the frontend can run
// standalone and degrade gracefully when the backend is not yet running.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5200,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://localhost:8010",
        changeOrigin: true,
      },
    },
  },
});
