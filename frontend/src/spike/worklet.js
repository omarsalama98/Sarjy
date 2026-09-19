// Block 0 spike (S5): accumulate 128-frame render quanta into fixed-size
// frames, float32 -> int16 PCM, post to the main thread.
//
// DELETE AFTER BLOCK 2 lifts the resampler this spike verified. Not
// production code -- see docs/plans/blocks/00-spikes.md S5.
//
// Assumes the AudioContext driving this worklet was constructed as
// `new AudioContext({ sampleRate: 16000 })`, so the browser/OS has already
// resampled the mic input by the time it reaches `process()` -- this
// worklet only frames and converts format, it does not resample.

// 20ms @ 16kHz = 320 samples/frame: a standard speech frame size. Small
// enough to keep latency low, large enough not to spam postMessage on
// every single 128-sample render quantum (~2.7ms at 48kHz native rate).
const FRAME_SAMPLES = 320;

class PCM16Worklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buf = new Float32Array(0);
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const channel = input[0]; // mono
    if (!channel || channel.length === 0) return true;

    const merged = new Float32Array(this._buf.length + channel.length);
    merged.set(this._buf, 0);
    merged.set(channel, this._buf.length);

    let offset = 0;
    while (merged.length - offset >= FRAME_SAMPLES) {
      const frame = merged.subarray(offset, offset + FRAME_SAMPLES);
      const int16 = new Int16Array(FRAME_SAMPLES);
      for (let i = 0; i < FRAME_SAMPLES; i++) {
        const s = Math.max(-1, Math.min(1, frame[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      // Transfer the buffer -- no copy across the worklet/main-thread boundary.
      this.port.postMessage({ pcm16: int16.buffer }, [int16.buffer]);
      offset += FRAME_SAMPLES;
    }
    this._buf = merged.subarray(offset);
    return true;
  }
}

registerProcessor("pcm16-worklet", PCM16Worklet);
