import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// OpsAtlas Sales: the dev server talks to this version's own backend, the sales app (scripts/start-tiberius-sales.sh,
// port 8780). It never uses port 5200 or the old backend on 8010: those belong to OpsAtlas Classic, which runs from
// its own folder, so both can run side by side. OPSATLAS_API points the dev server at another sales app (for
// example a throwaway copy of the workspace).
//
// The Host header is kept as the dev server's, so the sales app's same-origin check sees one origin on both sides.
const backend = process.env.OPSATLAS_API ?? "http://127.0.0.1:8780";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5280,
    strictPort: true,
    proxy: {
      "/api": { target: backend, changeOrigin: false },
      // Tibi's voice conversation is a WebSocket on the same host.
      "/services": { target: backend, changeOrigin: false, ws: true },
    },
  },
});
