# Perplexity prompts — how voice AI actually works

**Purpose:** the *mechanism* layer, not the vendor layer. `voice-stack-research.md` and `arabic-voice-research.md` already cover providers, pricing, and measured latency — don't re-research those. This is for understanding what's happening underneath, so the codebase walkthrough goes well.

**Why it matters for the grade:** the rubric asks *"do you understand it thoroughly?"* and the presentation ends in a live codebase discussion. The difference between "I used Pipecat" and "here's why endpointing dominates the latency budget and what the model is actually doing with the audio" is most of that score.

Work through these in order — each builds on the last. Prompts 1–4 are the core; 5–8 are depth if time allows.

---

## 1. How audio becomes something a model can consume

> Explain how raw audio is represented for modern speech AI models. Cover: waveform vs. mel-spectrogram representations; neural audio codecs (EnCodec, SoundStream, DAC) and residual vector quantization; the distinction between *semantic* tokens and *acoustic* tokens and why some architectures use both; typical frame rates and token rates (tokens per second of audio) and how those compare to text token rates. Explain why audio token rate is the central constraint on latency and context length in speech-to-speech models. Use diagrams or tables where helpful, and cite papers.

**What this buys you:** the single most useful mental model. Once you know audio is ~50–100 tokens/second versus text at ~3–4, most architectural decisions in the field become obvious.

---

## 2. Cascaded vs. end-to-end speech-to-speech

> Compare the two dominant architectures for conversational voice AI: (a) the cascaded pipeline — VAD → ASR → LLM → TTS — and (b) end-to-end speech-to-speech models that consume and emit audio tokens directly. For each, explain the data flow, where latency accumulates, and what information is preserved or lost. Specifically: what paralinguistic information (tone, emotion, emphasis, hesitation, speaker identity) does a cascaded pipeline discard at the ASR step, and what can an end-to-end model do with it? Cover the trade-offs in controllability, debuggability, cost, and the ability to inject tool calls or guardrails mid-turn. Cite the key papers and system cards.

**What this buys you:** the central architectural question of your project, and a near-certain interview question. Note the guardrails angle especially — a cascaded pipeline gives you a text checkpoint to inspect and gate, which an end-to-end model does not. That's directly relevant to your deep dive.

---

## 3. Turn detection and endpointing

> Explain how conversational voice systems decide that a user has finished speaking. Cover: energy-based VAD vs. neural VAD (Silero); the silence-threshold approach and why default thresholds of 500–700 ms are a large fraction of the total latency budget; semantic turn detection models that predict end-of-turn from linguistic content rather than silence; and integrated approaches where the ASR itself emits an end-of-turn signal. Explain the fundamental trade-off between cutting a user off and making them wait, and how production systems tune it. Cover backchannels ("mhm", "yeah") and why they must not trigger a turn. Cite benchmarks and papers.

**What this buys you:** the highest-leverage latency knob, and the one most take-homes never touch. Your research already found that a default VAD threshold can exceed the entire STT+LLM+TTS budget combined.

---

## 4. Streaming and latency engineering

> Explain the techniques used to minimise time-to-first-audio in a conversational voice pipeline. Cover: streaming ASR (partial hypotheses, lookahead, chunked attention) and why some models like Whisper are architecturally non-streaming; streaming LLM generation and how TTS can begin on the first clause rather than the complete response; streaming TTS and how time-to-first-byte is achieved; sentence/clause chunking strategies for feeding TTS; and how systems overlap stages rather than running them sequentially. Also cover barge-in handling — detecting user speech during playback, cancelling in-flight generation, and acoustic echo cancellation. Cite real system architectures.

**What this buys you:** the concrete engineering of the thing you're building, plus the vocabulary to explain your choices.

---

## 5. ASR architectures

> Explain the main neural ASR architectures and their trade-offs: CTC, attention-based encoder-decoder, and RNN-Transducer (RNN-T). For each, cover streaming capability, latency characteristics, and typical accuracy. Explain specifically how Whisper is designed (encoder-decoder, 30-second windows) and why that makes true streaming difficult, plus what techniques exist to approximate streaming with it. Cover how modern ASR handles code-switching between languages within a single utterance, and why that is architecturally hard. Cite papers.

**What this buys you:** why Whisper-based pipelines behave the way they do, and the code-switching mechanism behind your Arabic plan.

---

## 6. TTS architectures

> Explain modern neural text-to-speech architectures. Cover: autoregressive token-based TTS vs. non-autoregressive approaches; diffusion and flow-matching based TTS; the role of neural vocoders; and zero-shot voice cloning from short reference audio. Explain how streaming TTS achieves low time-to-first-byte and what quality trade-offs that involves. Cover how TTS systems handle multilingual text and embedded foreign words — for example an English drug name inside an Arabic sentence — and why language detection on code-mixed text is unreliable. Cite papers and system cards.

**What this buys you:** the output leg, which your Arabic research flagged as the real risk rather than the input.

---

## 7. Full-duplex conversation modelling

> Explain how voice AI systems model conversation as a full-duplex process rather than strict turn-taking. Cover: architectures that continuously process input while generating output; how models handle overlapping speech, interruptions, and backchannels; and the research on making AI conversation feel natural in timing (response latency norms in human conversation, typically around 200 ms). Cover what current production systems actually do versus what research prototypes demonstrate. Cite papers.

**What this buys you:** why voice agents feel robotic even when fast, and a good answer to "what would you do with another week?"

---

## 8. Evaluating voice agents

> Explain how conversational voice AI systems are evaluated. Cover: ASR accuracy metrics (WER, CER) and their known weaknesses — particularly how WER penalises semantically-correct transcription variants and how it behaves on code-switched speech; TTS quality metrics (MOS, CMOS, intelligibility); latency metrics and how time-to-first-audio is defined inconsistently across vendors; and end-to-end conversational quality evaluation including LLM-as-judge approaches. Cover what makes voice agent evaluation harder than text agent evaluation. Cite papers and benchmarks.

**What this buys you:** the measurement discipline your deep dive rests on, plus why vendor latency numbers aren't comparable.

---

## How to use the results

Don't paste the answers into the repo. Take notes in your own words — the point is the walkthrough, and notes you wrote yourself are the ones you'll still remember in three weeks.

Two things worth capturing as you go:

- **A latency budget diagram** you drew yourself, with your own numbers in it once you measure.
- **One paragraph on why you chose cascaded or end-to-end**, written before you build. That paragraph goes almost verbatim into the writeup, and it's the question you're most likely to be asked.

## Follow-up prompt pattern

When an answer is too shallow, this usually fixes it:

> That was a good overview. Now go a level deeper on [X]. I want the actual mechanism, not the summary — specific architectures, specific numbers, and the papers they come from. Where sources disagree, say so.
