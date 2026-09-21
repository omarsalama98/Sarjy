/**
 * Live audio levels for the orb. Two independent sources, both already
 * in the graph -- we only *read*, we never reroute:
 *
 *   - Mic: an AnalyserNode tapped off the shared MediaStream (the same
 *     one the recorder uses). Not connected to the destination, so the user
 *     never hears themselves.
 *   - TTS: RMS of the Int16 PCM already passing through onAudioChunk.
 *     playback.ts is not touched.
 *
 * The orb's rAF loop samples these. Nothing here calls setState.
 */

export class MicAnalyser {
  private readonly source: MediaStreamAudioSourceNode;
  private readonly analyser: AnalyserNode;
  private readonly data: Uint8Array<ArrayBuffer>;

  constructor(ctx: AudioContext, stream: MediaStream) {
    this.source = ctx.createMediaStreamSource(stream);
    this.analyser = ctx.createAnalyser();
    this.analyser.fftSize = 256;
    this.analyser.smoothingTimeConstant = 0.65;
    this.source.connect(this.analyser);
    this.data = new Uint8Array(this.analyser.fftSize) as Uint8Array<ArrayBuffer>;
  }

  sample(): number {
    this.analyser.getByteTimeDomainData(this.data);
    let sum = 0;
    for (let i = 0; i < this.data.length; i++) {
      const n = (this.data[i]! - 128) / 128;
      sum += n * n;
    }
    return Math.min(1, Math.sqrt(sum / this.data.length) * 3.2);
  }

  disconnect(): void {
    this.source.disconnect();
    this.analyser.disconnect();
  }
}

/** Peak-ish RMS of a PCM16 chunk, scaled so spoken voice reads as ~0.4–0.9. */
export function pcm16Rms(chunk: ArrayBuffer): number {
  const samples = new Int16Array(chunk);
  if (samples.length === 0) return 0;
  let sum = 0;
  for (let i = 0; i < samples.length; i++) {
    const n = samples[i]! / 0x8000;
    sum += n * n;
  }
  return Math.min(1, Math.sqrt(sum / samples.length) * 4);
}
