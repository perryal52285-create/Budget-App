import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: "./" emits relative asset URLs. The server injects a runtime <base href>
// derived from Home Assistant's X-Ingress-Path so the SPA works under the
// dynamic ingress prefix as well as standalone on :8099.
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true },
});
