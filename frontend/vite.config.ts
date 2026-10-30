import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the API runs on :8000 (uvicorn backend.app:app); Vite proxies /api, including WebSockets.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": { target: "http://127.0.0.1:8000", ws: true, changeOrigin: true } } },
  build: { outDir: "dist", sourcemap: true, chunkSizeWarningLimit: 1200 },
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"], css: false },
});
