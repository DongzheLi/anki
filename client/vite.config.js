import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev the Vite server hosts the React app and proxies API calls to the
// Python backend, so the browser only ever talks to one origin (port 5173).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
