#!/usr/bin/env node
/**
 * Copies the VAD's ONNX model, worklet and ONNX Runtime WASM files into
 * frontend/public/vad/ -- the single directory served from `/vad/` in all
 * three places this app runs (Vite dev, `npm run build`'s dist/, and the
 * Modal-mounted static bundle). See docs/plans/blocks/02-voice-loop.md,
 * "The VAD assets" -- MicVAD.new() defaults both `baseAssetPath` and
 * `onnxWASMBasePath` to "./", which resolves against the *document* URL
 * under Vite and 404s. Serving from a directory we control and pointing
 * both options at it is the fix; this script is what keeps that directory
 * populated without committing binary assets to git (frontend/public/vad/
 * is gitignored -- it's a copy, not a source file).
 *
 * Zero dependencies deliberately: this runs before `npm run dev` and
 * `npm run build` on every invocation (package.json), so pulling in a
 * copy-file library here would be one more thing to explain for a task
 * `fs.copyFileSync` already does in one line.
 */

import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const OUT_DIR = join(ROOT, "public", "vad");

// [source relative to node_modules, destination filename]
const FILES = [
  ["@ricky0123/vad-web/dist/vad.worklet.bundle.min.js", "vad.worklet.bundle.min.js"],
  // v5 is the model MicVAD is configured to use (turn.ts); legacy is copied
  // too so falling back is a one-word config change, not a rebuild, if v5
  // ever misfires on breaths (docs/plans/blocks/02-voice-loop.md, task 10's
  // trap list).
  ["@ricky0123/vad-web/dist/silero_vad_v5.onnx", "silero_vad_v5.onnx"],
  ["@ricky0123/vad-web/dist/silero_vad_legacy.onnx", "silero_vad_legacy.onnx"],
  // Assumed (not re-derived here): importing "onnxruntime-web/wasm" resolves
  // to the plain (non-`.jsep`) threaded SIMD build. Verify this in the
  // browser's Network tab the first time the page loads -- the `.jsep`
  // variant is ~28 MB and would mean this list is wrong.
  ["onnxruntime-web/dist/ort-wasm-simd-threaded.mjs", "ort-wasm-simd-threaded.mjs"],
  ["onnxruntime-web/dist/ort-wasm-simd-threaded.wasm", "ort-wasm-simd-threaded.wasm"],
];

mkdirSync(OUT_DIR, { recursive: true });

for (const [src, destName] of FILES) {
  const srcPath = join(ROOT, "node_modules", src);
  if (!existsSync(srcPath)) {
    console.error(`sync-vad-assets: missing ${srcPath} -- did npm install run?`);
    process.exit(1);
  }
  copyFileSync(srcPath, join(OUT_DIR, destName));
}

console.log(`sync-vad-assets: copied ${FILES.length} files to ${OUT_DIR}`);
