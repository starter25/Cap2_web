import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI backend (web_viz.backend.app) serves the built SPA from ./dist
// in production, and exposes the data API under /api. During `vite dev` we
// proxy /api to the running backend so the frontend talks to the real device
// without CORS. Override the target with VITE_API_TARGET if the backend runs
// on a different host/port.
const API_TARGET = process.env.VITE_API_TARGET ?? "http://127.0.0.1:5080";

export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    port: 5173,
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // Plotly is large; split it into its own chunk so app code stays small and
    // the vendor bundle caches across deploys.
    rollupOptions: {
      output: {
        manualChunks: { plotly: ["plotly.js-dist-min"] },
      },
    },
  },
});
