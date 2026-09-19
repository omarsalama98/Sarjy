/**
 * Block 0 spike (S5): does capture -> 16 kHz PCM16 -> playback work on this
 * machine? Three independent sections, each answering one or two of the
 * five checks in docs/plans/blocks/00-spikes.md S5 (C1-C5).
 *
 * DELETE AFTER BLOCK 2 lifts the resampler. This is diagnostic, not
 * production code -- see .claude/rules/voice/browser-audio.md for the
 * rules it exists to verify.
 *
 * Section A -- capture -> resample -> playback round trip     (C1, C2, C5)
 * Section B -- loopback through speakers, for echo cancellation (C3)
 * Section C -- VAD speech-start/speech-end timing               (C4)
 */

import { MicVAD, utils as vadUtils } from "@ricky0123/vad-web";

const SAMPLE_RATE = 16_000;

// ---------- tiny DOM + logging helpers ----------

function qs<T extends HTMLElement>(id: string): T {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing #${id}`);
  return el as T;
}

const logEl = qs<HTMLPreElement>("log");
const t0 = performance.now();

function log(line: string): void {
  const t = ((performance.now() - t0) / 1000).toFixed(3);
  logEl.textContent += `[t=${t}s] ${line}\n`;
  logEl.scrollTop = logEl.scrollHeight;
  // eslint-disable-next-line no-console
  console.log(`[t=${t}s]`, line);
}

function setState(s: string): void {
  qs<HTMLSpanElement>("state").textContent = s;
}

function download(bytes: ArrayBuffer, filename: string): void {
  const blob = new Blob([bytes], { type: "audio/wav" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
  log(`downloaded ${filename} (${bytes.byteLength} bytes) -- save it under scratch/spikes/out/`);
}

/** Own writer for Int16 capture (Section A/B) -- avoids a float round-trip
 * through vad-web's encodeWAV, which is used directly in Section C instead
 * since MicVAD already hands back Float32Array. Same header shape either way. */
function int16ToWav(samples: Int16Array, sampleRate: number): ArrayBuffer {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buf);
  const writeStr = (offset: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) view.setInt16(44 + i * 2, samples[i]!, true);
  return buf;
}

// ---------- shared capture context (Sections A & B) ----------
//
// One AudioContext, constructed AT 16kHz -- the browser resamples the mic
// input to this rate before any node (including the worklet) sees it. This
// is the "new AudioContext({ sampleRate: 16000 })" option named in the
// plan, chosen over a hand-rolled resampler: fewer moving parts, and it's
// the browser's own (presumably better-tested) resampling code, not ours.
let captureCtx: AudioContext | null = null;
let capturedFrames: Int16Array[] = [];
let capturing = false;

async function ensureCaptureGraph(): Promise<AudioContext> {
  if (captureCtx) return captureCtx;

  const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
  // C5: AudioContext starts suspended until a user gesture. This function
  // only ever runs from inside a button click handler, so resume() here IS
  // the gesture-gated resume -- if C5 is broken, ctx.state stays "suspended"
  // and the line below will show it.
  await ctx.resume();
  log(`AudioContext created, sampleRate=${ctx.sampleRate}, state=${ctx.state}`);
  qs<HTMLSpanElement>("ctx-state").textContent = ctx.state;
  ctx.addEventListener("statechange", () => {
    qs<HTMLSpanElement>("ctx-state").textContent = ctx.state;
    log(`AudioContext state -> ${ctx.state}`);
  });

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const track = stream.getAudioTracks()[0]!;
  const settings = track.getSettings();
  // Do not assume 48000 -- log what the track actually reports.
  qs<HTMLSpanElement>("mic-sample-rate").textContent = String(settings.sampleRate ?? "unknown");
  log(`mic track settings: sampleRate=${settings.sampleRate}, echoCancellation=${settings.echoCancellation}`);

  await ctx.audioWorklet.addModule("/src/spike/worklet.js");
  const node = new AudioWorkletNode(ctx, "pcm16-worklet");
  node.port.onmessage = (ev: MessageEvent<{ pcm16: ArrayBuffer }>) => {
    if (!capturing) return;
    capturedFrames.push(new Int16Array(ev.data.pcm16));
  };
  const source = ctx.createMediaStreamSource(stream);
  source.connect(node);
  // Deliberately NOT connected to ctx.destination -- we do not want to hear
  // raw capture live (that would be its own feedback loop independent of
  // the echo-cancellation question Section B asks).

  captureCtx = ctx;
  return ctx;
}

function concatFrames(frames: Int16Array[]): Int16Array {
  const total = frames.reduce((n, f) => n + f.length, 0);
  const out = new Int16Array(total);
  let offset = 0;
  for (const f of frames) {
    out.set(f, offset);
    offset += f.length;
  }
  return out;
}

async function playInt16(ctx: AudioContext, samples: Int16Array): Promise<void> {
  const float = new Float32Array(samples.length);
  for (let i = 0; i < samples.length; i++) float[i] = samples[i]! / (samples[i]! < 0 ? 0x8000 : 0x7fff);
  const buffer = ctx.createBuffer(1, float.length, SAMPLE_RATE);
  buffer.getChannelData(0).set(float);
  const src = ctx.createBufferSource();
  src.buffer = buffer;
  src.connect(ctx.destination);
  src.start();
  await new Promise<void>((resolve) => {
    src.onended = () => resolve();
  });
}

// ---------- Section A: capture -> resample -> playback round trip ----------

qs<HTMLButtonElement>("a-start").addEventListener("click", async () => {
  const ctx = await ensureCaptureGraph();
  capturedFrames = [];
  capturing = true;
  setState("listening (section A)");
  qs<HTMLButtonElement>("a-start").disabled = true;
  qs<HTMLButtonElement>("a-stop").disabled = false;
  log("Section A: recording started -- say a sentence, then click Stop.");
  void ctx; // ctx already stored in captureCtx; kept local for clarity above
});

qs<HTMLButtonElement>("a-stop").addEventListener("click", () => {
  capturing = false;
  setState("idle");
  qs<HTMLButtonElement>("a-start").disabled = false;
  qs<HTMLButtonElement>("a-stop").disabled = true;
  const seconds = concatFrames(capturedFrames).length / SAMPLE_RATE;
  qs<HTMLButtonElement>("a-play").disabled = capturedFrames.length === 0;
  qs<HTMLButtonElement>("a-download").disabled = capturedFrames.length === 0;
  log(`Section A: recording stopped, ${seconds.toFixed(2)}s captured.`);
});

qs<HTMLButtonElement>("a-play").addEventListener("click", async () => {
  if (!captureCtx || capturedFrames.length === 0) return;
  setState("speaking (section A playback)");
  log("Section A: playing back through AudioBufferSourceNode (not <audio>)...");
  await playInt16(captureCtx, concatFrames(capturedFrames));
  setState("idle");
  log("Section A: playback finished. C1/C2: was it intelligible?");
});

qs<HTMLButtonElement>("a-download").addEventListener("click", () => {
  if (capturedFrames.length === 0) return;
  download(int16ToWav(concatFrames(capturedFrames), SAMPLE_RATE), "s5-roundtrip.wav");
});

// ---------- Section B: loopback / echo-cancellation check ----------
//
// Plays a fixed tone through the SAME AudioContext's destination (speakers)
// while capture is running, and saves what was captured during that window.
// C3 requires SPEAKERS, not headphones -- echo cancellation has nothing to
// cancel if the mic can't physically hear the speakers.

function makeToneBuffer(ctx: AudioContext, seconds: number, freq: number): AudioBuffer {
  const buffer = ctx.createBuffer(1, Math.floor(seconds * SAMPLE_RATE), SAMPLE_RATE);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < data.length; i++) {
    data[i] = 0.4 * Math.sin((2 * Math.PI * freq * i) / SAMPLE_RATE);
  }
  return buffer;
}

qs<HTMLButtonElement>("b-run").addEventListener("click", async () => {
  const ctx = await ensureCaptureGraph();
  const btn = qs<HTMLButtonElement>("b-run");
  btn.disabled = true;
  qs<HTMLSpanElement>("b-status").textContent = "playing test tone through speakers + capturing...";
  log("Section B: playing a 2s, 440Hz tone through the speakers while capturing. Use SPEAKERS, not headphones.");

  capturedFrames = [];
  capturing = true;
  const tone = makeToneBuffer(ctx, 2, 440);
  const src = ctx.createBufferSource();
  src.buffer = tone;
  src.connect(ctx.destination);
  src.start();
  await new Promise<void>((resolve) => {
    src.onended = () => resolve();
  });
  capturing = false;

  qs<HTMLSpanElement>("b-status").textContent = "done -- download and listen for the tone leaking into capture";
  qs<HTMLButtonElement>("b-download").disabled = capturedFrames.length === 0;
  btn.disabled = false;
  log("Section B: capture during playback finished. C3: does the saved clip contain the tone? It should NOT if echo cancellation is working.");
});

qs<HTMLButtonElement>("b-download").addEventListener("click", () => {
  if (capturedFrames.length === 0) return;
  download(int16ToWav(concatFrames(capturedFrames), SAMPLE_RATE), "s5-echo-test.wav");
});

// ---------- Section C: VAD ----------

let vad: MicVAD | null = null;
let speechStartT = 0;
let lastSpeechAudio: Float32Array | null = null;

qs<HTMLButtonElement>("c-start").addEventListener("click", async () => {
  const redemptionMs = Number(qs<HTMLInputElement>("c-redemption-ms").value) || 600;
  qs<HTMLButtonElement>("c-start").disabled = true;
  qs<HTMLButtonElement>("c-stop").disabled = false;
  setState("listening (VAD)");
  log(`Section C: starting MicVAD, redemptionMs=${redemptionMs} (default library value is 1400ms -- overridden to match the TDD's ~600ms latency-budget assumption; C4 measures whether that holds).`);

  vad = await MicVAD.new({
    redemptionMs,
    processorType: "AudioWorklet", // never ScriptProcessor -- see .claude/rules/voice/browser-audio.md
    onSpeechStart: () => {
      speechStartT = performance.now();
      setState("speaking detected (VAD)");
      log("VAD: onSpeechStart");
    },
    onSpeechEnd: (audio: Float32Array) => {
      const delayMs = performance.now() - speechStartT;
      lastSpeechAudio = audio;
      setState("listening (VAD)");
      qs<HTMLButtonElement>("c-download-last").disabled = false;
      log(
        `VAD: onSpeechEnd -- segment ${(audio.length / SAMPLE_RATE).toFixed(2)}s, ` +
          `speech-start-to-speech-end wall time ${delayMs.toFixed(0)}ms ` +
          `(includes redemptionMs=${redemptionMs} of trailing silence -- this whole number, ` +
          `not just redemptionMs alone, is what C4 asks us to measure and carry into Block 2).`,
      );
    },
    onVADMisfire: () => {
      log("VAD: onVADMisfire (segment shorter than minSpeechMs -- treated as noise, not a turn). Good: this is what should happen for a short 'mhm'.");
    },
  });
  await vad.start();
});

qs<HTMLButtonElement>("c-stop").addEventListener("click", async () => {
  if (vad) {
    await vad.pause();
  }
  qs<HTMLButtonElement>("c-start").disabled = false;
  qs<HTMLButtonElement>("c-stop").disabled = true;
  setState("idle");
  log("Section C: VAD paused.");
});

qs<HTMLButtonElement>("c-download-last").addEventListener("click", () => {
  if (!lastSpeechAudio) return;
  const wav = vadUtils.encodeWAV(lastSpeechAudio, 1, SAMPLE_RATE, 1, 16);
  download(wav, "s5-vad-segment.wav");
});

log("Ready. Sections are independent -- see the on-page instructions for C1-C5.");
