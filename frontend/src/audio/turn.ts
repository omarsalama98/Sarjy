/**
 * Turn detection: the VAD decides when an utterance begins and ends.
 * Nothing is sent to the server until it decides the utterance is over --
 * see the block plan's design decision 2 ("nothing goes over the network
 * until onSpeechEnd"). Endpointing runs client-side because it saves a
 * network round trip on every turn (.claude/rules/voice/browser-audio.md).
 *
 * The silence threshold (`redemptionMs`) is a PRODUCT DECISION, not a
 * constant: it trades cutting the user off against making them wait, and
 * it is the single largest term in the whole latency budget -- larger than
 * any provider call. `getRedemptionMs()` reads it from the URL
 * (`?redemptionMs=800`) so the sweep in docs/plans/blocks/02-voice-loop.md
 * (task 14) can be run by ear, live, without a rebuild between trials.
 * DEFAULT_REDEMPTION_MS below is a placeholder until that sweep runs by a
 * human speaking into a real microphone -- record the chosen value and the
 * reason in docs/measurements/block2-voice-loop.md, then replace the
 * default here.
 */

import { MicVAD } from "@ricky0123/vad-web";
import { floatToPCM16, getSharedMicStream, TARGET_SAMPLE_RATE } from "./capture";

// One-character fix under pressure: if the demo shows Sarjy interrupting
// itself, echo cancellation didn't hold (unproven until task 10 runs on
// real speakers) and this is the fastest way to remove barge-in without
// touching anything else. Its existence is a stated trade-off, not a hedge.
export const BARGE_IN_ENABLED = true;

const DEFAULT_REDEMPTION_MS = 600;

// Groq Whisper's transcription window is a hard 30s -- not a guess (see
// backend/app/pipeline/turn.py's MAX_TURN_BYTES, the server's independent
// backstop for the same limit).
const MAX_UTTERANCE_MS = 30_000;

// vad-web's own default (frame-processor.js) -- matched here so the
// endpointing instrument below fires on the same threshold the library
// itself uses to decide a frame is speech.
const POSITIVE_SPEECH_THRESHOLD = 0.3;

export function getRedemptionMs(): number {
  const override = new URLSearchParams(window.location.search).get("redemptionMs");
  const parsed = override ? Number(override) : NaN;
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_REDEMPTION_MS;
}

/**
 * Absolute, and that is load-bearing -- "/vad/" breaks `npm run dev`.
 *
 * Vite's dep pre-bundler rewrites dynamic imports inside optimized deps as
 * `__vite__injectQuery(path, "import")`, and onnxruntime-web loads its WASM
 * glue with exactly such an import. Vite's own injectQuery reads:
 *
 *     if (url[0] !== "." && url[0] !== "/") return url;   // untouched
 *     ...otherwise append "?import"
 *
 * so "/vad/ort-wasm-simd-threaded.mjs" becomes ".mjs?import", which routes the
 * request through the transform pipeline instead of the static handler -- and
 * that pipeline refuses anything under public/ ("should not be imported from
 * source code"). The page renders blank with the error only in the dev-server
 * log. An absolute URL is returned untouched, so it reaches the static handler.
 *
 * Dev-only failure: `npm run build` has no transform middleware, which is why
 * the deployed URL always worked while `npm run dev` did not.
 */
const VAD_ASSET_BASE = new URL("/vad/", window.location.origin).href;

const VAD_ASSET_PATHS = [
  `${VAD_ASSET_BASE}silero_vad_v5.onnx`,
  `${VAD_ASSET_BASE}vad.worklet.bundle.min.js`,
  `${VAD_ASSET_BASE}ort-wasm-simd-threaded.wasm`,
];

/**
 * F1/F2: HEAD-checks every asset URL before MicVAD.new() ever runs, so a
 * missing file is a legible on-screen message naming the exact URL and
 * status -- never a silent "no speech events, nothing on the page" (the
 * observed Block 0 failure this whole trap exists to close off).
 */
export async function assertVadAssets(): Promise<void> {
  for (const path of VAD_ASSET_PATHS) {
    let response: Response;
    try {
      response = await fetch(path, { method: "HEAD" });
    } catch (err) {
      throw new Error(`Voice detection failed to load (${path} could not be reached: ${String(err)}).`, {
        cause: err,
      });
    }
    if (!response.ok) {
      throw new Error(`Voice detection failed to load (${path} returned ${response.status}).`);
    }
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("text/html")) {
      throw new Error(
        `Voice detection failed to load (${path} returned HTML instead of the asset -- was the frontend built?).`,
      );
    }
  }
}

/**
 * The endpointing leg of Block 3's timing record -- the one measurement
 * that only exists in the browser (the server never sees the acoustic
 * signal). `acousticEndAtMs` is a `performance.now()` timestamp, not a
 * duration, so App.tsx can subtract it from the moment the first audio
 * buffer is scheduled to get `first_audio_ms`, the headline number.
 */
export interface EndpointTiming {
  endpointMs: number; // last frame above POSITIVE_SPEECH_THRESHOLD -> onSpeechEnd firing
  acousticEndAtMs: number; // that frame's performance.now(), so App can close the headline leg
  redemptionMs: number;
}

export interface TurnDetectorCallbacks {
  /** VAD onSpeechStart -- rendered as "listening" immediately, client-only,
   * no round trip (docs/plans/blocks/02-voice-loop.md's state-ownership table). */
  onSpeechStart(): void;
  /** VAD onSpeechEnd, already converted to PCM16. `durationMs` is the
   * segment's own length (pre-speech padding included), for logging only. */
  onUtterance(pcm: ArrayBuffer, sampleRate: number, durationMs: number, endpoint: EndpointTiming): void;
  /** Backchannels ("mhm", "yeah") -- too short to be a turn. Must not
   * change conversation state or open a turn. */
  onMisfire(): void;
  /** onSpeechRealStart while `setSpeaking(true)` -- confirmed speech (past
   * minSpeechMs) during playback. The anti-self-interrupt primitive: it
   * only fires after real, sustained speech, not a stray noise. */
  onBargeDetected(): void;
}

export interface TurnDetector {
  /** Opens the microphone and starts listening -- the ONLY thing in this
   * module that touches getUserMedia. Must only be called from inside a
   * user gesture (Start button click): NotAllowedError (F3) and
   * NotFoundError (F4) surface here, and the caller catches them. */
  start(): Promise<void>;
  /** The gate: true while Sarjy's own audio is playing. The VAD keeps
   * running throughout -- it is never paused during a conversation, because
   * that is what makes barge-in possible -- this only changes whether
   * onSpeechRealStart is interpreted as one. */
  setSpeaking(isSpeaking: boolean): void;
  destroy(): Promise<void>;
}

/**
 * Constructs the VAD -- downloads its ~16MB of ONNX + WASM assets -- but
 * does NOT start it. Call this at page load, while the reviewer is still
 * reading the screen, not after they click Start (`browser-audio.md`'s "mic
 * prompt on page load with no explanation" anti-pattern would otherwise
 * apply to the ASSET DOWNLOAD instead, which is just as bad a first
 * impression: 14.2MB of WASM behind a spinner after the click).
 * MicVAD.new() never calls getStream() -- that only happens inside
 * `.start()` (verified against the installed 0.0.31 source), which is
 * exactly the boundary this split relies on: constructing here is mic-free,
 * and the returned TurnDetector.start() is where getUserMedia actually
 * fires. Throws on anything that should surface as F1/F2 (asset load
 * failure) -- the caller (App.tsx) renders that as the `unavailable` state.
 */
export async function createTurnDetector(
  audioContext: AudioContext,
  callbacks: TurnDetectorCallbacks,
): Promise<TurnDetector> {
  await assertVadAssets();

  let speaking = false;
  let lastSpeechFrameAt = 0;
  let utteranceTimer: number | undefined;

  // Referenced by `onSpeechStart` below, before `vad` itself is assigned --
  // valid because the closure only ever RUNS after MicVAD.new() resolves
  // and .start() is called (VAD callbacks can't fire before then), by
  // which point `vad` is a normal `const` a few lines down.
  async function forceEndpointAfter30s(): Promise<void> {
    // F7, client half: Whisper's 30s window is hard. `submitUserSpeechOnPause`
    // (set below) makes pause() emit whatever's been buffered as a real
    // onSpeechEnd instead of discarding it; start() right after resumes
    // listening -- pauseStream/resumeStream are no-ops (see below), so
    // this never touches the actual microphone track.
    console.warn("sarjy: utterance exceeded 30s, forcing endpoint");
    await vad.pause();
    await vad.start();
  }

  const vad = await MicVAD.new({
    audioContext,
    // Not eagerly resolved: getStream() is only ever CALLED from inside
    // vad.start() (the whole point of the page-load/click split above), and
    // getSharedMicStream() is the single-flight cache -- calling it here
    // again on the forced-30s resume below returns the SAME stream instead
    // of prompting a second time. NotAllowedError/NotFoundError propagate
    // out of start() untouched.
    getStream: () => getSharedMicStream(),
    // vad-web's defaults call track.stop() (pauseStream) and re-prompt via
    // a fresh getUserMedia (resumeStream) -- either would kill the shared
    // mic mid-conversation. No-ops instead: the VAD must keep listening
    // while Sarjy's own audio plays, or barge-in has nothing to detect.
    pauseStream: async () => {
      /* no-op */
    },
    resumeStream: () => getSharedMicStream(),
    startOnLoad: false, // .start() is called by App.tsx's Start click handler, never here
    processorType: "AudioWorklet", // ScriptProcessor is deprecated and main-thread
    model: "v5", // 512-sample (32ms) frames -- 3x finer than legacy's 96ms
    redemptionMs: getRedemptionMs(),
    submitUserSpeechOnPause: true, // makes the 30s forced cutoff above possible
    baseAssetPath: VAD_ASSET_BASE,
    onnxWASMBasePath: VAD_ASSET_BASE,
    ortConfig: (ort) => {
      // No SharedArrayBuffer without cross-origin isolation -- the threaded
      // build falls back anyway; pinning this removes a worker-spawn path
      // that can fail obscurely instead of just being slightly slower.
      ort.env.wasm.numThreads = 1;
      ort.env.logLevel = "warning";
    },
    onFrameProcessed: (probs) => {
      // The endpointing instrument (task 14): the term that matters is
      // acoustic-end-of-speech -> onSpeechEnd firing, not speech-start ->
      // speech-end (which includes the utterance itself).
      if (probs.isSpeech > POSITIVE_SPEECH_THRESHOLD) lastSpeechFrameAt = performance.now();
    },
    onSpeechStart: () => {
      window.clearTimeout(utteranceTimer);
      utteranceTimer = window.setTimeout(() => void forceEndpointAfter30s(), MAX_UTTERANCE_MS);
      callbacks.onSpeechStart();
    },
    onSpeechRealStart: () => {
      // Fires only after minSpeechMs of CONFIRMED speech -- exactly the
      // anti-self-interrupt primitive barge-in needs (docs/plans/blocks/02-voice-loop.md,
      // "Barge-in", point 1).
      if (speaking && BARGE_IN_ENABLED) callbacks.onBargeDetected();
    },
    onSpeechEnd: (audio: Float32Array) => {
      window.clearTimeout(utteranceTimer);
      const endMs = performance.now();
      const endpointDelayMs = endMs - lastSpeechFrameAt;
      // Kept even though the value now also travels in EndpointTiming --
      // this is what makes the endpointing sweep (block plan §"The
      // endpointing sweep") runnable by ear, with the console open, no UI
      // build needed between trials.
      console.log(
        `sarjy: endpoint delay ${endpointDelayMs.toFixed(0)}ms ` +
          `(redemptionMs=${getRedemptionMs()}, segment=${((audio.length / TARGET_SAMPLE_RATE) * 1000).toFixed(0)}ms)`,
      );
      callbacks.onUtterance(
        floatToPCM16(audio),
        TARGET_SAMPLE_RATE,
        (audio.length / TARGET_SAMPLE_RATE) * 1000,
        {
          endpointMs: Math.round(endpointDelayMs),
          acousticEndAtMs: lastSpeechFrameAt,
          redemptionMs: getRedemptionMs(),
        },
      );
    },
    onVADMisfire: () => {
      callbacks.onMisfire();
    },
  });

  return {
    // Deliberately not called here -- see this function's own doc comment.
    // The caller invokes this from inside the Start button's click handler.
    start() {
      return vad.start();
    },
    setSpeaking(isSpeaking: boolean) {
      speaking = isSpeaking;
    },
    async destroy() {
      window.clearTimeout(utteranceTimer);
      await vad.destroy();
    },
  };
}
