import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // @ricky0123/vad-web ships CommonJS (`require("onnxruntime-web")`), so it
  // MUST go through Vite's dep pre-bundler -- that is what converts it to ESM
  // for the browser. Excluding it from optimizeDeps serves raw CJS, the module
  // throws on `exports is not defined`, and the page renders blank. Measured,
  // not guessed: Vite served `exports.MicVAD = ...` verbatim.
  //
  // The /vad/*.mjs public-dir conflict is handled in src/audio/turn.ts by
  // building the asset base URL at runtime instead of as a literal.
  server: {
    proxy: {
      // Keep every provider key server-side. The client talks only to our backend.
      "/ws": { target: "ws://localhost:8000", ws: true },
      "/api": "http://localhost:8000",
    },
  },
});
