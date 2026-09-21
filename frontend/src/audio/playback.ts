/**
 * Playback: schedule PCM16 chunks into an AudioContext with explicit
 * timing, back to back with no gaps.
 *
 * Never point an <audio> element at a stream -- that gives neither low
 * latency nor clean interruption. Barge-in needs audio to stop NOW: kill
 * every scheduled buffer, don't wait for the current one to drain -- see
 * stop().
 *
 * The AudioContext itself is owned by the caller (App.tsx), constructed at
 * 24 kHz -- Deepgram's native output rate, so there is no resampling on
 * this hot path -- and resumed inside the Start button's click handler
 * (the user gesture Web Audio requires). This class only ever schedules
 * into it.
 */

export class PlaybackQueue {
  private nextStartTime = 0;
  private readonly sources = new Set<AudioBufferSourceNode>();
  private onFirstChunk: (() => void) | null = null;
  private firedFirstChunk = false;

  constructor(private readonly ctx: AudioContext) {}

  /**
   * Called once per turn, when `audio_start` arrives. Arms scheduling fresh
   * and registers the callback that fires the moment a chunk is actually
   * scheduled -- not merely announced. That moment, not `audio_start`
   * itself, is when the UI flips to "speaking" (docs/plans/blocks/02-voice-loop.md,
   * "Who owns which conversation state": `audio_start` only ARMS the queue).
   */
  beginTurn(onFirstChunk: () => void): void {
    this.nextStartTime = this.ctx.currentTime;
    this.onFirstChunk = onFirstChunk;
    this.firedFirstChunk = false;
  }

  enqueue(pcm: ArrayBuffer, sampleRate: number): void {
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

  /** Immediate. Drops every scheduled buffer -- playing or queued -- rather
   * than letting the current one drain. This is what makes barge-in feel
   * instant instead of "interrupts after this sentence." */
  stop(): void {
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
}
