Conversational voice systems decide that a user has finished speaking through **turn detection** (also called endpointing or end-of-utterance detection), a multi-stage process that balances two competing risks: interrupting a mid-thought pause versus waiting through dead air. The choice of turn detector—energy-based VAD, neural VAD, semantic endpointing, or integrated ASR-based signals—directly determines whether your agent feels snappy or sluggish. [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)

## Energy-Based VAD vs. Neural VAD (Silero)

### Energy-Based VAD

**Energy-based VAD** measures the root-mean-square (RMS) energy of each audio frame (typically 10–30 ms) and compares it against an adaptive noise floor. Frames above threshold are labeled speech; frames below are silence. [callmissed](https://www.callmissed.com/blog/vad-and-endpointing-why-your-voice-agent-feels-slow-and-how-to-fix-it)

**Limitations:**
- Fails in noisy environments (TV, café, keyboard clicks) where background energy exceeds speech energy
- Cannot distinguish human speech from other loud sounds (door slams, music)
- High false-positive rate in telephony (G.711 μ-law narrowband) due to codec artifacts [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf)

### Neural VAD (Silero)

**Neural VAD** (e.g., Silero VAD v5) replaces hand-crafted energy thresholds with a recurrent neural network trained on thousands of hours of labeled speech across languages, accents, and noise conditions. The model outputs a per-frame speech probability \(P(\text{speech}) \in [0, 1]\). [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf)

**Advantages:**
- Detects speech in <15 ms with high robustness to non-speech noise
- Learns vocal formant resonances (F1, F2, F3) and pitch harmonics (F0), rejecting sirens, dogs, typing [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf)
- Silero v5 achieves ~87.7% speech detection at 5% false-positive rate vs. ~63% for WebRTC GMM energy filter [aclanthology](https://aclanthology.org/2025.emnlp-main.1266.pdf)

| VAD Type | Technical Basis | Latency | Noise Robustness | False Trigger Rate |
|----------|-----------------|---------|------------------|-------------------|
| Energy-based (WebRTC legacy) | RMS energy + spectral flatness | <1 ms | Low | 24.5%  [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf) |
| Neural (Silero v5) | RNN on mel-spectrogram | 1–5 ms | High | 6.8%  [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf) |

## Silence-Threshold Approach and the 500–700 ms Latency Tax

The **silence-threshold approach** waits for a fixed duration of continuous silence (e.g., 500 ms) before declaring end-of-turn. This is the default in most production STT APIs and voice pipelines. [autointerviewai](https://www.autointerviewai.com/blog/what-is-turn-taking-vad-in-voice-ai-interruptions-2026)

**Why 500–700 ms is a large fraction of the latency budget:**

| Pipeline Stage | Typical Latency (P50) |
|----------------|----------------------|
| VAD end-of-speech hold | **300–700 ms** (configurable)  [dev](https://dev.to/lenajhoffmann/barge-in-vad-and-the-latency-budget-engineering-realtime-voice-3i1b) |
| ASR streaming first partial | 100–300 ms  [hamming](https://hamming.ai/resources/voice-ai-latency-whats-fast-whats-slow-how-to-fix-it) |
| LLM time-to-first-token | 200–600 ms  |
| TTS time-to-first-audio | 75–300 ms  |
| **Total** | **675–1,900 ms** |

At 500 ms silence threshold, VAD endpointing alone consumes **30–50% of a sub-1-second latency budget**, leaving insufficient margin for ASR, LLM, and TTS. [autointerviewai](https://www.autointerviewai.com/blog/what-is-turn-taking-vad-in-voice-ai-interruptions-2026)

**The 200 ms human baseline:** In natural human conversation, the average gap between turns is ~200 ms (Stivers et al., PNAS 2009). A 500 ms silence threshold is **2.5× the human baseline**, making agents feel sluggish even if downstream stages are fast. [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)

## Semantic Turn Detection

**Semantic turn detection** (semantic VAD, semantic endpointing) predicts end-of-turn from linguistic content rather than silence duration alone. It answers: *"Has the speaker finished a complete thought?"* instead of *"Has there been N ms of silence?"* [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)

### How It Works

Semantic VAD analyzes:
- **Syntactic completeness**: Does the partial transcript end mid-clause ("I want to...") or at a grammatical boundary ("I want to book a flight.")? [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)
- **Intonation contours**: Falling pitch (F0 downdrift) signals completion; level/rising pitch signals continuation [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf)
- **Filler words and hesitations**: "um", "uh", "let me think" extend the pause threshold dynamically [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)
- **Question-answer adjacency pairs**: A question ("What's my balance?") implies an expected response, triggering faster endpointing [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)

### Multi-Horizon Inactivity Prediction

Modern semantic VAD (e.g., Gradium STT) emits a **multi-horizon inactivity forecast** every 80 ms: an array of probabilities that the user will remain silent over the next 0.5, 1, 2, or 3 seconds. The agent reads whichever horizon matches its reactivity needs. [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)

```
vad: [0.12, 0.35, 0.68, 0.89]  # P(inactive over 0.5s, 1s, 2s, 3s)
```

This allows:
- **Snappy assistants**: Read `vad [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)` (0.5s horizon) at threshold 0.30 → commit after 1–2 high-confidence frames [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)
- **Noisy telephony**: Read `vad [autointerviewai](https://www.autointerviewai.com/blog/what-is-turn-taking-vad-in-voice-ai-interruptions-2026)` (3s horizon) at threshold 0.60 + require 3 consecutive high frames → robust to codec artifacts [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)

### Latency Impact

Semantic VAD reduces endpointing latency from 500 ms to **100–200 ms** without increasing interruption rate, because it distinguishes hesitation pauses from true turn endings. [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)

## Integrated ASR-Based End-of-Turn Signals

Some systems integrate turn detection directly into the ASR model. The ASR emits an **end-of-turn (EOT) flag** alongside partial transcripts, trained jointly on transcription and turn-completion prediction. [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)

**Advantages:**
- Zero additional model in the turn-detection loop: EOT signal comes from the same forward pass as the transcript [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)
- Context-aware: ASR has already seen the full acoustic context, so EOT is more accurate than a separate VAD [gradium](https://gradium.ai/content/how-to-connect-tts-to-llm-voice-pipeline)

**Example**: Gradium STT integrates semantic VAD natively, emitting `vad` arrays in the same WebSocket stream as transcripts. No separate endpointing component is needed. [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)

## The Fundamental Trade-Off: Cutting Off vs. Making Them Wait

Turn detection faces an **unavoidable precision-recall trade-off**:

| Setting | Effect |
|---------|--------|
| **Low silence threshold (200–300 ms)** | Fast responses, but high interruption rate (cuts users off mid-thought)  [dev](https://dev.to/lenajhoffmann/barge-in-vad-and-the-latency-budget-engineering-realtime-voice-3i1b) |
| **High silence threshold (800–1,200 ms)** | Fewer interruptions, but every turn carries 500+ ms of dead air → agent feels slow  [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026) |

**Why no single threshold works:** A 400 ms pause mid-sentence ("I'd like to book a flight to... uh... Lisbon") is acoustically identical to a 400 ms pause at sentence end. Silence duration alone cannot distinguish hesitation from completion. [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)

### Production Tuning Strategies

| Use Case | Silence Threshold | Min Speech Duration | Consecutive High Frames | Notes |
|----------|-------------------|---------------------|-------------------------|-------|
| Snappy assistant, clean audio | 200–300 ms | 500 ms | 1 | Aggressive; risk of interruptions  [dev](https://dev.to/lenajhoffmann/barge-in-vad-and-the-latency-budget-engineering-realtime-voice-3i1b) |
| Default conversational agent | 400–500 ms | 800 ms | 1–2 | Balanced; industry default  [dev](https://dev.to/lenajhoffmann/barge-in-vad-and-the-latency-budget-engineering-realtime-voice-3i1b) |
| Phone IVR, noisy channels | 600–800 ms | 1,000 ms | 3 | Conservative; tolerates codec artifacts  [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026) |
| Semantic VAD enabled | 100–200 ms (effective) | N/A | 1–2 high-confidence horizons | Reduces dead air without increasing interruptions  [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026) |

**Dynamic tuning:** Some systems adjust thresholds per user (fast talkers vs. slow thinkers) or per dialog state (open-ended questions → longer threshold; yes/no questions → shorter threshold). [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)

## Backchannels ("mhm", "yeah") and Why They Must Not Trigger a Turn

**Backchannels** are short listener responses ("mhm", "yeah", "I see", "right") that signal active listening **without seizing the conversational floor**. In human conversation, backchannels occur ~2–4 times per minute and are essential for natural flow. [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf)

### Why Backchannels Are Problematic for VAD

- **Acoustically identical to turns**: "mhm" is 200–400 ms of speech, indistinguishable from a short turn ("yes") to energy-based VAD [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf)
- **If misclassified as turn**: Agent stops speaking, waits for user response → awkward pause, or responds prematurely to a non-question [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf)

### How Production Systems Handle Backchannels

1. **Duration filtering**: Ignore speech segments <300 ms unless followed by silence >800 ms [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf)
2. **Lexical classification**: Train a classifier to detect backchannel words/phrases ("mhm", "uh-huh", "got it") and suppress turn detection [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf)
3. **Prosodic cues**: Backchannels have flat or rising pitch contour (not falling like turn-yielding statements) [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf)
4. **Semantic VAD**: Recognizes that "mhm" after agent's explanation is not a complete thought requiring response [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)

**Example**: User says "mhm" while agent explains a refund policy. Semantic VAD sees no syntactic completion, no falling pitch, no question structure → continues agent turn without pause. [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)

## Benchmarks and Key Papers

| System | VAD Architecture | Speech Onset Detection | Barge-In Speed | Accidental Interruption Rate |
|--------|------------------|------------------------|----------------|------------------------------|
| WebRTC Energy VAD | GMM energy filter | 65 ms | 280 ms | 24.5%  [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf) |
| Silero VAD v5 | RNN | 20 ms | 85 ms | 6.8%  [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf) |
| OpenAI Realtime VAD | Server-side audio gating | 40 ms | 120 ms | 4.2%  [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf) |
| Deepgram Flux | Semantic endpointing | 25 ms | 75 ms | 3.6%  [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf) |

**Key references:**
- **Stivers et al. (2009, PNAS)**: "Universals and cultural variation in turn-taking in conversation" — establishes 200 ms average human turn gap [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)
- **Gradium Semantic VAD (2026)**: Multi-horizon inactivity prediction integrated into STT [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)
- **Silero VAD (2021–2026)**: Open-source neural VAD with ONNX runtime [proceedings.iclr](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf)
- **OpenAI Realtime API (2024–2026)**: Semantic VAD mode with function calling [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)

Production systems in 2026 increasingly adopt **hybrid architectures**: acoustic VAD for input gating + semantic VAD for turn completion, achieving sub-500 ms end-to-end latency with human-parity interruption rates. [gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)