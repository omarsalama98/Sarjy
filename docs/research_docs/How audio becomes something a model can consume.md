Modern speech AI represents raw audio through a hierarchy of abstractions: starting from waveforms (raw amplitude samples), moving to mel-spectrograms (time-frequency energy distributions aligned with human hearing), and finally to discrete tokens produced by neural audio codecs or semantic tokenizers. The choice of representation determines everything from model architecture to latency and context limits. [theorempath](https://theorempath.com/topics/audio-language-models)

## Waveform vs. Mel-Spectrogram Representations

**Waveform** is the rawest representation: a 1D sequence of amplitude samples at a fixed sampling rate (typically 16 kHz or 24 kHz for speech). One second of 16 kHz audio contains 16,000 samples. While waveforms preserve all information, they are computationally prohibitive for transformer-based models due to the quadratic cost of self-attention over sequence length. [mbrenndoerfer](https://mbrenndoerfer.com/writing/speech-representations-mel-spectrograms)

**Mel-spectrogram** compresses the waveform into a 2D time-frequency representation:
- Apply Short-Time Fourier Transform (STFT) with overlapping windows (e.g., 25 ms window, 10 ms hop) to get a spectrogram
- Aggregate linear-frequency bins into ~80 triangular filters spaced uniformly on the **mel scale** (perceptually uniform pitch scale)
- Apply log compression to match human loudness perception

This reduces dimensionality from 16,000 samples/sec to ~100 frames/sec × 80 mel bins = 8,000 values/sec, a ~2× compression, but more importantly concentrates phonetically relevant information. [mbrenndoerfer](https://mbrenndoerfer.com/writing/speech-representations-mel-spectrograms)

| Aspect | Waveform | Mel-Spectrogram |
|--------|----------|-----------------|
| Dimensionality | 16,000 values/sec (16 kHz) | ~8,000 values/sec (100 fps × 80 bins) |
| Structure | 1D time series | 2D time-frequency heatmap |
| Phonetic info | Implicit, entangled with pitch/timbre | Explicit spectral envelope |
| Transformer-friendly | No (sequence too long) | Partially (still high frame rate) |
| Used in | Raw end-to-end models (e.g., Wave2Vec 2.0 encoder) | Traditional ASR, Whisper encoder input |

## Neural Audio Codecs and Residual Vector Quantization

Neural audio codecs (EnCodec, SoundStream, DAC) compress audio into **discrete tokens** suitable for language modeling. They share a common architecture: **RVQ-VAE** (Residual Vector Quantized Variational Autoencoder). [forasoft](https://www.forasoft.com/learn/audio-for-video/articles-audio/neural-audio-codecs-lyra-encodec-soundstream)

### RVQ-VAE Architecture

1. **Encoder**: CNN downsamples waveform 2× per layer to 50–75 Hz frame rate
2. **RVQ Bottleneck**: Multiple codebooks quantize residuals hierarchically
3. **Decoder**: Symmetric CNN upsamples back to waveform

**Residual Vector Quantization (RVQ)** works like making change with coins: the first codebook captures coarse structure, the second quantizes the residual error from the first, the third quantizes the residual from the second, and so on. Each added codebook roughly halves reconstruction error. [forasoft](https://www.forasoft.com/learn/audio-for-video/articles-audio/neural-audio-codecs-lyra-encodec-soundstream)

```
Waveform → Encoder → Latent vectors
                    ↓
              Codebook 1: quantize → residual 1
                    ↓
              Codebook 2: quantize residual 1 → residual 2
                    ↓
              Codebook 3: quantize residual 2 → ...
```

This hierarchical quantization lets you trade bitrate for quality by using more or fewer codebooks. EnCodec and SoundStream achieve high fidelity at 1–6 kbps using 4–8 codebooks with vocabulary size 1,024 each. [theorempath](https://theorempath.com/topics/audio-language-models)

## Semantic Tokens vs. Acoustic Tokens

Modern speech models distinguish two token types with complementary roles: [computer](https://www.computer.org/csdl/journal/tp/2026/04/11298521/2cojfroKS0U)

| Property | Semantic Tokens | Acoustic Tokens |
|----------|-----------------|-----------------|
| **Source** | SSL models (HuBERT, w2v-BERT, Whisper encoder) + k-means clustering | Neural codecs (EnCodec, SoundStream, DAC) with RVQ |
| **Content** | Linguistic meaning (phonemes, words) | Full audio: timbre, pitch, prosody, speaker identity, background noise |
| **Token rate** | 25–50 tokens/sec | 50–75 tokens/sec **per codebook** (×4–8 codebooks = 200–600 tokens/sec total) |
| **Vocabulary** | 500–2,000 clusters | 1,024 per codebook |
| **Use case** | Understanding, transcription, planning | Generation, voice cloning, high-fidelity synthesis |
| **Information loss** | Discards paralinguistic details | Near-lossless reconstruction at sufficient bitrate |

**Why both?** Separating semantics from acoustics lets models plan content at low token rate (efficient reasoning) then render acoustic detail at high rate (high fidelity). AudioLM pioneered this two-stage design: coarse semantic tokens guide fine acoustic token generation. [theorempath](https://theorempath.com/topics/audio-language-models)

Hybrid tokenizers (e.g., SpeechTokenizer, MimI in Moshi) decouple semantic and acoustic layers within a single RVQ stack, distilling semantic information into early codebooks while later codebooks carry acoustic residuals. [theorempath](https://theorempath.com/topics/audio-language-models)

## Frame Rates and Token Rates

| Representation | Frame Rate | Token Rate | Tokens per 30-sec clip |
|----------------|------------|------------|------------------------|
| Raw waveform (16 kHz) | 16,000 samples/sec | N/A (continuous) | 480,000 samples |
| Mel-spectrogram | ~100 frames/sec | N/A (continuous features) | 3,000 frames × 80 dims |
| Semantic tokens | 25–50 tokens/sec | 25–50 tokens/sec | 750–1,500 tokens |
| Acoustic tokens (4 codebooks) | 50 tokens/sec | 200 tokens/sec (4 × 50) | 6,000 tokens |
| Acoustic tokens (8 codebooks) | 75 tokens/sec | 600 tokens/sec (8 × 75) | 18,000 tokens |
| Text (English) | N/A | ~4–6 tokens/sec (avg word ~1.3 tokens, ~3 words/sec) | ~120–180 tokens |

Audio token rates are **10–100× higher** than text token rates. A 30-second utterance produces 750–1,500 semantic tokens or 6,000–18,000 acoustic tokens, versus ~150 text tokens for the same content. [theorempath](https://theorempath.com/topics/audio-language-models)

## Why Audio Token Rate Constrains Latency and Context

Audio token rate is the **central bottleneck** for speech-to-speech models because:

1. **Sequence length scales linearly with token rate**: A 1-minute audio clip at 50 tokens/sec = 3,000 tokens; at 400 tokens/sec (8-codebook acoustic) = 24,000 tokens. Transformer attention cost scales quadratically with sequence length, making long contexts computationally prohibitive. [theorempath](https://theorempath.com/topics/audio-language-models)

2. **Context window limits**: Most LLMs support 4K–128K tokens. At 400 tokens/sec, a 128K context covers only ~5 minutes of audio. At 50 tokens/sec (semantic), the same window covers ~40 minutes. This forces architectural tradeoffs: use semantic tokens for long-context understanding, acoustic tokens for short high-fidelity generation. [theorempath](https://theorempath.com/topics/audio-language-models)

3. **Latency = tokens to first output × token generation time**: End-to-end speech models must generate acoustic tokens autoregressively. At 50 tokens/sec output rate, generating 1 second of audio requires 200–600 tokens (4–8 codebooks), taking 4–12 seconds at 50 tokens/sec generation speed unless parallelized. Pipeline architectures (ASR → LLM → TTS) add serialization overhead: LASR + LLLM + LTTS ≈ 1–3 seconds total. [theorempath](https://theorempath.com/topics/audio-language-models)

4. **Streaming constraints**: Real-time conversation requires <200 ms turn-taking gaps. High token rates force models to buffer more audio before generating, increasing latency. MimI codec (Moshi) addresses this by distilling semantics into the first RVQ codebook, enabling a single token stream at ~50 tokens/sec that carries both linguistic and acoustic content. [theorempath](https://theorempath.com/topics/audio-language-models)

### Key Papers

- **SoundStream** (Zeghidour et al., 2021, arXiv:2107.03312): Introduced RVQ to neural audio codecs [theorempath](https://theorempath.com/topics/audio-language-models)
- **EnCodec** (Defossez et al., 2022, arXiv:2210.13438): High-fidelity neural audio compression with RVQ [theorempath](https://theorempath.com/topics/audio-language-models)
- **AudioLM** (Borsos et al., 2022, arXiv:2209.03143): Two-stage semantic + acoustic token generation [theorempath](https://theorempath.com/topics/audio-language-models)
- **Recent Advances in Discrete Speech Tokens** (Guo et al., 2026, IEEE TPAMI): Comprehensive survey of semantic vs. acoustic tokenizers [computer](https://www.computer.org/csdl/journal/tp/2026/04/11298521/2cojfroKS0U)
- **Moshi** (Kyutai, 2024, arXiv:2410.00037): Full-duplex speech model with MimI codec for low-latency dialogue [theorempath](https://theorempath.com/topics/audio-language-models)

The field is converging on hybrid tokenizers that compress semantic information into early RVQ layers while preserving acoustic detail in later layers, enabling single-stream models that balance latency, context, and fidelity. [yudonglee](https://yudonglee.me/codec-explained/)