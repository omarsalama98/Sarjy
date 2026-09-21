/**
 * User-controlled capture: tap to start, tap to send. No VAD, no hold-to-talk.
 *
 * The worklet copies Float32 frames off the audio thread; this class
 * downsamples to 16 kHz PCM16 and streams binary as it arrives so the
 * server is already buffering when the user taps to send -- no post-endpoint
 * upload burst.
 *
 * 30 s is a hard cap (Whisper's window / MAX_TURN_BYTES). Hitting it
 * end()s the turn the same way a tap would.
 */

import { floatToPCM16, getSharedMicStream, TARGET_SAMPLE_RATE } from "./capture";

export const MAX_UTTERANCE_MS = 30_000;
const MAX_TURN_BYTES = 30 * TARGET_SAMPLE_RATE * 2;

const workletsLoaded = new WeakSet<AudioContext>();

export interface RecorderCallbacks {
  onChunk: (pcm: ArrayBuffer) => void;
  onAutoStop: () => void;
}

export class MicRecorder {
  private node: AudioWorkletNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private recording = false;
  private samplesOut = 0;
  private bytesSent = 0;
  private capTimer: number | null = null;
  private residual: Float32Array = new Float32Array(0);
  private startedAtMs = 0;

  constructor(
    private readonly ctx: AudioContext,
    private readonly callbacks: RecorderCallbacks,
  ) {}

  get isRecording(): boolean {
    return this.recording;
  }

  get sampleCount(): number {
    return this.samplesOut;
  }

  /** Wall-clock ms from start() to now -- becomes client_timing.endpoint_ms
   * (user-ended, not VAD redemption). Zero by construction at the instant
   * of start; the useful number is how long they held. */
  get elapsedMs(): number {
    return this.startedAtMs === 0 ? 0 : Math.round(performance.now() - this.startedAtMs);
  }

  async start(): Promise<void> {
    if (this.recording) return;
    if (this.ctx.state !== "running") {
      await this.ctx.resume();
    }
    const stream = await getSharedMicStream();
    if (!workletsLoaded.has(this.ctx)) {
      await this.ctx.audioWorklet.addModule(
        new URL("/pcm-capture.worklet.js", window.location.origin).href,
      );
      workletsLoaded.add(this.ctx);
    }

    this.source = this.ctx.createMediaStreamSource(stream);
    this.node = new AudioWorkletNode(this.ctx, "pcm-capture");
    this.node.port.onmessage = (ev: MessageEvent<Float32Array>) => {
      if (!this.recording) return;
      this.ingest(ev.data);
    };
    this.source.connect(this.node);
    // Not connected to destination -- the user never hears themselves.

    this.recording = true;
    this.samplesOut = 0;
    this.bytesSent = 0;
    this.residual = new Float32Array(0);
    this.startedAtMs = performance.now();
    this.capTimer = window.setTimeout(() => {
      console.warn("sarjy: utterance exceeded 30s, forcing endpoint");
      this.callbacks.onAutoStop();
    }, MAX_UTTERANCE_MS);
  }

  stop(): { samples: number; elapsedMs: number } {
    const samples = this.samplesOut;
    const elapsedMs = this.elapsedMs;
    this.recording = false;
    if (this.capTimer !== null) {
      window.clearTimeout(this.capTimer);
      this.capTimer = null;
    }
    this.flushResidual();
    this.node?.port.postMessage(undefined);
    this.node?.disconnect();
    this.source?.disconnect();
    this.node = null;
    this.source = null;
    this.startedAtMs = 0;
    return { samples, elapsedMs };
  }

  async destroy(): Promise<void> {
    this.stop();
  }

  private ingest(frame: Float32Array): void {
    const inputRate = this.ctx.sampleRate;
    const combined = new Float32Array(this.residual.length + frame.length);
    combined.set(this.residual);
    combined.set(frame, this.residual.length);

    const ratio = inputRate / TARGET_SAMPLE_RATE;
    const outCount = Math.floor(combined.length / ratio);
    if (outCount === 0) {
      this.residual = combined;
      return;
    }

    const down = new Float32Array(outCount);
    for (let i = 0; i < outCount; i++) {
      const src = i * ratio;
      const lo = Math.floor(src);
      const hi = Math.min(lo + 1, combined.length - 1);
      const frac = src - lo;
      down[i] = combined[lo]! * (1 - frac) + combined[hi]! * frac;
    }
    const consumed = Math.floor(outCount * ratio);
    this.residual = combined.slice(consumed);

    this.emit(down);
  }

  private flushResidual(): void {
    if (this.residual.length === 0) return;
    this.emit(this.residual);
    this.residual = new Float32Array(0);
  }

  private emit(samples: Float32Array): void {
    if (samples.length === 0) return;
    const pcm = floatToPCM16(samples);
    if (this.bytesSent + pcm.byteLength > MAX_TURN_BYTES) {
      this.callbacks.onAutoStop();
      return;
    }
    this.bytesSent += pcm.byteLength;
    this.samplesOut += samples.length;
    this.callbacks.onChunk(pcm);
  }
}
