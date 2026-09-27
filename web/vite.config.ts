import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the API runs separately (uvicorn on :8000); in Docker nginx
// serves the build and proxies /api the same way, so the app always calls
// same-origin relative URLs.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: process.env.API_URL ?? "http://localhost:8000", changeOrigin: true } },
  },
  build: {
    target: "es2022",
    chunkSizeWarningLimit: 1200,
    rollupOptions: { output: { manualChunks: { echarts: ["echarts"] } } },
  },
  test: { environment: "node" },
});
