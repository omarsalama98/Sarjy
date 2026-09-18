The two dominant architectures for conversational voice AI—**cascaded pipelines** (VAD → ASR → LLM → TTS) and **end-to-end speech-to-speech (S2S) models**—differ fundamentally in data flow, latency accumulation, information preservation, and operational flexibility. Cascaded systems dominate production in 2026 due to modularity and mature tooling, while S2S models offer lower latency and paralinguistic awareness but remain research/prototype-grade for most use cases. [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)

## Cascaded Pipeline: VAD → ASR → LLM → TTS

### Data Flow

1. **Voice Activity Detection (VAD)**: Detects speech onset/offset to segment audio into utterances. Modern systems use **semantic VAD** that waits for linguistically complete turns rather than silence gaps. [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)
2. **ASR (Automatic Speech Recognition)**: Streams partial transcripts while user speaks, finalizes on turn end. Outputs: text transcript + confidence scores. [livekit](https://livekit.com/blog/voice-agent-architecture-stt-llm-tts-pipelines-explained)
3. **LLM**: Receives transcript, generates text response token-by-token. Can invoke tools, access RAG, apply guardrails mid-generation. [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)
4. **TTS (Text-to-Speech)**: Converts LLM tokens to audio, streams first audio chunk before LLM finishes. [deepgram](https://deepgram.com/learn/unified-end-to-end-text-to-speech-architecture-cuts-latency)

```
User audio → VAD → ASR (text) → LLM (text) → TTS → Agent audio
                    ↑              ↑              ↑
                transcript    tool calls    voice synthesis
```

### Where Latency Accumulates

| Stage | Typical Latency (P50) | Notes |
|-------|----------------------|-------|
| VAD end-of-speech detection | 20–100 ms | Semantic VAD reduces false endpoints  [gradium](https://gradium.ai/content/cascaded-voice-agent-vs-speech-to-speech-2026) |
| ASR first partial | 100–300 ms | Streaming; final transcript adds 50–100 ms  [livekit](https://livekit.com/blog/voice-agent-architecture-stt-llm-tts-pipelines-explained) |
| LLM time-to-first-token (TTFT) | 200–600 ms | Dominates pipeline; depends on model size  [deepgram](https://deepgram.com/learn/unified-end-to-end-text-to-speech-architecture-cuts-latency) |
| TTS time-to-first-audio (TTFA) | 75–300 ms | Modern APIs (e.g., Realtime TTS-2 Flash) achieve <100 ms P99  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) |
| Network + orchestration | 50–200 ms | WebRTC <50 ms; PSTN 150–700 ms  [livekit](https://livekit.com/blog/voice-agent-architecture-stt-llm-tts-pipelines-explained) |
| **Total TTFA** | **600–1,200 ms** | Sub-500 ms achievable with aggressive streaming  [futureagi](https://futureagi.com/blog/cascaded-voice-ai-vs-speech-to-speech-2026/) |

Latency is **additive**: each stage must wait for prior stage output, though streaming overlaps ASR→LLM→TTS partially. [livekit](https://livekit.com/blog/voice-agent-architecture-stt-llm-tts-pipelines-explained)

### Information Lost at ASR Step

ASR discards **all paralinguistic information**:

- **Tone**: pitch contour, intonation patterns (question vs. statement)
- **Emotion**: frustration, excitement, sarcasm, uncertainty
- **Emphasis**: which words are stressed for contrast or focus
- **Hesitation**: filled pauses ("um", "uh"), elongated vowels, restarts
- **Speaker identity**: voice timbre, accent, age/gender cues
- **Background context**: ambient noise, overlapping speech, laughter [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)

Example: User says "*I'm **fine***" with flat tone and elongated "fine" (indicating frustration). ASR outputs `"I'm fine"`—the LLM cannot distinguish genuine vs. ironic fine. [gradium](https://gradium.ai/content/cascaded-voice-agent-vs-speech-to-speech-2026)

### What Cascaded Pipelines Can Do With Paralinguistic Cues

**Nothing directly.** The LLM reasons over text only. Some systems attempt reconstruction:
- TTS can add prosody based on punctuation or SSML tags, but this is synthetic, not responsive to user emotion. [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)
- Separate emotion classifiers on audio (pre-ASR) can inject metadata, but this is ad-hoc and rarely production-grade. [gradium](https://gradium.ai/content/cascaded-voice-agent-vs-speech-to-speech-2026)

### Controllability, Debuggability, Cost, Tool Calls, Guardrails

| Dimension | Cascaded Pipeline |
|-----------|-------------------|
| **Controllability** | High: swap STT/LLM/TTS independently; tune each component; apply SSML to TTS; prompt-engineer LLM  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) |
| **Debuggability** | High: per-stage spans (ASR WER, LLM hallucination, TTS mispronunciation); transcript-native logging for compliance  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) |
| **Cost** | Per-component pricing: STT ~$0.15/hr, TTS ~$25/1M chars, LLM at-cost routing. Can downgrade LLM without touching voice quality.  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) |
| **Tool calls** | Mature: inherits LLM provider's full function-calling surface (OpenAI, Anthropic). Supports multi-tool chains, strict JSON schema, parallel calls.  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) |
| **Guardrails mid-turn** | Easy: intercept transcript pre-LLM (PII redaction, moderation); intercept LLM tokens pre-TTS (safety filters, RAG injection).  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) |

## End-to-End Speech-to-Speech Models

### Data Flow

Single multimodal model consumes audio tokens, emits audio tokens directly:

```
User audio → Audio codec (tokens) → S2S transformer → Audio codec (tokens) → Agent audio
                 ↑                                        ↑
           EnCodec/DAC tokens                      DAC/EnCodec decoder
```

No intermediate transcript on hot path. Transcript may be generated for logging via separate ASR pass. [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)

Key systems:
- **OpenAI Realtime API** (`gpt-realtime`): WebRTC/WebSocket, function calling, multi-modal (audio + text + image). [futureagi](https://futureagi.com/blog/cascaded-voice-ai-vs-speech-to-speech-2026/)
- **Google Gemini Live API**: Native audio/video/text input, tool calling, long-context conversation. [futureagi](https://futureagi.com/blog/cascaded-voice-ai-vs-speech-to-speech-2026/)
- **Moshi** (Kyutai, 2024): Open-weight, full-duplex (two simultaneous audio streams), no turn-taking mechanism. [gradium](https://gradium.ai/content/cascaded-voice-agent-vs-speech-to-speech-2026)

### Where Latency Accumulates

| Component | Typical Latency | Notes |
|-----------|----------------|-------|
| Single inference pass (audio-in → audio-out) | 300–500 ms TTFA | No STT/LLM/TTS handoff; warm WebRTC connection  [inworld](https://inworld.ai/resources/best-speech-to-speech-model) |
| Network + transport | 50–150 ms | WebRTC optimized  [livekit](https://livekit.com/blog/voice-agent-architecture-stt-llm-tts-pipelines-explained) |
| **Total TTFA** | **300–500 ms** | ~2× faster than typical cascaded  [inworld](https://inworld.ai/resources/best-speech-to-speech-model) |

Latency is **non-additive**: single forward pass avoids sequential bottlenecks. However, large multimodal models may have higher per-token compute cost. [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)

### Paralinguistic Information Preserved

S2S models perceive and respond to:

- **Tone**: matches output prosody to user's pitch contour (e.g., gentle response to flat tone). [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)
- **Emotion**: detects frustration, excitement, sarcasm from audio features; modulates response accordingly. [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)
- **Emphasis**: hears which words user stressed; can mirror or contrast in response. [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)
- **Hesitation**: detects uncertainty from filled pauses, elongations; can offer clarification or encouragement. [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)
- **Speaker identity**: recognizes voice timbre across turns; enables personalized voice cloning without explicit enrollment. [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)
- **Background context**: laughter, overlapping speech, ambient noise inform turn-taking and response timing. [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)

Example: User says "*I'm **fine***" with frustrated tone. S2S model hears frustration, responds gently: "*You sound upset—want to talk about it?*" [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)

### Full-Duplex Conversation

Moshi and similar models process **two simultaneous audio streams** (user + agent), eliminating turn-taking:
- No VAD required; model can respond while user speaks (backchanneling: "mhm", "uh-huh"). [gradium](https://gradium.ai/content/cascaded-voice-agent-vs-speech-to-speech-2026)
- Natural overlap handling: user interrupts, model pauses, both speak briefly. [gradium](https://gradium.ai/content/cascaded-voice-agent-vs-speech-to-speech-2026)

### Controllability, Debuggability, Cost, Tool Calls, Guardrails

| Dimension | End-to-End S2S |
|-----------|----------------|
| **Controllability** | Low: LLM baked into weights; cannot swap components; fixed voice sets; prompt engineering not directly applicable.  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) |
| **Debuggability** | Low: single audio-in/audio-out span; no per-stage transcript; must sample-decode to text for retrospective eval.  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) |
| **Cost** | Bundled audio-token pricing: OpenAI gpt-realtime-2.1 at $32/1M input tokens + $64/1M output tokens; Gemini Live at $0.005/min in + $0.018/min out. No per-component levers.  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) |
| **Tool calls** | Emerging: OpenAI Realtime and Gemini Live support function calling, but edge cases (mid-turn barge-in during tool call, strict schema validation) are rougher than cascaded.  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) |
| **Guardrails mid-turn** | Limited: no transcript boundary to intercept; must run inline audio moderation (e.g., Future AGI Protect on output audio).  [futureagi](https://futureagi.com/blog/cascaded-voice-ai-vs-speech-to-speech-2026/) |

## Trade-Off Summary

| Axis | Cascaded Wins When... | S2S Wins When... |
|------|----------------------|------------------|
| **Latency** | Aggressive streaming + co-located components achieve sub-500 ms  [futureagi](https://futureagi.com/blog/cascaded-voice-ai-vs-speech-to-speech-2026/) | Default 300–500 ms without tuning; critical for conversational UX  [inworld](https://inworld.ai/resources/best-speech-to-speech-model) |
| **Paralinguistic awareness** | Not required (transactional: scheduling, support, healthcare)  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) | Core product (companions, language tutors, social apps)  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) |
| **Tool depth** | 5+ tools with strict schemas (booking, payments, PHI)  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) | 1–3 tools with loose validation (search, lookup)  [futureagi](https://futureagi.com/blog/cascaded-voice-ai-vs-speech-to-speech-2026/) |
| **Observability** | Compliance, moderation, eval require transcript-native logging  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) | Prototype/research; can tolerate post-hoc sampled transcript eval  [futureagi](https://futureagi.com/blog/cascaded-voice-ai-vs-speech-to-speech-2026/) |
| **Vendor flexibility** | Need to swap LLM quarterly; multi-vendor STT/TTS  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) | Single-vendor simplicity acceptable; locked to S2S provider  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) |
| **Voice cloning** | Custom brand voice required (ElevenLabs, Cartesia)  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) | Fixed voice sets sufficient (OpenAI shimmer/alloy/echo)  [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture) |

## Key Papers and System Cards

- **Moshi** (Kyutai, 2024, arXiv:2410.00037): First open full-duplex S2S model with two simultaneous audio streams. [gradium](https://gradium.ai/content/cascaded-voice-agent-vs-speech-to-speech-2026)
- **OpenAI Realtime API** (2024–2026): Production S2S with function calling, multi-modal input. Pricing: $32/1M input tokens, $64/1M output tokens (gpt-realtime-2.1). [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)
- **Gemini Live API** (Google, 2025–2026): Native audio/video/text S2S with tool calling. Pricing: $0.005/min in, $0.018/min out. [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)
- **SoundStream** (Zeghidour et al., 2021, arXiv:2107.03312): Neural audio codec enabling discrete audio tokens for S2S. [gradium](https://gradium.ai/content/cascaded-voice-agent-vs-speech-to-speech-2026)
- **Cascaded vs. S2S comparisons**: Inworld AI (July 2026), Gradium (Sept 2026), Future AGI (April 2026). [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)

The field is converging toward **hybrid architectures**: semantic VAD + streaming cascaded pipelines with S2S-like prosody transfer, or S2S models with modular LLM backends. Until then, cascaded remains the production default; S2S leads in conversational naturalness. [inworld](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)