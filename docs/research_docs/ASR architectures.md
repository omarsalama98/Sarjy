Modern neural ASR architectures fall into three families—**CTC**, **attention-based encoder-decoder**, and **RNN-Transducer (RNN-T)**—each with distinct trade-offs in streaming capability, latency, and accuracy. The choice determines whether your system can stream partials in real-time, how much compute it requires, and whether it supports language control via prompts. [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

## Architecture 1: Connectionist Temporal Classification (CTC)

### Mechanism

CTC predicts a token (or blank) for every audio frame independently, then collapses repeats and removes blanks to produce the final transcript. The loss function sums over all valid alignments between audio frames and output tokens using dynamic programming. [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

**Key assumptions:**
- **Conditional independence**: Each frame's prediction depends only on audio at that frame, not on previous tokens [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)
- **Monotonic alignment**: Output tokens are emitted left-to-right without reordering [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

### Streaming Capability

**Native streaming**: CTC is inherently streaming-friendly because it emits per-frame predictions without waiting for future context. Greedy decoding (argmax per frame) produces text as audio arrives. [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

**Latency characteristics:**
- **Frame-level latency**: 10–20 ms per frame (typical frame shift) [heardright](https://heardright.app/blog/asr-models-explained/)
- **No lookahead required**: Can operate with zero right-context, though accuracy improves with 100–300 ms lookahead [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

### Typical Accuracy

CTC models achieve **6–10% WER** on clean speech (e.g., LibriSpeech), but struggle with:
- Ambiguous homophones ("read" vs. "red") due to weak language modeling [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)
- Rare words and proper nouns without external language model biasing [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

**Accuracy boosters:**
- **Shallow fusion**: Combine CTC scores with external n-gram or neural LM at decode time (λ = 0.1–0.5) [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)
- **Contextual biasing**: Boost expected phrases (contact names, domain terms) in beam search [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

| Property | CTC |
|----------|-----|
| Streaming output | Yes (native)  [heardright](https://heardright.app/blog/asr-models-explained/) |
| Language model | Weak (conditional independence)  [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/) |
| Latency | 10–20 ms per frame  [heardright](https://heardright.app/blog/asr-models-explained/) |
| Typical WER (LibriSpeech) | 6–10%  [linkedin](https://www.linkedin.com/pulse/anatomy-asr-encoders-decoders-deepikaa-sriram-c2m0e) |
| On-device friendly | Yes (simple greedy decoding)  [heardright](https://heardright.app/blog/asr-models-explained/) |

## Architecture 2: Attention-Based Encoder-Decoder (AED / LAS)

### Mechanism

**Listen, Attend, and Spell (LAS)** models use a bidirectional encoder (LSTM, Conformer, or Transformer) to process the full audio sequence, then an autoregressive decoder attends to encoder states to generate text token-by-token. [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

**Key properties:**
- **Global context**: Decoder attends to all encoder states, capturing long-range dependencies [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)
- **Autoregressive**: Each token conditions on previous tokens via decoder self-attention [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

### Streaming Capability

**Not natively streaming**: The decoder requires the full encoder output before generating the first token. Bidirectional attention means the encoder must see the entire utterance. [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

**Workarounds for pseudo-streaming:**
- **Chunked attention**: Process audio in overlapping 1–2 second chunks with limited right-context (e.g., 500 ms lookahead) [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)
- **Sliding window**: Re-run encoder on rolling 30-second windows, emitting partials from each window [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)
- **Triggered attention**: Use a separate VAD or CTC model to trigger encoder-decoder inference on speech segments [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

### Latency Characteristics

**Batch-oriented**: TTFT (Time to First Token) scales linearly with utterance length because the encoder must process all frames before decoder starts. [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)

| Component | Latency |
|-----------|---------|
| Encoder (30s audio) | 100–300 ms on GPU  [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/) |
| Decoder first token | +50–150 ms  [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/) |
| **Total TTFT (30s utterance)** | **150–450 ms**  [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/) |

### Typical Accuracy

AED models achieve **state-of-the-art accuracy** on offline transcription:
- **Whisper Large v3**: 7.44% WER (Open ASR Leaderboard average) [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)
- **Canary Qwen 2.5B**: 5.63% WER (current SOTA) [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)

**Strengths:**
- Strong language modeling via cross-attention [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)
- Multilingual support (Whisper: 99 languages) [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)
- Prompt-driven language control (e.g., `<|en|>`, `<|translate|>`)  [heardright](https://heardright.app/blog/asr-models-explained/)

| Property | Encoder-Decoder (Whisper) |
|----------|---------------------------|
| Streaming output | No (batch)  [heardright](https://heardright.app/blog/asr-models-explained/) |
| Language control via prompt | Yes  [heardright](https://heardright.app/blog/asr-models-explained/) |
| Translation to English | Yes  [heardright](https://heardright.app/blog/asr-models-explained/) |
| Hallucination risk on silence | Higher  [heardright](https://heardright.app/blog/asr-models-explained/) |
| Typical WER (LibriSpeech) | 3–6%  [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/) |

## Architecture 3: RNN-Transducer (RNN-T)

### Mechanism

RNN-T combines three components:
1. **Encoder (Transcription Network)**: Processes audio frames (similar to CTC encoder) [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)
2. **Prediction Network**: Autoregressive LM that conditions on previously emitted tokens [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)
3. **Joint Network**: Combines encoder and prediction outputs to emit tokens [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

**Key innovation**: The prediction network acts as an **internal language model**, removing CTC's conditional independence assumption while preserving streaming capability. [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

### Streaming Capability

**Native streaming**: RNN-T emits tokens left-to-right as audio arrives, with bounded latency. The model can only move forward in time (monotonic), making it ideal for real-time applications. [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

**Decoding grid**: Imagine a 2D grid where:
- X-axis: Time frames (T)
- Y-axis: Output tokens (U)
- At each step, model can emit token (move up) or blank (move right) [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

### Latency Characteristics

**Frame-synchronous**: Emits tokens every 10–40 ms with internal LM context. Latency is tunable via lookahead:
- **0 ms lookahead**: Lowest latency, but accuracy drops (can't distinguish "The" vs. "A" without future context) [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)
- **100–300 ms lookahead**: Sweet spot for production systems [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)

**Production deployments:**
- **Google Assistant, Apple Siri**: RNN-T with ~200 ms latency [valmera](https://valmera.io/glossary/transcription-and-asr)
- **NVIDIA Parakeet TDT**: RTFx > 2000 on A100 (2,000× faster than real-time) [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)

### Typical Accuracy

RNN-T models achieve **better accuracy than CTC** (due to internal LM) while maintaining streaming:
- **NVIDIA Parakeet TDT 1.1B**: 7.02% WER (Open ASR average) [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)
- **Google's production ASR**: ~5–7% WER on conversational speech [cheatgrid](https://www.cheatgrid.com/generative-ai/0439-speech-to-text-asr-models-cheat-sheet)

| Property | RNN-T / TDT |
|----------|-------------|
| Streaming output | Yes (native)  [heardright](https://heardright.app/blog/asr-models-explained/) |
| Built-in language model | Yes (prediction network)  [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/) |
| Latency | 100–300 ms (tunable)  [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/) |
| Typical WER (LibriSpeech) | 4–7%  [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/) |
| On-device friendly | Yes (streaming, no full attention)  [heardright](https://heardright.app/blog/asr-models-explained/) |

## Whisper Architecture: Why It's Non-Streaming

### Encoder-Decoder with 30-Second Windows

**Whisper** (OpenAI, 2022) is a standard Transformer encoder-decoder trained on 680,000 hours of weakly-labeled web audio. Key design choices: [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)

1. **Fixed 30-second input**: Encoder always processes exactly 30 seconds of audio (padded with silence if shorter) [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)
2. **Bidirectional attention**: Encoder attends to all 30 seconds simultaneously; decoder attends to full encoder output [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)
3. **Autoregressive decoder**: Generates tokens one-by-one, conditioning on all previous tokens [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)

### Why True Streaming Is Difficult

**Fundamental bottleneck**: The decoder cannot start until the encoder finishes processing all 30 seconds. This creates:
- **Linear TTFT growth**: A 2-second utterance still waits for 30 seconds of encoder compute (28 seconds wasted on padding) [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)
- **No incremental output**: Cannot emit partials while user speaks; must buffer entire utterance [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)
- **Hallucination on silence**: Decoder was trained on real audio and generates plausible text for random noise/silence [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)

### Techniques to Approximate Streaming

| Technique | Description | Trade-offs |
|-----------|-------------|------------|
| **Chunked inference** | Split audio into overlapping 5–10 second chunks; run Whisper on each chunk independently  [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/) | Loses long-range context; words at chunk boundaries may be split or dropped |
| **Sliding window** | Process 30-second windows with 5–10 second stride; merge overlapping transcripts  [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/) | Redundant compute (re-processes same audio); latency still 30s per window |
| **Whisper-streaming** | Use CTC or RNN-T front-end to detect speech segments; run Whisper only on detected segments  [yobitel](https://yobitel.com/knowledge-base/whisper) | Adds complexity; still batch-oriented within each segment |
| **Distil-Whisper** | Smaller decoder (4 layers vs. 32) reduces TTFT but preserves encoder accuracy  [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/) | Still non-streaming; just faster batch inference |

**Example**: `whisper.cpp` implements chunked streaming by:
1. Buffering audio into 30-second segments
2. Overlapping adjacent chunks by 1–2 seconds to avoid boundary artifacts
3. Emitting partials after each chunk completes [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)

## Code-Switching Within Single Utterances

### What Is Code-Switching?

**Code-switching (CSW)** is the alternation of languages within a single utterance (e.g., "I need to book a flight *بكره*" mixing English and Arabic). This is common in multilingual societies (India, Middle East, Southeast Asia) but remains a fundamental challenge for ASR. [arxiv](https://arxiv.org/abs/2510.07037)

### Why It's Architecturally Hard

1. **Language ID ambiguity**: Monolingual models assume single language per utterance; CSW violates this assumption [arxiv](https://arxiv.org/abs/2510.07037)
2. **Vocabulary explosion**: Bilingual models need combined vocabulary (e.g., English + Hindi = 100K+ tokens), increasing model size and training data requirements [arxiv](https://arxiv.org/abs/2510.07037)
3. **Acoustic-linguistic mismatch**: Phonemes from language A may be pronounced with language B's prosody, confusing acoustic models [lrec.elra](https://lrec.elra.info/lrec2026-main-768)
4. **LM context switching**: Language models trained on monolingual text struggle to predict code-switched sequences ("I'm going to *المكتب*" → next word could be English or Arabic) [arxiv](https://arxiv.org/abs/2510.07037)

### Modern Approaches

| Approach | Description | Limitations |
|----------|-------------|-------------|
| **Multilingual training** | Train on mixed-language corpora (e.g., Google's Universal Speech Model)  [arxiv](https://arxiv.org/abs/2510.07037) | Requires massive CSW datasets; most public datasets are monolingual |
| **Language-adaptive layers** | Add language-specific adapter modules to shared encoder  [arxiv](https://arxiv.org/abs/2510.07037) | Increases model complexity; requires language tags at inference |
| **CSW-aware LMs** | Train external LMs on code-switched text; use shallow fusion  [arxiv](https://arxiv.org/abs/2510.07037) | Limited CSW text corpora; most web text is monolingual |
| **Token-level language ID** | Predict language ID per token alongside transcription  [lrec.elra](https://lrec.elra.info/lrec2026-main-768) | Adds output dimension; requires token-level language annotations |

**State-of-the-art**: Most production ASR systems (Whisper, Google Cloud STT) handle CSW poorly—WER degrades 20–50% on mixed-language utterances vs. monolingual. [arxiv](https://arxiv.org/abs/2510.07037)

## Architecture Comparison Summary

| Property | CTC | RNN-T / TDT | Encoder-Decoder (Whisper) |
|----------|-----|-------------|---------------------------|
| **Streaming output** | Yes (native)  [heardright](https://heardright.app/blog/asr-models-explained/) | Yes (native)  [heardright](https://heardright.app/blog/asr-models-explained/) | No (batch)  [heardright](https://heardright.app/blog/asr-models-explained/) |
| **Language control via prompt** | No  [heardright](https://heardright.app/blog/asr-models-explained/) | No  [heardright](https://heardright.app/blog/asr-models-explained/) | Yes  [heardright](https://heardright.app/blog/asr-models-explained/) |
| **Translation to English** | No  [heardright](https://heardright.app/blog/asr-models-explained/) | No  [heardright](https://heardright.app/blog/asr-models-explained/) | Yes  [heardright](https://heardright.app/blog/asr-models-explained/) |
| **Built-in language model** | No (needs external LM)  [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/) | Yes (prediction network)  [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/) | Yes (cross-attention)  [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/) |
| **Hallucination risk on silence** | Low  [heardright](https://heardright.app/blog/asr-models-explained/) | Low  [heardright](https://heardright.app/blog/asr-models-explained/) | Higher  [heardright](https://heardright.app/blog/asr-models-explained/) |
| **Typical WER (LibriSpeech)** | 6–10%  [linkedin](https://www.linkedin.com/pulse/anatomy-asr-encoders-decoders-deepikaa-sriram-c2m0e) | 4–7%  [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/) | 3–6%  [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/) |
| **Latency** | 10–20 ms per frame  [heardright](https://heardright.app/blog/asr-models-explained/) | 100–300 ms (tunable)  [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/) | 150–450 ms (30s utterance)  [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/) |
| **On-device friendly** | Yes  [heardright](https://heardright.app/blog/asr-models-explained/) | Yes  [heardright](https://heardright.app/blog/asr-models-explained/) | ⚠️ High-end only  [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/) |
| **Code-switching support** | Poor  [arxiv](https://arxiv.org/abs/2510.07037) | Poor  [arxiv](https://arxiv.org/abs/2510.07037) | Moderate (multilingual training)  [arxiv](https://arxiv.org/abs/2510.07037) |

**Key papers:**
- **CTC**: Graves et al. (2006), "Connectionist Temporal Classification" [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)
- **RNN-T**: Graves (2012), "Sequence Transduction with Recurrent Neural Networks" [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)
- **LAS**: Chan et al. (2015), "Listen, Attend and Spell" [arunbaby](https://arunbaby.com/speech-tech/0027-end-to-end-speech-model-design/)
- **Whisper**: Radford et al. (2022), "Robust Speech Recognition via Large-Scale Weak Supervision" [made-in-jurgistan.github](https://made-in-jurgistan.github.io/mobile-stt-engineering-guide/)
- **Code-switching survey**: LingO-IITGN (2025), "Beyond Monolingual Assumptions: A Survey of Code-Switched NLP" [arxiv](https://arxiv.org/abs/2510.07037)

Production systems in 2026 increasingly use **hybrid architectures**: RNN-T for streaming partials + encoder-decoder for final high-accuracy pass, or multilingual Whisper with language-adaptive layers for CSW handling. [arxiv](https://arxiv.org/abs/2510.07037)