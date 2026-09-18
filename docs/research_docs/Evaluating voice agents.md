Conversational voice AI systems are evaluated across four distinct layers—**ASR accuracy**, **TTS quality**, **latency**, and **end-to-end conversational quality**—each with its own metrics, known weaknesses, and evaluation challenges. Voice agent evaluation is fundamentally harder than text agent evaluation because it involves **continuous time** (latency, turn-taking), **multi-modal signals** (audio + text + timing), and **subjective quality** (naturalness, emotion) that cannot be captured by token matching alone. [arxiv](https://arxiv.org/abs/2608.09930)

## ASR Accuracy Metrics: WER, CER, and Their Weaknesses

### Word Error Rate (WER) and Character Error Rate (CER)

**WER** is the standard ASR metric, defined as: [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)

\[
\text{WER} = \frac{S + D + I}{N}
\]

where \(S\) = substitutions, \(D\) = deletions, \(I\) = insertions, and \(N\) = total words in reference. WER is computed via minimum edit distance (Levenshtein alignment) between hypothesis and reference transcripts. [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)

**CER** (Character Error Rate) is the character-level analogue, used for languages without clear word boundaries (Chinese, Japanese) or agglutinative languages (Tamil, Turkish). [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)

### Why WER Penalizes Semantically-Correct Variants

WER has **three fundamental weaknesses** that inflate error scores on semantically correct transcriptions: [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)

1. **Orthographic variation**: Different valid spellings of the same word are counted as substitutions. Example: "colour" vs. "color", "ibuprofen" vs. "إيبوبروفين" (Arabic transliteration) [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)

2. **Morphological agglutination**: In agglutinative languages (Tamil, Malayalam, Turkish), a single spoken utterance can be validly written with different morpheme boundaries. WER counts different segmentations as full word errors. [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)

3. **Code-switching script variance**: In Arabic–English or Persian–English code-switching, English loanwords may appear in Latin script or transliterated into Arabic/Persian script. Both are correct, but WER treats them as completely different tokens. [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)

**Empirical evidence**: A 2026 benchmark on Arabic–Persian code-switching found Kendall's τ correlation of only 0.40 between WER and BERTScore for Persian–English (vs. 0.80 for German–English), indicating WER unfairly penalizes semantically equivalent transliterations. [themoonlight](https://www.themoonlight.io/en/review/benchmarking-commercial-asr-systems-on-code-switching-speech-arabic-persian-and-german)

### WER Behavior on Code-Switched Speech

Code-switching (CS) exacerbates WER's weaknesses: [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)

| Issue | Example | WER Penalty |
|-------|---------|-------------|
| **Script variance** | "feature" vs. "فیچر" (Persian transliteration) | Full substitution (1.0 WER) despite semantic equivalence  [themoonlight](https://www.themoonlight.io/en/review/benchmarking-commercial-asr-systems-on-code-switching-speech-arabic-persian-and-german) |
| **Morphological blending** | Arabic prefix "الـ" + English word ("الـfeature") | Counted as insertion + substitution  [themoonlight](https://www.themoonlight.io/en/review/benchmarking-commercial-asr-systems-on-code-switching-speech-arabic-persian-and-german) |
| **Token alternation** | "I need to book a flight *بكره*" (Arabic "tomorrow") | WER assumes single language; penalizes script switches  [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework) |

**Alternative metrics for CS**: [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)
- **BERTScore**: Token-level cosine similarity in multilingual embedding space (mBERT, XLM-R). Captures semantic equivalence across scripts. [themoonlight](https://www.themoonlight.io/en/review/benchmarking-commercial-asr-systems-on-code-switching-speech-arabic-persian-and-german)
- **Mixed Error Rate (MER)**: Combines WER for word-based segments and CER for character-based segments within one transcription [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)
- **Script-Aware Error Rate (SAER)**: Explicitly penalizes script-switching errors [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)
- **Switch Entry Token Error Rate (SETER)**: Measures error rate specifically at code-switch boundaries [arxivtldr](https://arxivtldr.org/abs/2609.11786)

**BRIDGE framework** (Deepgram, 2026): Composite 7-metric evaluation for Indic ASR: [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)
- **B**: BERTScore (semantic similarity)
- **R**: Entity F1 (named entity accuracy)
- **I**: Word Information Lost (WIL, normalized complement to WER)
- **D**: Domain-weighted accuracy (AWWER for agricultural/medical terms)
- **G**: Grapheme-level error rate (CER)
- **E**: Error segmentation (SER + MER/SAER for code-switching)

### Typical WER Benchmarks

| System | Monolingual WER | Code-Switched WER | Notes |
|--------|----------------|-------------------|-------|
| **Whisper Large v3** | 3–6% (LibriSpeech)  | 15–25% (Arabic–English)  [themoonlight](https://www.themoonlight.io/en/review/benchmarking-commercial-asr-systems-on-code-switching-speech-arabic-persian-and-german) | Non-streaming; struggles with CS |
| **ElevenLabs Scribe v2** | 5–8% (conversational) | 13.2% (CS average)  [themoonlight](https://www.themoonlight.io/en/review/benchmarking-commercial-asr-systems-on-code-switching-speech-arabic-persian-and-german) | Best on Arabic pairs; BERTScore 0.936 |
| **Google Chirp 3** | 6–10% (conversational) | 18–22% (CS average)  [themoonlight](https://www.themoonlight.io/en/review/benchmarking-commercial-asr-systems-on-code-switching-speech-arabic-persian-and-german) | Language-agnostic end-to-end |
| **Deepgram Nova-3** | 4–7% (English) | N/A (no Arabic/Persian support)  [themoonlight](https://www.themoonlight.io/en/review/benchmarking-commercial-asr-systems-on-code-switching-speech-arabic-persian-and-german) | Native CS for Latin-script pairs |

## TTS Quality Metrics: MOS, CMOS, Intelligibility

### Mean Opinion Score (MOS)

**MOS** is the gold standard for TTS quality, asking human raters to score naturalness on a 1–5 scale: [linkedin](https://www.linkedin.com/posts/prakruthi-b-gowda-b3aaa9160_speechai-tts-evaluation-activity-7475554934013313024-0Y7k)

\[
\text{MOS} = \frac{1}{N} \sum_{i=1}^{N} r_i
\]

where \(N\) = number of listeners, \(r_i\) = rating from listener \(i\). [convozen](https://convozen.ai/research/article/benchmarking-conversational-tts)

**Limitations**: [arxiv](https://arxiv.org/abs/2608.09930)
- **Expensive**: Requires 20–50 trained raters per condition; not scalable for iterative development
- **Subjective**: Inter-rater variance can be ±0.5 MOS points
- **Saturation**: At MOS > 4.5, neural MOS predictors cannot reliably differentiate frontier models [linkedin](https://www.linkedin.com/posts/prakruthi-b-gowda-b3aaa9160_speechai-tts-evaluation-activity-7475554934013313024-0Y7k)

### CMOS (Comparative MOS) and AB Tests

**CMOS** (Comparative MOS) uses pairwise comparison (System A vs. System B) rather than absolute scoring, reducing rater bias. Results are reported as preference percentages (e.g., "System A preferred 62% of the time"). [convozen](https://convozen.ai/research/article/benchmarking-conversational-tts)

### Intelligibility Metrics

**Intelligibility** measures whether synthesized speech is understandable, distinct from naturalness. Key metrics: [linkedin](https://www.linkedin.com/posts/prakruthi-b-gowda-b3aaa9160_speechai-tts-evaluation-activity-7475554934013313024-0Y7k)

| Metric | Description | Target |
|--------|-------------|--------|
| **WER (ASR-based)** | Run TTS output through ASR; compare transcript to original text | WER < 5% for production  [linkedin](https://www.linkedin.com/posts/prakruthi-b-gowda-b3aaa9160_speechai-tts-evaluation-activity-7475554934013313024-0Y7k) |
| **CER** | Character-level intelligibility (for Chinese, Japanese) | CER < 3%  [linkedin](https://www.linkedin.com/posts/prakruthi-b-gowda-b3aaa9160_speechai-tts-evaluation-activity-7475554934013313024-0Y7k) |
| **STOI** (Short-Time Objective Intelligibility) | Signal-processing metric predicting speech intelligibility | STOI > 0.85  [git-lium.univ-lemans](https://git-lium.univ-lemans.fr/jsalt2025/wp1/tts4all_eval/-/tree/main/src?ref_type=heads) |
| **UTMOSv2** | Neural MOS predictor (Pearson correlation 0.84+ with human MOS) | UTMOS > 4.0 for production  [linkedin](https://www.linkedin.com/posts/prakruthi-b-gowda-b3aaa9160_speechai-tts-evaluation-activity-7475554934013313024-0Y7k) |

### Speaker Similarity and Prosody

| Metric | Description | Target |
|--------|-------------|--------|
| **SIM-o** (Speaker Similarity) | Cosine similarity of speaker embeddings (WavLM, ECAPA) from reference vs. synthesized audio | SIM-o > 0.85 for voice cloning  [linkedin](https://www.linkedin.com/posts/prakruthi-b-gowda-b3aaa9160_speechai-tts-evaluation-activity-7475554934013313024-0Y7k) |
| **f0 variation** | Expressivity score based on pitch contour variation | f0 contour matches reference  [git-lium.univ-lemans](https://git-lium.univ-lemans.fr/jsalt2025/wp1/tts4all_eval/-/tree/main/src?ref_type=heads) |
| **MCD** (Mel Cepstral Distortion) | Euclidean distance between MFCCs of synthesized vs. reference audio | MCD < 5 dB  [mbrenndoerfer](https://mbrenndoerfer.com/writing/text-to-speech-neural-architectures-acoustic-modeling) |

### Automated TTS Evaluators and Their Weaknesses

A 2026 study benchmarked **four MOS predictors** (UTMOSv2, DNSMOS, NISQA, TTSQA) and **four Audio-LLM judges** (Qwen-Audio, Llama-3-Audio, etc.) on 860 linguistically annotated utterances. [arxiv](https://arxiv.org/abs/2608.09930)

**Key findings**: [arxiv](https://arxiv.org/abs/2608.09930)
- **MOS predictors collapse onto acoustic signal quality**: They detect noise, distortion, and artifacts but miss linguistically structured errors (mispronunciation, wrong stress, unnatural prosody)
- **Audio-LLM judges show selective, prompt-dependent detection**: They can detect specific error types (e.g., "check for mispronounced words") but do not generalize across all 10 perceptual dimensions
- **Neither class reliably captures breadth of errors**: Automated evaluators miss ~40% of linguist-annotated errors, particularly prosodic and morphological mistakes

**Recommendation**: Use automated MOS predictors for rapid iteration, but validate with human MOS for production releases. [arxiv](https://arxiv.org/abs/2608.09930)

## Latency Metrics: Inconsistent TTFA Definitions

### Time-to-First-Audio (TTFA) Definition Variance

**TTFA** (Time-to-First-Audio) measures latency from TTS request submission to first audio sample arrival. However, vendors define TTFA inconsistently: [bland](https://www.bland.ai/blog/low-latency-tts-api)

| Vendor | Clock Start | Clock Stop | Notes |
|--------|-------------|------------|-------|
| **Coval** | Synthesis start (after connection established) | First audio chunk arrival + leading silence inside stream | TTFA = (first audio chunk arrival - synthesis start) + leading silence  [gradium](https://gradium.ai/content/tts-latency-benchmark-2026) |
| **Bland AI** | After connection established, on warm server, with short input sentence | First byte of audio (not first intelligible word) | Vendors control where clock starts/stops; end-to-end window longer than isolated TTFA  [bland](https://www.bland.ai/blog/low-latency-tts-api) |
| **ElevenLabs** | Text submission to API | First audio byte received | Does not include network handshake or LLM inference  |
| **Gradium** | LLM generates first token | First audible sample (excluding leading silence) | Median TTFA 214 ms (Sept 2026)  [gradium](https://gradium.ai/content/tts-latency-benchmark-2026) |

**Why inconsistency matters**: A vendor reporting 100 ms TTFA (warm connection, short sentence) may actually deliver 400 ms end-to-end in production (cold start, long sentence, network latency). [bland](https://www.bland.ai/blog/low-latency-tts-api)

### End-to-End Latency Budget

Production voice agents must account for **full pipeline latency**, not just TTS TTFA: [bland](https://www.bland.ai/blog/low-latency-tts-api)

| Stage | Typical Latency (P50) | Notes |
|-------|----------------------|-------|
| VAD end-of-speech detection | 20–100 ms | Semantic VAD reduces false endpoints  |
| ASR streaming first partial | 100–300 ms | Streaming; final transcript adds 50–100 ms  |
| LLM time-to-first-token (TTFT) | 200–600 ms | Dominates pipeline; depends on model size  |
| TTS time-to-first-audio (TTFA) | 75–300 ms | Modern APIs (e.g., Realtime TTS-2 Flash) achieve <100 ms P99  |
| Network + orchestration | 50–200 ms | WebRTC <50 ms; PSTN 150–700 ms  |
| **Total TTFA** | **600–1,200 ms** | Sub-500 ms achievable with aggressive streaming  |

### Recommended Latency Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **TTFA (isolated)** | TTS request → first audio byte | <150 ms (warm)  |
| **End-to-end TTFA** | User stops speaking → agent starts speaking | <500 ms (P50), <1,000 ms (P95)  [softwareseni](https://www.softwareseni.com/voice-agent-latency-solved-enough-for-production-benchmarks-and-architecture-tradeoffs/) |
| **RTF (Real-Time Factor)** | Inference time / audio duration | RTF < 1.0 (faster than real-time)  [linkedin](https://www.linkedin.com/posts/prakruthi-b-gowda-b3aaa9160_speechai-tts-evaluation-activity-7475554934013313024-0Y7k) |
| **Turn gap** | User utterance end → agent utterance start | 160–230 ms (human parity)  |

## End-to-End Conversational Quality Evaluation

### LLM-as-Judge Approaches

**LLM-as-judge** uses large language models to evaluate voice agent conversations holistically, scoring dimensions like helpfulness, naturalness, and task completion. [arxiv](https://arxiv.org/abs/2608.09930)

**Typical setup**: [arxiv](https://arxiv.org/abs/2608.09930)
1. Record full conversation (user audio + agent audio + transcripts)
2. Prompt LLM (e.g., GPT-4o, Claude) with conversation transcript + evaluation rubric
3. LLM scores each dimension on 1–5 scale with justification

**Advantages**: [arxiv](https://arxiv.org/abs/2608.09930)
- **Scalable**: No human raters needed; can evaluate thousands of conversations
- **Multi-dimensional**: Can score helpfulness, naturalness, empathy, task completion simultaneously
- **Explainable**: LLM provides rationale for each score

**Weaknesses**: [arxiv](https://arxiv.org/abs/2608.09930)
- **Prompt-dependent**: Scores vary significantly based on prompt wording and few-shot examples
- **Bias toward verbosity**: LLMs prefer longer, more detailed responses, penalizing concise agents
- **Cannot perceive audio quality**: LLM judges text transcripts only; misses prosody, emotion, and acoustic artifacts

### Full-Duplex-Bench and Turn-Taking Metrics

**Full-Duplex-Bench v1.5** (NTU + UW + Berkeley + CMU, 2026) is an automated benchmark for overlap handling in full-duplex voice agents. 

**Metrics**: 
- **Stop latency**: Time from user interruption onset to agent stopping speech
- **Response appropriateness**: Whether agent correctly identifies overlap type (backchannel, barge-in, background speech)
- **Context recovery**: Whether agent resumes conversation coherently after interruption

**Turn-Taking metrics** (Gradium, 2026): 
- **Interruption rate**: % of user utterances where agent interrupts mid-sentence
- **Backchannel detection accuracy**: % of backchannels correctly identified (not triggering turn end)
- **Turn gap distribution**: Histogram of user-end → agent-start intervals (target: 160–230 ms)

### Why Voice Agent Evaluation Is Harder Than Text Agent Evaluation

Voice agent evaluation is fundamentally more complex than text agent evaluation due to **four additional dimensions**: [arxiv](https://arxiv.org/abs/2608.09930)

| Dimension | Text Agent | Voice Agent | Why Harder |
|-----------|------------|-------------|------------|
| **Timing** | Irrelevant (asynchronous) | Critical (latency, turn gap) | Must measure P50/P95 latency across regions; human parity requires 160–230 ms turn gaps  |
| **Audio quality** | N/A | MOS, intelligibility, speaker similarity | Requires human raters or neural MOS predictors; automated evaluators miss 40% of errors  [arxiv](https://arxiv.org/abs/2608.09930) |
| **Multi-modal signals** | Text only | Audio + text + timing + prosody | Must evaluate backchannels, interruptions, emotion; LLM-as-judge cannot perceive audio  [arxiv](https://arxiv.org/abs/2608.09930) |
| **Subjective quality** | Helpfulness, correctness | Helpfulness + naturalness + empathy + prosody | MOS saturation at 4.5; requires fine-grained linguistic annotation (10 dimensions)  [arxiv](https://arxiv.org/abs/2608.09930) |

**Additional challenges**: [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)
- **Code-switching**: WER unfairly penalizes semantically correct transliterations; requires BERTScore + MER/SAER [themoonlight](https://www.themoonlight.io/en/review/benchmarking-commercial-asr-systems-on-code-switching-speech-arabic-persian-and-german)
- **Dialect variation**: Same language (e.g., Arabic) has 30+ dialects; WER varies 10–20% across dialects [themoonlight](https://www.themoonlight.io/en/review/benchmarking-commercial-asr-systems-on-code-switching-speech-arabic-persian-and-german)
- **Domain terminology**: Headline WER can hide 2× higher error rates on domain-critical terms (medical, agricultural) [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)

## Key Papers and Benchmarks

| Paper / Benchmark | Year | Contribution |
|-------------------|------|--------------|
| **Beyond Naturalness** (Bamgbose et al., arXiv:2608.09930) | 2026 | Deconstructs TTS naturalness into 10 linguistic dimensions; benchmarks MOS predictors and Audio-LLM judges  [arxiv](https://arxiv.org/abs/2608.09930) |
| **Benchmarking Commercial ASR on Code-Switching** (Moonlight, 2026) | 2026 | 1,200 CS utterances (Arabic–English, Persian–English, German–English); argues for BERTScore over WER  [themoonlight](https://www.themoonlight.io/en/review/benchmarking-commercial-asr-systems-on-code-switching-speech-arabic-persian-and-german) |
| **Why WER Fails Indian Languages** (Deepgram, 2026) | 2026 | BRIDGE 7-metric framework for Indic ASR (BERTScore, Entity F1, WIL, AWWER, CER, SER, MER/SAER)  [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework) |
| **Full-Duplex-Bench v1.5** (Lin et al., ICASSP 2026) | 2026 | Automated benchmark for overlap handling; decomposes interruptions, backchannels, background speech  |
| **Beyond Word Error Rate** (arXiv:2609.11786) | 2026 | Evaluates ASR on English–Yoruba CS; proposes switch-localized diagnostics (SETER, windowed switch point error)  [arxivtldr](https://arxivtldr.org/abs/2609.11786) |
| **TTS MOS Playbook** (DupDub, 2025) | 2025 | Comprehensive guide to TTS evaluation (WER/CER, UTMOSv2, SIM-o, RTF)  [linkedin](https://www.linkedin.com/posts/prakruthi-b-gowda-b3aaa9160_speechai-tts-evaluation-activity-7475554934013313024-0Y7k) |

**Recommended evaluation stack for production voice agents (2026)**: [deepgram](https://deepgram.com/learn/why-wer-fails-indian-languages-bridge-7-metric-framework)
- **ASR**: WER + CER + BERTScore + Entity F1 (for code-switching: MER/SAER)
- **TTS**: UTMOSv2 (naturalness) + WER/CER (intelligibility) + SIM-o (speaker similarity)
- **Latency**: End-to-end TTFA (P50/P95) + turn gap distribution
- **Conversational quality**: LLM-as-judge (helpfulness, task completion) + Full-Duplex-Bench (overlap handling)

Voice agent evaluation requires **multi-metric, multi-dimensional** approaches that capture both surface accuracy (WER, MOS) and deeper qualities (semantic fidelity, naturalness, turn-taking timing). Single-number metrics are insufficient for production deployments. [arxiv](https://arxiv.org/abs/2608.09930)