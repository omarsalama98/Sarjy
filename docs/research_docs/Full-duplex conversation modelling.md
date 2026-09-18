Voice AI systems are shifting from **half-duplex turn-taking** (user speaks → agent listens → agent speaks → user listens) to **full-duplex conversation** (both parties can speak and listen simultaneously). This architectural change enables natural overlapping speech, interruptions, and backchannels that characterize human conversation. [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)

## Full-Duplex Architectures: Two Parallel Audio Streams

### Core Innovation: Multi-Stream Token Modeling

The key insight behind full-duplex models like **Moshi** (Kyutai, 2024) is to model conversation as **two simultaneous token streams** rather than one:
- **Stream 1**: User's audio tokens (incoming speech)
- **Stream 2**: Agent's audio tokens (outgoing speech)

Both streams are processed jointly at every timestep (80 ms for Mimi codec), with no explicit turn boundaries. The model learns to coordinate speaking and listening from stereo training data (e.g., telephone conversations with separate left/right channels). [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)

```
Timestep t (80 ms):
  User audio tokens:  [semantic][acoustic_1][acoustic_2]...[acoustic_7]
  Agent audio tokens: [semantic][acoustic_1][acoustic_2]...[acoustic_7]
  
Joint sequence: 17 tokens per timestep (1 text + 8 user audio + 8 agent audio)
```

**Moshi architecture** (7.7B parameters): [aiwiki](https://aiwiki.ai/wiki/moshi)
- **Helium**: 7B-parameter text LLM backbone (32-layer Transformer)
- **Mimi**: Streaming neural audio codec (12.5 Hz, 1.1 kbps, 80 ms latency)
- **RQ-Transformer**: Two-level transformer (Temporal + Depth) predicts 17-token joint sequence per timestep

### Architectural Hierarchy: L0–L3 Duplex Levels

A 2026 survey proposes an **L0–L3 hierarchy** to classify where duplex decisions are made: [alphaxiv](https://www.alphaxiv.org/abs/2606.19453)

| Level | Decision Location | Example Systems | Duplex Capability |
|-------|------------------|-----------------|-------------------|
| **L0 (Module-level)** | External VAD / Dialogue Manager | FireRedChat, FlexDuo | Rule-based interruptions; limited overlap handling  [alphaxiv](https://www.alphaxiv.org/abs/2606.19453) |
| **L1 (Hidden-state-level)** | Sidecar predictor monitors LLM hidden states | MinMo, Freeze-Omni | Learns when to interrupt from internal representations  [alphaxiv](https://www.alphaxiv.org/abs/2606.19453) |
| **L2 (Token-level)** | Duplex decision encoded in token stream | Moshi, LSLM | Native full-duplex; both streams modeled jointly  [aiwiki](https://aiwiki.ai/wiki/moshi) |
| **L3 (Representation-level)** | Continuous latent fusion (theoretical) | None yet | No discrete tokens; fully continuous multi-stream modeling  [alphaxiv](https://www.alphaxiv.org/abs/2606.19453) |

Most production systems in 2026 are **L0** (cascaded with external VAD), while research prototypes like Moshi are **L2** (token-level full-duplex). [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)

## Handling Overlapping Speech, Interruptions, and Backchannels

### Overlapping Speech Classification

Full-duplex systems must distinguish four overlap types with different required responses: [alphaxiv](https://www.alphaxiv.org/abs/2606.19453)

| Overlap Class | User Intent | Expected Agent Behavior |
|---------------|-------------|------------------------|
| **Backchannel** ("mhm", "yeah", "right") | Acknowledgment without taking floor | Continue speaking; do not yield turn  [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad) |
| **Cooperative barge-in** (user completes agent's sentence) | Collaborative completion | Stop speaking; let user finish  [qubittool](https://qubittool.com/blog/voice-conversation-ai-agent-latency-architecture) |
| **Competitive interruption** (user changes topic/corrects) | Floor-claiming; redirect conversation | Yield immediately; process new request  [qubittool](https://qubittool.com/blog/voice-conversation-ai-agent-latency-architecture) |
| **Background speech** (user talking to someone else) | Not addressed to agent | Hold state; ignore without corrupting context  [qubittool](https://qubittool.com/blog/voice-conversation-ai-agent-latency-architecture) |

**Moshi's approach**: The model learns these distinctions implicitly from stereo training data (Fisher corpus, 2,000 hours of telephone conversations). No explicit classifier is needed; the joint token stream encodes both user and agent speech simultaneously. [aiwiki](https://aiwiki.ai/wiki/moshi)

### Backchannels Without Turn Switching

**Backchannels** ("uh-huh", "I see", "go on") are critical for natural conversation but problematic for turn-based systems:
- **Half-duplex failure**: Agent detects "mhm" as speech → triggers end-of-turn → stops speaking → awkward pause [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)
- **Full-duplex solution**: Agent recognizes "mhm" as backchannel (via prosody + lexical cues) → continues speaking uninterrupted [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)

**Moshi training**: Instruction fine-tuning includes 20,000+ hours of synthetic conversations with explicit backchannel examples. The model learns to emit backchannel tokens ("mhm", "yeah") while the user speaks, then resume main response after user finishes. [aiwiki](https://aiwiki.ai/wiki/moshi)

### Interruption Handling (Barge-In)

**Barge-in** occurs when user speaks over agent mid-utterance. Full-duplex systems handle this via: [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)

1. **Continuous listening**: Agent always processes user audio, even while speaking (no VAD gate)
2. **Epoch invalidation**: When interruption detected, invalidate current generation epoch; flush buffered audio
3. **Cooperative cancellation**: Stop TTS playback; cancel LLM generation; preserve context from interruption point
4. **Context recovery**: Resume conversation from last coherent state (not from scratch)

**Moshi's latency**: Theoretical 160 ms (80 ms Mimi frame + 80 ms acoustic delay); practical ~200 ms on L4 GPU. This is **faster than human average** (230 ms across 10 languages), enabling natural interruption timing. [aiwiki](https://aiwiki.ai/wiki/moshi)

## Human Conversation Timing Norms (~200 ms Gap)

### Research on Turn-Taking Latency

Decades of conversation analysis establish that **human turn gaps average 200 ms** across languages: [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)

- **Stivers et al. (2009, PNAS)**: Average gap 208 ms across 10 languages (English, German, Japanese, etc.) [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)
- **Dingemanse & Liesenfeld (2022)**: Gap range 59–200 ms depending on social context [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC12517399/)
- **Levinson (2016)**: Gaps too fast for reactive planning; listeners predict turn completion mid-utterance [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC12517399/)

**Implication for AI**: Agents with >300 ms latency feel sluggish; <150 ms latency feels unnaturally fast (like interrupting). Sweet spot: **160–230 ms** matches human norms. [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)

### Why 200 ms Is the Target

Human conversation relies on **predictive processing**: listeners anticipate turn completion based on:
- **Syntactic cues**: Sentence structure signals approaching end (e.g., subject-verb-object completion) [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)
- **Prosodic cues**: Falling pitch (F0 downdrift) marks declarative completion; rising pitch signals continuation [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)
- **Pragmatic cues**: Question-answer adjacency pairs create expectation of response [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)

AI systems that wait for silence (500–700 ms threshold) miss these predictive signals, creating unnatural delays. Full-duplex models like Moshi achieve 160–200 ms latency by:
- **Streaming codec**: Mimi processes audio in 80 ms frames (vs. 30-second Whisper windows) [aiwiki](https://aiwiki.ai/wiki/moshi)
- **Joint modeling**: No separate VAD → ASR → LLM → TTS handoffs; single forward pass [aiwiki](https://aiwiki.ai/wiki/moshi)

## Production Systems vs. Research Prototypes

### What Production Systems Actually Do (2026)

**Virtually all production voice agents use cascaded half-duplex architecture**: [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)

| System | Architecture | Duplex Level | Latency | Overlap Handling |
|--------|-------------|--------------|---------|------------------|
| **OpenAI Realtime API** | Audio-native LLM (GPT-4o) | L1 (hidden-state predictor) | 232–320 ms  [aiwiki](https://aiwiki.ai/wiki/moshi) | Barge-in detection via VAD; backchannels partially supported  |
| **Google Gemini Live** | Multimodal LLM | L1 | ~300 ms | Interrupts on speech onset; limited backchannel awareness  |
| **ElevenLabs + LLM** | Cascaded (STT + LLM + TTS) | L0 (external VAD) | 600–1,200 ms  | Rule-based barge-in; backchannels trigger false turn ends  [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad) |
| **Gradium STT + LLM** | Cascaded with semantic VAD | L0 (semantic endpointing) | 400–800 ms  | Semantic VAD reduces interruptions; still half-duplex  [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad) |

**Why production lags research**: [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)
- **Modularity**: Cascaded systems allow swapping LLM/STT/TTS independently; full-duplex requires retraining entire model
- **LLM evolution**: Rapid LLM improvements (multiple releases/year) make full-duplex retraining prohibitively expensive
- **Tool integration**: Cascaded systems inherit mature LLM function-calling; full-duplex models lack tool use (Moshi has no function calling) [aiwiki](https://aiwiki.ai/wiki/moshi)

### What Research Prototypes Demonstrate

**Moshi** (Kyutai, 2024): First open full-duplex model with: [aiwiki](https://aiwiki.ai/wiki/moshi)
- **Simultaneous streams**: Two audio token streams (user + agent) processed jointly at 12.5 Hz
- **No turn-taking**: Model can speak while listening; user can interrupt without triggering state reset
- **Backchannel generation**: Emits "mhm", "yeah" mid-user-utterance without yielding floor
- **Latency**: 160 ms theoretical, 200 ms practical (below human 230 ms average)

**Successor models**:
- **Hibiki** (Kyutai, 2025): Simultaneous speech translation (French → English) with voice preservation [aiwiki](https://aiwiki.ai/wiki/moshi)
- **MoshiVis** (2025): Vision-augmented full-duplex (discuss images in real-time) [aiwiki](https://aiwiki.ai/wiki/moshi)
- **Unmute** (Kyutai, 2025): Wraps any text LLM with Kyutai's STT/TTS for modular full-duplex [aiwiki](https://aiwiki.ai/wiki/moshi)
- **SteerDuplex** (2026): Extends Moshi with explicit control over tone, persona, accent, speaking speed [alphaxiv](https://www.alphaxiv.org/abs/2609.12623)
- **PersonaPlex-7B** (NVIDIA, 2026): Dual-stream full-duplex with persona control [marktechpost](https://www.marktechpost.com/2026/01/17/nvidia-releases-personaplex-7b-v1-a-real-time-speech-to-speech-model-designed-for-natural-and-full-duplex-conversations/)

### The Realization Gap

A 2026 survey identifies a **realization gap**: many L2 architectures can *in principle* operate full-duplex, but *in practice* revert to half-duplex behavior due to: [alphaxiv](https://www.alphaxiv.org/abs/2606.19453)
- **Training data bottleneck**: Public datasets (Fisher, Switchboard) have ~5K hours of stereo data; industrial corpora are undisclosed but likely much larger
- **Evaluation mismatch**: Standard metrics (WER, BLEU) ignore timing and overlap handling; new benchmarks (Full-Duplex-Bench) focus on stop-latency and response-appropriateness [alphaxiv](https://www.alphaxiv.org/abs/2606.19453)
- **Concurrent speech gap**: Sustained overlap (both parties speaking for >1 second) is almost entirely absent from training/evaluation data [alphaxiv](https://www.alphaxiv.org/abs/2606.19453)

## Key Papers and System Cards

| Paper / System | Year | Contribution |
|----------------|------|--------------|
| **Moshi** (Défossez et al., arXiv:2410.00037) | 2024 | First open full-duplex speech-text foundation model; two-stream token modeling  [aiwiki](https://aiwiki.ai/wiki/moshi) |
| **Full-Duplex-Bench v1.5** (Lin et al., ICASSP 2026) | 2026 | Automated benchmark for overlap handling; decomposes interruptions, backchannels, background speech  [alphaxiv](https://www.alphaxiv.org/abs/2507.23159) |
| **Survey of Full-Duplex SDS** (Lin et al., arXiv:2606.19453) | 2026 | L0–L3 architectural hierarchy; T×I×R interaction ontology; Decision State Machine  [alphaxiv](https://www.alphaxiv.org/abs/2606.19453) |
| **SteerDuplex** (arXiv:2609.12623) | 2026 | Extends Moshi with explicit steering over tone, persona, vocal style, accent  [alphaxiv](https://www.alphaxiv.org/abs/2609.12623) |
| **PersonaPlex-7B** (NVIDIA) | 2026 | Real-time full-duplex S2S model with dual-stream configuration  [marktechpost](https://www.marktechpost.com/2026/01/17/nvidia-releases-personaplex-7b-v1-a-real-time-speech-to-speech-model-designed-for-natural-and-full-duplex-conversations/) |
| **Turn-Taking in Voice Agents** (Gradium, 2026) | 2026 | Analysis of VAD failures; semantic VAD as intermediate step toward full-duplex  [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad) |

**Human conversation benchmarks**:
- **Stivers et al. (2009, PNAS)**: 208 ms average turn gap across 10 languages [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)
- **Dingemanse & Liesenfeld (2022)**: 59–200 ms gap range depending on social context [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC12517399/)

Production systems in 2026 remain **cascaded half-duplex** (L0) with semantic VAD improvements, while research prototypes demonstrate **native full-duplex** (L2) with human-parity timing. The gap is operational (modularity, tool integration) rather than architectural. [gradium](https://gradium.ai/content/turn-taking-voice-agents-vad)