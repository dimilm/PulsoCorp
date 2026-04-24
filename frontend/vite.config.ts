import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// During `npm run dev` the React app calls `/api/v1/...` which has no host
// component. Without a proxy the browser would resolve those URLs against the
// Vite dev server (5173) and get 404s. The proxy below forwards every `/api`
// request to the FastAPI backend so the dev experience matches the
// production setup served via Nginx.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_BACKEND_URL || "http://localhost:8001";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target,
          changeOrigin: true,
          secure: false,
        },
      },
    },
  };
});
