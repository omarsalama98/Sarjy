/**
 * Capture worklet: forwards each input frame to the main thread.
 *
 * Runs off the main thread (browser-audio.md). The recorder downsamples
 * to 16 kHz PCM16 and streams the bytes -- this processor only copies.
 */
class PcmCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel && channel.length > 0) {
      this.port.postMessage(Float32Array.from(channel));
    }
    return true;
  }
}

registerProcessor("pcm-capture", PcmCaptureProcessor);
