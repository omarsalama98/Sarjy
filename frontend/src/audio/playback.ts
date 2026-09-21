/**
 * Playback: schedule PCM16 chunks into an AudioContext with explicit
 * timing, back to back with no gaps.
 *
 * Never point an <audio> element at a stream -- that gives neither low
 * latency nor clean interruption. Barge-in needs audio to stop NOW: kill
 * every scheduled buffer, don't wait for the current one to drain -- see
 * stop().
 *
 * The AudioContext itself is owned by the caller (App.tsx). This class
 * schedules into it, resumes it if the browser has suspended it mid-session
 * (backgrounded tab, sleep, output-device change -- the silent-Sarjy bug),
 * and holds chunks that arrived while resume() was in flight so they are
 * not scheduled against a frozen clock.
 *
 * Rules: .claude/rules/voice/browser-audio.md
 */

export type AudioHealth = "ok" | "blocked" | "dead";

export class PlaybackQueue {
  private nextStartTime = 0;
  private readonly sources = new Set<AudioBufferSourceNode>();
  private onFirstChunk: (() => void) | null = null;
  private firedFirstChunk = false;
  private pending: Array<{ pcm: ArrayBuffer; sampleRate: number }> = [];
  private resumeInFlight: Promise<void> | null = null;
  private lastWallMs = 0;
  private lastCtxTime = 0;
  private onHealth: ((health: AudioHealth) => void) | null = null;
  private onDeadClock: (() => void) | null = null;

  constructor(private ctx: AudioContext) {
    this.nextStartTime = ctx.currentTime;
    ctx.onstatechange = () => this.reportState();
  }

  /** App.tsx surfaces this as a header chip so a silent turn cannot look like a success. */
  setHealthListener(onHealth: (health: AudioHealth) => void, onDeadClock: () => void): void {
    this.onHealth = onHealth;
    this.onDeadClock = onDeadClock;
    this.reportState();
  }

  get context(): AudioContext {
    return this.ctx;
  }

  /**
   * Called once per turn, when `audio_start` arrives. Arms scheduling fresh
   * and registers the callback that fires the moment a chunk is actually
   * scheduled -- not merely announced. That moment, not `audio_start`
   * itself, is when the UI flips to "speaking".
   */
  beginTurn(onFirstChunk: () => void): void {
    this.pending = [];
    this.nextStartTime = this.ctx.currentTime;
    this.onFirstChunk = onFirstChunk;
    this.firedFirstChunk = false;
    this.lastWallMs = 0;
    this.lastCtxTime = 0;
    void this.ensureRunning();
  }

  enqueue(pcm: ArrayBuffer, sampleRate: number): void {
    if (this.ctx.state === "closed") {
      this.onHealth?.("dead");
      return;
    }
    if (this.ctx.state !== "running") {
      this.pending.push({ pcm, sampleRate });
      void this.ensureRunning();
      return;
    }
    this.schedule(pcm, sampleRate);
  }

  /** Immediate. Drops every scheduled buffer -- playing or queued -- rather
   * than letting the current one drain. This is what makes barge-in feel
   * instant instead of "interrupts after this sentence." */
  stop(): void {
    this.pending = [];
    for (const source of this.sources) {
      source.onended = null;
      try {
        source.stop(0);
      } catch {
        // Already stopped or never started -- nothing to clean up.
      }
      source.disconnect();
    }
    this.sources.clear();
    this.nextStartTime = this.ctx.currentTime;
  }

  /**
   * User-gesture restore -- the AUDIO chip's click handler. Browsers will
   * not resume a suspended context without a gesture; calling this from
   * onAudioStart (no gesture) can still succeed if the context is merely
   * interrupted, but the chip is the guaranteed path.
   */
  async ensureRunning(): Promise<boolean> {
    if (this.ctx.state === "closed") {
      this.onHealth?.("dead");
      return false;
    }
    if (this.ctx.state === "running") {
      this.flushPending();
      this.onHealth?.("ok");
      return true;
    }
    if (this.resumeInFlight) {
      await this.resumeInFlight;
      const waited: string = this.ctx.state;
      return waited === "running";
    }
    this.resumeInFlight = this.ctx
      .resume()
      .then(() => undefined)
      .catch((err: unknown) => {
        console.warn("sarjy: playback AudioContext resume failed", err);
      })
      .finally(() => {
        this.resumeInFlight = null;
      });
    await this.resumeInFlight;
    const after: string = this.ctx.state;
    if (after === "running") {
      this.flushPending();
      this.onHealth?.("ok");
      return true;
    }
    this.onHealth?.("blocked");
    return false;
  }

  replaceContext(ctx: AudioContext): void {
    this.stop();
    this.ctx.onstatechange = null;
    this.ctx = ctx;
    this.nextStartTime = ctx.currentTime;
    ctx.onstatechange = () => this.reportState();
    this.reportState();
  }

  private flushPending(): void {
    const queued = this.pending.splice(0);
    for (const chunk of queued) {
      this.schedule(chunk.pcm, chunk.sampleRate);
    }
  }

  private schedule(pcm: ArrayBuffer, sampleRate: number): void {
    this.watchClock();

    const int16 = new Int16Array(pcm);
    const float = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      const s = int16[i]!;
      float[i] = s < 0 ? s / 0x8000 : s / 0x7fff;
    }

    const buffer = this.ctx.createBuffer(1, float.length, sampleRate);
    buffer.getChannelData(0).set(float);

    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(this.ctx.destination);

    // Schedule back to back: never earlier than "now" (a chunk that arrived
    // late must not try to play in the past), never earlier than the
    // previous chunk's own end (that's what makes this gapless).
    const startAt = Math.max(this.nextStartTime, this.ctx.currentTime);
    source.start(startAt);
    this.nextStartTime = startAt + buffer.duration;

    this.sources.add(source);
    source.onended = () => this.sources.delete(source);

    if (!this.firedFirstChunk) {
      this.firedFirstChunk = true;
      this.onFirstChunk?.();
    }
  }

  private watchClock(): void {
    const now = performance.now();
    const t = this.ctx.currentTime;
    if (this.lastWallMs > 0 && now - this.lastWallMs > 80 && this.ctx.state === "running") {
      if (t === this.lastCtxTime) {
        // Running, but currentTime has not moved -- the output graph is
        // orphaned (typical after a Bluetooth device switch). Recreate.
        this.onHealth?.("dead");
        this.onDeadClock?.();
      }
    }
    this.lastWallMs = now;
    this.lastCtxTime = t;
  }

  private reportState(): void {
    if (this.ctx.state === "closed") {
      this.onHealth?.("dead");
      return;
    }
    if (this.ctx.state === "running") {
      this.onHealth?.("ok");
      return;
    }
    this.onHealth?.("blocked");
  }
}
