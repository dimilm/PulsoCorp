import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Vitest config kept separate from `vite.config.ts` so the production build
// stays free of test-only dependencies and the proxy section.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
