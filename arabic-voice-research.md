# Arabic & Bilingual Voice — Feasibility for a 3-Day Clinical Copilot

State of the art, September 2026. Every number below carries a source and a date. Where a
number is vendor-self-reported or unverifiable I say so explicitly, and there is a
[dedicated section](#12-what-i-could-not-verify) listing everything I could not confirm.

---

## Summary — read this page only

**Verdict: GO.** A bilingual Arabic/English voice assistant that handles intra-sentence
code-switching is buildable in ~3 part-time days in September 2026. It would *not* have
been in early 2025. The thing that changed is that code-switching stopped being a research
problem and became a purchasing decision: as of March 2026 there is a commercial,
production, real-time **Arabic–English bilingual ASR model — with a medical variant
trained on drug names, dosages and ICD-10-CM codes** — which is almost comically
on-target for a doctor-facing clinical copilot.

**The single biggest risk is the output leg, not the input leg.** STT for code-switching is
solved by picking the right vendor. TTS is not: ElevenLabs' own docs state that automatic
language detection is *"unreliable for short text or codemixed input"* and that production
systems must pass explicit `[AR]` / `[EN]` tags inline. Your LLM emits untagged mixed
text. Something has to tag it before it reaches TTS, or English drug names get read with
Arabic phonology (or vice versa) — which in a clinical demo is the exact failure the demo
exists to disprove.

### Recommended stack for Arabic specifically

| Stage | Pick | Why |
|---|---|---|
| **STT (primary)** | **Speechmatics `ar_en` bilingual pack**, realtime | The only vendor shipping a *single* bilingual Arabic+English model. Claims 6.3% WER on mixed speech vs Google 9.7%. Gulf + Egyptian + Levantine. Free tier: 480 min/mo, 240 realtime min. First-class Pipecat **and** LiveKit plugins. |
| **STT (fallback / A-B)** | **ElevenLabs Scribe v2 Realtime** (~150 ms) | Won the only *independent* commercial code-switching benchmark: 13.2% mean WER vs 38.6% (OpenAI), 39.4% (Google Chirp 3), 43.6% (Azure). Gap widens to **41.5 points** on the hardest code-switch quartile. |
| **LLM** | GPT-5 / GPT-o3 class, or Claude Sonnet 4 | Best published Arabic *medical* accuracy: 0.765 / 0.764 / 0.694 on MedAraBench (24,883 Arabic MCQs, Feb 2026). Arabic-specialist models are far behind: Fanar 0.498, ALLaM-7B 0.447. |
| **TTS** | **ElevenLabs Flash v2.5** (Arabic supported, ~75 ms model latency, 137 ms measured median TTFT) | Fastest Arabic-capable option with real voice quality. **Requires an explicit language-tagging step.** |
| **Do NOT use** | Deepgram Nova-3 for code-switching | Deepgram supports 17 Arabic locales, but Arabic is **not** in Nova-3's multilingual/code-switching mode (that mode is EN/ES/FR/DE/HI/RU/PT/JA/IT/NL only). It is a monolingual Arabic model. |

### Six facts that should shape the build

1. **Dialect, not Arabic, is the axis of difficulty.** On the same models: MSA 10.19 WER,
   Levantine 23.53, Egyptian 34.8, **Gulf/Khaleeji 68.39**, Moroccan 81.77
   ([Arab Voices, arXiv 2601.13319, 19 Jan 2026](https://arxiv.org/html/2601.13319v1)).
   "Arabic works" is meaningless; Gulf is ~6.7× harder than MSA. Demo in Egyptian if you
   have a choice.
2. **WER is the wrong metric for code-switching and overstates the problem by ~3×.** When
   a system writes an embedded English word in Arabic transliteration instead of Latin
   script, WER scores it a 100% substitution error even though it is semantically perfect.
   BERTScore rankings agree exactly (Kendall's τ = 1.000 on both Arabic pairs) but the
   magnitudes are far smaller
   ([arXiv 2605.19069, May 2026](https://arxiv.org/abs/2605.19069)). **Consequence for
   your demo: don't display WER. Show the transcript.**
3. **Script inconsistency is the real failure mode, not error rate.** The same paper's
   hypothesis for why ElevenLabs' BERTScore *rises* on the hardest quartile (0.929 → 0.938)
   is that it "consistently picks a single script convention and applies it coherently,"
   while others produce inconsistent output. Your UI has to survive both conventions.
4. **Frontier LLMs beat Arabic-specialist LLMs on medicine, decisively.** MedAraBench and
   MedArabiQ both find this. MedArabiQ's conclusion: *"task specificity may be more
   critical than language specificity for Arabic medical tasks."* Don't reach for ALLaM
   or Jais.
5. **Arabic medical reasoning does lag.** Best model is 0.765 on MedAraBench, which the
   authors state "does not match expert-level performance." GPT-4's MedArabiQ accuracy
   collapsed 66.3% → 35.7% under injected cognitive bias. Ship a clinical disclaimer.
6. **`dir="auto"` will break your live captions.** It uses the Unicode *first-strong*
   heuristic, not majority script. A caption line that begins "patient عنده chest pain"
   locks the entire line LTR; the next line beginning in Arabic flips RTL. During
   streaming the direction can flip mid-token as the first strong character arrives.

### Minimum viable demo that still lands

A single live caption pane, Egyptian Arabic in, code-switched transcript rendered with
correct bidi, and a **side-by-side toggle: Speechmatics `ar_en` vs Whisper-large-v3.**
Speak one sentence — "عندي patient عنده chest pain ومحتاج aspirin" — and let the audience
watch Whisper mangle it while the bilingual model keeps `patient`, `chest pain` and
`aspirin` intact in Latin script. That contrast *is* the demo. Everything else (TTS reply,
memory, HUD) is garnish. Budget day 3 entirely for the TTS language-tagging step, because
that is where the time will actually go.

---

## 1. Arabic STT / ASR quality, September 2026

### 1.1 The dialect cliff

The most useful single source is **Arab Voices: Mapping Standard and Dialectal Arabic
Speech Technology** ([arXiv 2601.13319, 19 Jan 2026](https://arxiv.org/html/2601.13319v1)),
which aggregates 31 datasets across 14 dialects and evaluates 14 open models
(Whisper-large-v3, MMS, SeamlessM4T v2, Omnilingual/OmniASR, Qwen3). Best-system WER per
variety:

| Variety | Code | Best WER |
|---|---|---|
| Modern Standard Arabic | arb | **10.19** |
| Levantine | apc | 23.53 |
| Egyptian | arz | 34.80 |
| **Gulf / Khaleeji** | afb | **68.39** |
| Tunisian | aeb | 74.31 |
| Algerian | arq | 78.01 |
| Moroccan | ary | 81.77 |
| Hassaniyya | mey | 88.45 |

> 🚨 Gulf Arabic at 68 WER on open models is the finding that should most change your
> plans. If the take-home is demoed with a Khaleeji speaker on an open model, it fails.
> The commercial bilingual models (§2) are the only credible answer for Gulf.

Note: this paper evaluates **open models only — no commercial APIs.** Datasets used include
Common Voice, FLEURS, MGB-2, MGB-3, MGB-5, MASC, QASR, GALE, Casablanca and SADA; the
code-mixed sets it catalogues are **ArzEn, Mixat, SCC and ZAEBUC-Spoken**.

### 1.2 Open-weights leaderboard (multi-dialect, zero-shot)

The [Open Universal Arabic ASR Leaderboard](https://huggingface.co/spaces/elmresearchcenter/open_universal_arabic_asr_leaderboard)
(ELM Research Center; methodology published at
[Interspeech 2025](https://www.isca-archive.org/interspeech_2025/wang25_interspeech.pdf))
evaluates zero-shot multi-dialect generalisation over six test sets spanning MSA, Egyptian,
Gulf, Levantine and Maghrebi.

| Model | Avg WER | CommonVoice | MASC-C | MASC-N | MGB-2 | SADA | Casablanca | Date |
|---|---|---|---|---|---|---|---|---|
| **Audar-ASR-V1-Turbo** | **24.78** | 8.60 | 19.60 | 28.35 | 11.13 | 29.41 | 51.58 | [9 Jul 2026](https://www.audarai.com/news/introducing-audar-asr-v1) |
| Cohere Transcribe Arabic | 25.87 | 5.82 | 15.54 | 27.07 | — | 37.47 | 49.71 | [7 Jul 2026](https://cohere.com/blog/transcribe-arabic) |
| Munsit-1 (CNTXT AI) | 26.68 | — | — | — | — | — | — | [3 Aug 2026](https://munsit.com/blog/best-arabic-speech-to-text) |
| OmniASR-LLM-7B | 28.32 | 9.75 | 19.69 | 29.29 | — | 41.61 | 56.46 | 7 Jul 2026 |
| Qwen3-ASR-0.6B | 42.18 | — | — | — | — | — | — | 9 Jul 2026 |
| **Whisper Large v3** | **36.86** | 17.83 | 24.66 | 34.63 | — | 55.96 | 71.81 | 7 Jul 2026 |

Reading this table:

- **Whisper large-v3 is ~11 WER points behind the Arabic-specialist state of the art**, and
  the gap is worst exactly where it matters — Casablanca (multidialectal) 71.81 vs 49.71.
- **Casablanca is brutal for everyone.** Even the leader is at ~50 WER. Casablanca
  ([arXiv 2410.04527](https://arxiv.org/pdf/2410.04527)) is the honest multidialectal test;
  Common Voice AR is the flattering one (5.8–8.6 WER). Beware anyone quoting only
  Common Voice.
- **Audar-ASR-V1** explicitly ships Arabic-English code-switching via a `<tag:ar+en>`
  control token, trained on 300k+ hours; weights on Hugging Face, API invite-only. Its
  internal Gulf-Emirati set scores 30.02 WER — far better than the 68 above, but it is
  a *vendor-internal* set, so not comparable.
- **Cohere Transcribe Arabic** is Apache 2.0, free on Cohere's API with rate limits,
  RTFx 525 (vs Whisper's 146), and claims native-speaker preference over Whisper in
  95.8% of tests on accuracy, dialect faithfulness and code-switching robustness.
  It preserves the speaker's dialect rather than normalising to MSA.

### 1.3 Commercial providers — what each actually offers for Arabic

| Provider | Arabic status | Dialects | Realtime | Published Arabic WER |
|---|---|---|---|---|
| **Speechmatics** | `ar` + **`ar_en` bilingual pack**; medical variant | Gulf, Egyptian, Levantine, MSA | Yes, sub-second, same model as batch | 4.5% Arabic-only; 6.3% code-switched (**vendor**) |
| **ElevenLabs Scribe v2 / v2 Realtime** | Supported; docs tier Arabic as **"Good: >10% to ≤20% WER"** | Not broken out | Yes, ~150 ms | Tier only, no point estimate |
| **Deepgram Nova-3** | 17 Arabic locales (`ar`, `ar-EG`, `ar-SA`, `ar-AE`, `ar-IQ`, `ar-MA`…) | Gulf, Levantine, Egyptian/Nile, Maghrebi, Mesopotamian | Yes (streaming + batch) | None published; blog claims "~40% lower WER" unqualified |
| **Soniox v5** | 60+ languages incl. Arabic, mid-sentence switching | Not broken out | Yes, sub-200 ms | None published |
| **OpenAI (Whisper / gpt-4o-transcribe)** | Yes | Poor on dialect | Realtime API yes | 36.86 avg (Whisper, leaderboard) |
| **Google Chirp 3** | Yes, `auto` language inference | Weak on Gulf (see §2) | Yes | None published |
| **Azure AI Speech (CLID)** | Yes, segment-level LID | Multiple locales | Yes | None published |
| **AssemblyAI Universal 3.5 Pro** | Yes | Not broken out | Yes | 40.9% mixed error (per Speechmatics) |
| **Munsit / CNTXT AI** | Arabic-only specialist, 25+ dialects | All major | Yes, "sub-300 ms" (**vendor**) | 26.68 avg (leaderboard) |
| **Audar AI** | Arabic-first, open weights | Multi | Not stated | 24.78 avg (leaderboard) |
| **Cohere Transcribe Arabic** | Open weights, Apache 2.0 | Multi | Not stated | 25.87 avg (leaderboard) |

Sources: [Speechmatics languages docs](https://docs.speechmatics.com/speech-to-text/languages),
[ElevenLabs STT docs](https://elevenlabs.io/docs/overview/capabilities/speech-to-text),
[Deepgram models & languages](https://developers.deepgram.com/docs/models-languages-overview),
[Soniox Arabic](https://soniox.com/platform/arabic),
[Deepgram Nova-3 Arabic blog](https://deepgram.com/learn/nova-3-arabic-speech-to-text-production-grade-stt).
All retrieved 18 Sep 2026.

---

## 2. Code-switching (Arabic ↔ English, intra-sentence) — the make-or-break section

### 2.1 The one independent benchmark

**Benchmarking Commercial ASR Systems on Code-Switching Speech: Arabic, Persian, and German**
([arXiv 2605.19069](https://arxiv.org/abs/2605.19069), v1 18 May 2026, v3 22 May 2026).
Four language pairs — **Egyptian Arabic–English, Saudi Arabic (Najdi/Hijazi)–English**,
Persian–English, German–English — 300 samples each, natural conversational recordings by
native speakers, difficulty-stratified by a computed `H_Score`.

**Overall results (Table 4):**

| System | Mean WER | Mean BERTScore | CS pairs covered |
|---|---|---|---|
| **ElevenLabs Scribe v2** | **13.2%** | **0.936** | 4 |
| OpenAI gpt-4o-transcribe | 38.6% | 0.856 | 4 |
| Google Chirp 3 | 39.4% | 0.862 | 4 |
| Azure AI Speech (CLID) | 43.6% | 0.839 | 4 |
| Deepgram Nova-3 | 5.0% † | 0.959 † | **1 (German only)** |

† The paper explicitly excludes Deepgram from the ranking: *"Deepgram Nova-3 does not list
Arabic or Persian in its documented CS language support. For these pairs we suppress WER
and BERTScore and exclude the system from aggregate rankings."* Its 5.0% is German-only and
is **not** an Arabic result. Do not quote it as one.

**By difficulty quartile (Table 5) — this is the table that matters:**

| Quartile | ElevenLabs | Google Chirp 3 | OpenAI | Azure |
|---|---|---|---|---|
| Q1 (easiest) | 2.0% | 4.4% | 9.7% | 17.1% |
| Q2 | 13.9% | 30.8% | 46.2% | 46.4% |
| Q3 | 15.0% | 54.4% | 48.7% | 54.2% |
| **Q4 (hardest)** | **20.0%** | 61.5% | 45.2% | 52.2% |

> ⚠️ The 2.4-point gap between ElevenLabs and Google at Q1 becomes a **41.5-point gap at
> Q4**. Q4 is dominated by Arabic and Persian utterances with dense switching and
> morphological blending — i.e. exactly how your doctors speak. Aggregate WER numbers hide
> this completely. Never choose an Arabic code-switching ASR on an aggregate number.

**On Gulf specifically:** *"Google Chirp 3 performs worse on Saudi Arabic than on Egyptian
Arabic, suggesting that Gulf dialectal phonology remains less robustly covered than more
widely represented Arabic varieties."*

### 2.2 What actually happens to the English words

Three distinct behaviours, all documented:

1. **Kept in Latin script** — the good case. ElevenLabs is reported to pick one script
   convention and apply it coherently.
2. **Transliterated into Arabic script** — semantically correct, *scored as 100% wrong by
   WER*. This is the source of the ~3× inflation. It is also a genuine UI problem for you:
   `أسبرين` and `aspirin` must both map to the same drug downstream.
3. **Failure modes at switch boundaries** — the paper's architectural analysis notes that
   segment-level LID systems (Azure CLID) are *"structurally limited to producing one
   script per recognition segment"*, so a mid-segment switch cannot be represented at all.

Whisper specifically has a well-documented additional pathology: it will return
**Arabic speech transliterated into Latin script** even with `language="ar"` set
(e.g. "marhaban" instead of "مرحبا") — reported repeatedly on the
[OpenAI developer forum](https://community.openai.com/t/issue-with-arabic-transcription-in-whisper-large-v3-turbo-naah-naahe/1291617).
Fine-tunes exist specifically to patch this (e.g.
[Arabic Whisper CodeSwitching Edition](https://dataloop.ai/library/model/mohamedrashad_arabic-whisper-codeswitching-edition/)),
which is itself evidence base Whisper is inadequate here.

### 2.3 Named code-switching benchmarks

- **ArzEn** (Hamed, Vu & Abdennadher 2020) — Egyptian Arabic–English, 6,213 sentences,
  **66.9% code-mixed**, 30.0% monolingual Arabic, 3.1% monolingual English. Extended by
  **ArzEn-ST** ([arXiv 2211.12000](https://arxiv.org/pdf/2211.12000)) into a three-way
  speech-translation corpus with ASR/MT/ST baselines, and used by
  **ArzEn-LLM** ([arXiv 2406.18120](https://arxiv.org/pdf/2406.18120)).
- **Mixat** — Emirati Arabic–English code-mixed; catalogued in Arab Voices.
- **SCC**, **ZAEBUC-Spoken** — additional code-mixed sets in the Arab Voices catalogue.
- **SwitchLingua** (Xie et al. 2026) — 12-language synthesized+recorded CS benchmark.
- **SAGE** ([arXiv 2506.22143](https://arxiv.org/pdf/2506.22143)) — spliced-audio data
  augmentation for low-resource Arabic-English CS ASR.
- The 2605.19069 benchmark set itself is published on Hugging Face.

### 2.4 The vendor that built for exactly this

[**Speechmatics**](https://www.speechmatics.com/company/articles-and-news/arabic-english-bilingual-speech-to-text)
(6 Mar 2026) shipped a single bilingual Arabic–English model rather than two monolingual
ones. Claims: **6.3% WER on mixed speech** (vs Google 9.7%, "35% fewer errors") and
**4.5% on Arabic-only** (vs Google 5.9%, Whisper 6.2%). Gulf + Egyptian + Levantine.
Sub-second latency, same model realtime and batch, cloud / on-prem / on-device.

Four days later ([10 Mar 2026](https://finance.yahoo.com/news/speechmatics-achieves-world-first-bilingual-125400210.html))
they announced an **Arabic–English medical** variant: trained on twice the vocabulary of
their English medical model, covering **ICD-10-CM codes, drug names, dosages and clinical
shorthand "regardless of which language carries them"**, built from real clinical audio
with dialect variation. Their own framing of the problem
([5 Mar 2026](https://www.speechmatics.com/company/articles-and-news/your-voice-agent-speaks-perfect-arabic-thats-the-problem))
is almost verbatim your brief: *"A doctor names a drug in English and finishes the sentence
in Arabic."*

Their newer general model **Melia 1** (launched June 2026) was benchmarked
[1 Sep 2026](https://www.speechmatics.com/company/articles-and-news/melia-code-switching-arabic-mandarin-tamil)
at **15.1% mixed error rate on Arabic–English with no language hints**, vs Soniox v5 33.2%,
AssemblyAI Universal 3.5 Pro 40.9%, Amazon 45.6%. Vendor-run, unnamed test set — treat as
directional, not as ground truth.

**Practical config.** The [Speechmatics languages docs](https://docs.speechmatics.com/speech-to-text/languages)
list an **"Arabic & English bilingual" pack, language code `ar_en`**, described as *"ideal
when transcribing Arabic and English in the same media file or stream."* Note a
documentation conflict: the [Pipecat Speechmatics service docs](https://docs.pipecat.ai/server/services/stt/speechmatics)
document bilingual modes via `language` + `domain` (e.g. `Language.ES` + `domain="bilingual-en"`,
plus packs `cmn_en`, `en_ms`, `en_ta`) and **do not list `ar_en`**. Resolve this against the
live API on day 1 — try `ar_en` as a language code first, then `language="ar", domain="bilingual-en"`.
Plugins exist for both [LiveKit](https://docs.livekit.io/agents/integrations/speechmatics/)
(`livekit-plugins-speechmatics`) and Pipecat.

---

## 3. Arabic TTS, September 2026

### 3.1 Latency

Measured TTFT, [SILMA benchmark, 15 Sep 2026](https://silma.ai/blog/best-low-latency-arabic-text-to-speech-apis-for-developers-2026-benchmark):

| Model | Min TTFT | Median TTFT | Cost/min |
|---|---|---|---|
| Cartesia Sonic 3.5 | 102 ms | **120 ms** | — |
| ElevenLabs Flash v2.5 | 131 ms | 137 ms | $0.050 |
| Deepgram Aura-2 | 251 ms | 256 ms | $0.027 |
| SILMA TTS v2 | 279 ms | 280 ms | $0.025 |
| ElevenLabs v3 | 677 ms | 730 ms | $0.100 |

> ⚠️ This benchmark does **not** break results out by language. These are global TTFT
> figures, not Arabic-specific. Arabic TTFT is unverified for every provider.

ElevenLabs' own docs claim ~75 ms model latency for Flash v2.5; the 137 ms measured figure
is the honest one to plan against.

### 3.2 Dialect coverage — this is where providers diverge sharply

| Provider | Arabic dialect coverage | Source |
|---|---|---|
| **Azure Neural TTS** | ~20 locales: `ar-SA`, `ar-EG`, `ar-AE`, `ar-LB`, `ar-OM`, `ar-IQ`, `ar-MA`… named voices each (Salma/ar-EG, Zariyah/ar-SA) | [MS Learn](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support) |
| **ElevenLabs Multilingual v2** | Arabic listed as "Arabic (Saudi Arabia, UAE)"; Egyptian/Gulf/Moroccan voices exist in the voice library | [ElevenLabs models](https://elevenlabs.io/docs/overview/models) |
| **ElevenLabs Flash v2.5** | Arabic among 32 languages | same |
| **ElevenLabs v3** | Arabic among 70+ languages | same |
| **Google Cloud (Chirp 3 HD)** | **`ar-XA` — MSA only.** No Gulf, Levantine, Egyptian or Maghrebi voice variants documented | [Google TTS voice list](https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types) |
| **Amazon Polly** | MSA + Gulf (`ar-AE`) | [Munsit TTS roundup, 30 Jul 2026](https://munsit.com/blog/best-arabic-tts) |
| **Cartesia Sonic 3 / 3.6** | Arabic among 42 / 44 languages; 3.6 lists "several Arabic locales" | [Cartesia docs](https://docs.cartesia.ai/build-with-cartesia/tts-models/latest) |
| **Munsit / Faseeh TTS** | Gulf, MSA, Levantine, Egyptian, Maghrebi + **dedicated Tashkīl (diacritization) API endpoint** | Munsit roundup |
| **Soniox TTS** | Arabic voices, "starts speaking in under a second", explicitly handles "alphanumerics, names, borrowed words, language switching" | [Soniox Arabic](https://soniox.com/platform/arabic) |

### 3.3 Diacritization — the structural Arabic TTS problem

Arabic script omits short vowels. `كتب` is *kataba* ("he wrote"), *kutub* ("books"), or
*kutiba* ("it was written") — same letters, three pronunciations, three meanings. TTS must
restore diacritics (tashkīl) before phonemisation, and this is a genuine NLP task, not a
lookup.

- Microsoft reports that **improving diacritic prediction alone produced a 78% reduction
  in pronunciation errors** for `ar-SA` and `ar-EG` voices
  ([Azure AI blog](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/azure-ai-voices-in-arabic-improved-pronunciation/4360306)).
- 2026 research (KSAA-2026 shared task at OSACT7/LREC 2026) finds **text-only Seq2Seq
  diacritizers outperform off-the-shelf multimodal/ASR-based ones**
  ([Fine-Tashkeel, ACL Anthology](https://aclanthology.org/2026.osact-1.31/);
  [Thaka, arXiv 2605.25928](https://arxiv.org/pdf/2605.25928)).
- Practical escape hatches: Munsit exposes diacritization as its own API so you can fix
  pronunciation deterministically instead of regenerating audio; Azure and Polly accept
  SSML with IPA phonemes; ElevenLabs' route is phonetic respelling.

### 3.4 Embedded English inside an Arabic sentence — the actual risk

ElevenLabs' documentation is explicit: language detection is **"automatic but unreliable
for short text or codemixed input — always pass explicit language tags in the text
parameter (e.g. `[EN] Hello [ES] Hola`) for production systems to avoid mispronunciation"**,
and further warns to *"avoid mixing right-to-left scripts (Arabic, Hebrew) without explicit
markup."*

> 🚨 **This is the single biggest implementation risk in the project.** Your LLM will emit
> `"المريض محتاج aspirin مرتين يومياً"` as plain text. Handed to TTS untagged, the English
> token is a coin flip. You need a tagging step between LLM and TTS: either (a) instruct
> the LLM to emit `[AR]`/`[EN]` span tags directly in its output, or (b) run a cheap regex
> on Unicode script ranges (Arabic block `U+0600–U+06FF` vs Latin) to segment and tag.
> Option (b) is ~20 lines, deterministic, and is what I would ship in 3 days.

Independent corroboration that this is a real production problem: TTS providers
"mispronounce names, addresses, medical terms, product names, acronyms" and *"the
mispronunciation isn't even consistent — the model will pronounce the same word differently
across calls"* ([Rime, TTS best practices 2026](https://www.rime.ai/resources/tts-voice-best-practices)).
Hence the existence of pronunciation-dictionary features
([Telnyx](https://telnyx.com/release-notes/tts-pronunciation-dictionaries)) — worth wiring
a small dictionary of your demo's drug names if time permits.

---

## 4. Realtime speech-to-speech APIs and Arabic

### OpenAI Realtime

- Arabic **is** supported. `gpt-4o-realtime` documents 70+ input languages; OpenAI states
  it only lists languages that came in **under 50% WER**, and *"the model returns results
  for languages not listed but the quality will be low."* Arabic makes the list, but that
  is a low bar — a 50% WER threshold tells you nothing about Egyptian vs Gulf.
- `gpt-realtime-translate` supports 70+ input / 13 output languages, with Arabic named
  among the better-performing output languages
  ([OpenAI cookbook](https://developers.openai.com/cookbook/examples/voice_solutions/realtime_translation_guide)).
- **No dialect breakdown is published anywhere.** There is no `ar-EG` vs `ar-SA` story.
- Known pathology: with `input_audio_transcription` enabled, **Arabic speech sometimes
  comes back transcribed as English**. Workaround is to set the `language` parameter
  explicitly on `input_audio_transcription`
  ([OpenAI forum, 10 Feb 2025](https://community.openai.com/t/arabic-transcription-issue-with-openai-realtime-api/1117262)).
  Old report, but the underlying language-lock behaviour is the same class of bug the
  code-switching benchmark documents.

### Gemini Live

- Arabic **is** in the documented list — **`ar`, one of 99 supported languages**
  ([Live API capabilities](https://ai.google.dev/gemini-api/docs/live-api/capabilities),
  retrieved 18 Sep 2026). **No regional variants** (`ar-EG`, `ar-XA`) are documented.
- Native-audio models *"can switch between languages naturally during conversation"* — the
  closest thing to a documented code-switching claim from either realtime vendor, though
  it is about turn-level switching, not intra-sentence.
- **Stability is a live concern, independent of language.** Through 2026 the Google AI
  developer forum carries reports of: audio regression after the 9 Mar 2026 update;
  voice/volume degradation on outputs longer than ~1 min; premature `turnComplete` causing
  [mid-sentence truncation](https://github.com/googleapis/python-genai/issues/2117); and,
  as recently as **5 Sep 2026, first-audio latency of 16–26 s** on
  `gemini-3.1-flash-live-preview`
  ([forum thread](https://discuss.ai.google.dev/t/gemini-3-1-flash-live-preview-first-audio-16-26-s-since-2026-09-05-09-00-utc-reproduced-on-an-isolated-project-same-model-on-2026-09-03/180927)).

> ⚠️ **Recommendation: do not build the Arabic demo on a speech-to-speech API.** Neither
> vendor publishes Arabic dialect quality, neither lets you swap the ASR, and a black-box
> S2S pipeline gives you nothing to *show*. A cascade lets you put the code-switched
> transcript on screen — which is the whole point. Keep Gemini Live as an optional toggle
> if you already have one wired from the English build.

---

## 5. Arabic LLM quality for medical reasoning

### 5.1 MedAraBench — the large one

[arXiv 2602.01714](https://arxiv.org/html/2602.01714), 2 Feb 2026. **24,883 Arabic
multiple-choice medical questions**, 19 specialties, five difficulty levels (Y1–Y5),
digitised from regional medical school exams, quality-checked by clinicians and
LLM-as-judge.

| Model | Accuracy |
|---|---|
| GPT-o3 | **0.765** |
| GPT-5 | 0.764 |
| Claude Sonnet 4 | 0.694 |
| GPT-4.1 | 0.673 |
| Gemini 2.0 Flash | 0.654 |
| DeepSeek-Chat-v3 | 0.620 |
| Qwen-Plus | 0.618 |
| Llama-3.3-70B | 0.547 |
| **Fanar-C-1-8.7B** (Qatar) | 0.498 |
| **ALLaM-7B** (Saudi) | 0.447 |
| MedGemma-4B | 0.390 |

Two conclusions, both actionable: **frontier general models win by 25+ points over Arabic-
specialist models**, and even the winner "does not match expert-level performance."

### 5.2 MedArabiQ — the diagnostic one

[arXiv 2505.03427](https://arxiv.org/html/2505.03427). Seven Arabic medical tasks (MCQ,
fill-in-blank, patient–doctor Q&A). Findings that matter for a clinical copilot:

- **No single model dominates.** Gemini 1.5 Pro 57.5% and Claude 3.5 Sonnet 53.5% lead on
  MCQ; DeepSeek v3 79.7% on fill-in-blank-with-choices; **Jais 85.7% on open-ended
  patient–doctor Q&A** — an Arabic-specialist model winning the *conversational* task while
  losing the knowledge tasks. If your copilot is dialogue-shaped, that is worth knowing.
- **Cognitive bias is devastating.** GPT-4 fell from **66.3% → 35.7%** under bias-injected
  conditions. A copilot that echoes a doctor's stated hypothesis will amplify anchoring.
- **The benchmark is MSA-only**, which the authors flag as a limitation: it "may not
  reflect real clinical communication using dialects." So the published numbers are an
  *upper bound* on real dialectal clinical performance.
- Authors' conclusion: *"task specificity may be more critical than language specificity
  for Arabic medical tasks."*

### 5.3 Other Arabic medical evaluation

- **AraHealthQA 2025** ([ACL Anthology](https://aclanthology.org/2025.arabicnlp-sharedtasks.18/)) —
  first shared task on Arabic health QA, two tracks: MentalQA and MedArabiQ, the latter
  spanning 12 specialties. Winning approaches were prompt-engineering + ensembling over
  **Gemini 2.5 Flash**, not fine-tuned Arabic models
  ([arXiv 2509.11365](https://arxiv.org/pdf/2509.11365)).
- **Arabic Healthcare Understanding & Reasoning** ([arXiv 2508.15797](https://arxiv.org/html/2508.15797v1)).
- **QIMMA** ([arXiv 2604.03395](https://arxiv.org/pdf/2604.03395)) argues many Arabic
  benchmarks are themselves unreliable — worth a caveat line in your write-up.

### 5.4 Arabic-specialist LLMs, for completeness

- **Falcon-H1-Arabic** (TII, [5 Jan 2026](https://falcon-lm.github.io/blog/falcon-h1-arabic/)) —
  hybrid Mamba-Transformer; 7B scores 71.47% avg on the Open Arabic LLM Leaderboard
  (beating Fanar-1-9B and ALLaM-7B), 34B scores 75.36% (beating Qwen2.5-72B and
  Llama-3.3-70B). Strong on 3LM (STEM), ArabCulture, AraDice (dialect).
- **Fanar 2.0** (QCRI/HBKU, [arXiv 2603.16397](https://arxiv.org/pdf/2603.16397)) —
  Fanar-2-27B-Instruct, Apache 2.0, ~Mar 2026.
- **ALLaM** — now under HUMAIN (Saudi).

> These are excellent for Arabic *fluency and culture* and poor for *medicine*. For a
> clinical copilot, use a frontier model and spend your effort on the prompt.

---

## 6. RTL / bilingual frontend

### 6.1 The core bug: `dir="auto"` uses first-strong, not majority

The HTML `dir="auto"` attribute resolves direction from the **first strong directional
character** in the element, per the Unicode Bidirectional Algorithm. It is not a vote.
[Direction is not alignment (13 Sep 2026)](https://dev.to/shayan_salehirad/direction-is-not-alignment-rendering-mixed-persian-and-english-text-2e67)
puts it precisely: *"Appending Persian after an existing unisolated `Hello` does not make it
switch merely because Persian now dominates."*

For your live captions this means: **a caption line that begins with an English word renders
entirely LTR**, punctuation lands on the wrong side, and the Arabic reads right-aligned in a
left-aligned block. The next line, beginning in Arabic, flips. The pane visually stutters.

**Worse during streaming:** tokens arrive incrementally. If the first token is Arabic the
line commits RTL; if the first arriving token happens to be `patient` it commits LTR and the
rest of the Arabic reflows under an LTR paragraph. Direction can visibly flip mid-stream.

### 6.2 Fixes, in order of effort

1. **Compute direction per line from dominant script, not first character.** Count Arabic-
   block codepoints (`U+0600–U+06FF`, plus `U+0750–U+077F`, `U+FB50–U+FDFF`, `U+FE70–U+FEFF`)
   vs Latin, set `dir` explicitly. This is the single highest-value fix and is ~15 lines.
   [`bidi-dir`](https://github.com/avizeapp/bidi-dir) is a zero-dependency library that does
   exactly this — "resolve text direction by dominant script, not by the first character;
   fixes mixed Persian/Arabic/Hebrew text that `dir="auto"` renders backwards."
2. **Isolate every foreign-script span with `<bdi>`.** Wrap each Latin run inside an Arabic
   line: `<p dir="rtl">عندي <bdi dir="ltr">patient</bdi> عنده <bdi dir="ltr">chest pain</bdi></p>`.
   `<bdi>` is exactly "treat this text in isolation from its surroundings"
   ([MDN/CodeLucky](https://codelucky.com/html-bdi-tag/)). Equivalent CSS is
   `unicode-bidi: isolate`.
3. **Separate the three concerns.** Direction (`dir`), alignment (`text-align`) and
   isolation (`<bdi>`) are independent. The named "critical mistake" is conflating direction
   with alignment. You can legitimately want `dir="rtl"` with `text-align: left` in a
   caption rail.
4. **Freeze direction once committed during a stream.** Decide the line's `dir` on first
   flush and don't recompute on every token, or accept flicker.
5. **Next.js specifics.** Next does **not** set direction from `lang` — you must set
   `document.documentElement.dir` yourself, usually from your i18n layer
   ([next-i18next discussion #1738](https://github.com/i18next/next-i18next/discussions/1738)).
   Use CSS logical properties (`margin-inline-start`, `padding-inline-end`, `inset-inline`)
   throughout rather than left/right so one `dir` flip restyles the whole app; Tailwind's
   `ms-*`/`me-*`/`ps-*`/`pe-*` and `rtl:`/`ltr:` variants cover this.
   ([LeanCode RTL in React](https://leancode.co/blog/right-to-left-in-react),
   [better-i18n RTL guide](https://better-i18n.com/en/blog/rtl-support-css-react-guide/))
6. **If you want the heavy artillery**, [BidiLens](https://github.com/CodeinScrubs/BidiLens)
   bundles per-block direction policy, inline isolation, **streaming stability**, and
   bidi-control auditing with React adapters. Probably overkill for 3 days, but its
   existence tells you streaming bidi is a known hard problem.

### 6.3 Security note worth one line in the write-up

Unicode bidi control characters (RLO/LRO, `U+202A`–`U+202E`) can visually reorder text
without changing its bytes — the "Trojan Source" class of attack. If transcripts are ever
rendered into a clinical record, strip bidi control characters from ASR output before
storage. BidiLens ships "bidi-control auditing" for this reason.

---

## 7. Verdict

### 7.1 Is it buildable in ~3 part-time days on free/cheap tiers?

**Yes — GO.** The decisive change is that Arabic-English code-switching is now a
line item you buy rather than a model you train. Concretely:

- **Speechmatics free tier**: 480 min/month total, **240 realtime minutes**, 2 concurrent
  realtime sessions, 3,000 Voice Agent minutes. Pro is $0.0067/min realtime (~$0.40/hr).
  ([Speechmatics pricing](https://www.speechmatics.com/pricing) via
  [PulseSignal](https://getpulsesignal.com/pricing/speechmatics), retrieved 18 Sep 2026 —
  **verify on the pricing page directly; tier details move.**)
- **Groq Whisper large-v3-turbo free tier**: 20 RPM, 2,000 req/day, 28,800 audio sec/day,
  $0.04/hr paid — the cheapest possible *baseline* to A/B against
  ([Groq docs](https://console.groq.com/docs/model/whisper-large-v3-turbo)).
- **Cohere Transcribe Arabic**: free on Cohere's API with rate limits, Apache 2.0 weights.
- **Soniox**: $0.12/hr realtime STT, $0.10/hr async, ~$0.70/hr TTS, no free tier documented.
- **Munsit**: free 10,000 credits (~30 min), then $8/mo; $0.12/hr realtime.
- **ElevenLabs**: Scribe realtime from ~$0.28/hr; TTS Flash v2.5 ~$0.05/min.

A three-day budget of a few dollars covers the whole build.

### 7.2 The single biggest risk

**The TTS output leg — specifically, rendering an LLM-generated Arabic sentence containing
English drug names without mispronouncing them.** Ranked reasoning:

1. STT code-switching: **solved by vendor choice.** Low risk.
2. TTS code-switching: **not solved by vendor choice.** ElevenLabs' own docs say automatic
   detection is unreliable on codemixed input and mandate explicit tags. You must build the
   tagging step. Unknowns compound: diacritization ambiguity on the Arabic, phoneme choice
   on the English, and no published Arabic-specific TTFT from anyone.
3. Second-order risk: **240 free realtime minutes disappears fast** when you're re-running
   the same test sentence 200 times. Record 5–10 canonical WAV files on day 1 and iterate
   against files, not a live mic.
4. Third: **Gulf dialect.** If your demo audio is Khaleeji rather than Egyptian, every
   number in §1.1 gets worse. Control this — pick your demo speaker.

### 7.3 Minimum viable version that still impresses

Strip to the contrast, not the pipeline:

1. **Mic → Speechmatics `ar_en` realtime → caption pane with correct bidi.** That alone is
   the demo.
2. **A/B toggle to Whisper-large-v3 via Groq** on the same audio. Side by side. The
   audience sees `chest pain` survive on one side and dissolve into Arabic transliteration
   on the other. This is the single most persuasive 20 seconds you can build.
3. **One LLM turn** — a clinical summary or a drug-interaction flag — proving the code-
   switched transcript is machine-usable downstream (e.g. `aspirin` and `أسبرين` normalise
   to the same RxNorm-style key).
4. **TTS reply with the script-range tagger** (§3.4 option b). Even a 20-line regex tagger
   demonstrates you understood the problem.
5. **Skip**: speech-to-speech, dialect ID, diacritization models, Arabic-specialist LLMs,
   any fine-tuning. All are day-5+ work.

### 7.4 Ranked stack for Arabic

| Rank | Stack | When to pick it |
|---|---|---|
| **1** | Speechmatics `ar_en` realtime → GPT-5/o3 → ElevenLabs Flash v2.5 + script tagger | Default. Only true bilingual model, medical variant exists, free tier sufficient, plugins in both Pipecat and LiveKit. |
| **2** | ElevenLabs Scribe v2 Realtime (~150 ms) → GPT-5 → ElevenLabs Flash v2.5 | If Speechmatics' `ar_en` config fights you on day 1. Independently benchmarked best on code-switching; one vendor for STT+TTS; ~150 ms. |
| **3** | Soniox v5 realtime (sub-200 ms, $0.12/hr) → GPT-5 → Soniox TTS | Cheapest coherent single-vendor bilingual option; explicitly claims mid-sentence switching and handles "borrowed words". Weaker third-party validation (33.2% mixed error in Speechmatics' own test). |
| **4** | Groq Whisper-v3-turbo → GPT-5 → ElevenLabs | **Baseline only.** Use as the losing side of the A/B. Not viable as the product. |
| **5** | Gemini Live native audio (Arabic `ar`) | Optional toggle if already wired. No dialect docs, 2026 stability complaints, and it hides the transcript — which is your demo. |
| **—** | Deepgram Nova-3 Arabic | **Avoid for this use case.** 17 Arabic locales but Arabic is excluded from the code-switching multilingual mode. Fine for monolingual Arabic. |

---

## 8. What I could not verify

Listed explicitly, as requested.

| Claim | Status |
|---|---|
| **Per-language-pair WER for Egyptian and Saudi Arabic in arXiv 2605.19069** | **NOT VERIFIED.** The paper presents these only in Figures 2 and 3 (raster images); the text says "Figures 2 and 3 report the per-language-pair results, making separate result tables unnecessary." I have the overall means (Table 4) and the difficulty quartiles (Table 5) verbatim from the PDF. An earlier automated read of the PDF produced per-pair numbers around "45–50% for OpenAI on Egyptian" — **I could not confirm those in the extracted text and have excluded them.** Do not cite them. |
| Speechmatics 6.3% / 4.5% / 15.1% figures | **Vendor self-reported**, test set unnamed, not independently reproduced. |
| Melia 1 competitor numbers (Soniox 33.2%, AssemblyAI 40.9%, Amazon 45.6%) | **Vendor-run comparison**, unnamed test set. |
| Deepgram Nova-3 Arabic WER | **No published number exists.** The "~40% lower WER" blog claim has no named benchmark and no date on the page. |
| ElevenLabs Arabic-specific WER | Only a docs *tier*: "Good, >10% to ≤20% WER". No point estimate, no dialect breakdown. |
| Munsit "sub-300 ms realtime" and "<150 ms TTS" | **Vendor self-reported.** No independent measurement found. |
| Arabic-specific TTS TTFT for any provider | **NOT VERIFIED.** The SILMA 15 Sep 2026 benchmark gives global TTFT only, not per-language. |
| Whether the Speechmatics **medical** Arabic-English model is available self-serve / on the free tier | **NOT VERIFIED.** Press release says "available now in our portal"; no pricing or tier detail found. Check before relying on it. |
| Exact Speechmatics bilingual Arabic config parameter | **CONFLICTING.** Speechmatics docs list pack `ar_en`; Pipecat's service docs list bilingual packs `cmn_en`/`en_ms`/`en_ta` + `domain="bilingual-en"` and **do not include `ar_en`**. Resolve against the live API. |
| Whether Scribe v2 Realtime covers the same 90+ languages as batch Scribe v2 | **NOT STATED** in ElevenLabs docs. Both are described as "90+ languages" but no realtime language list is published. |
| Arabic quality reports for Gemini Live specifically | **NONE FOUND.** All 2026 forum complaints are language-agnostic (compression, truncation, latency regressions). |
| Arabic quality reports for OpenAI Realtime specifically | Only a **Feb 2025** forum report of Arabic being returned in English. No 2026 Arabic-specific evaluation found. |
| Whisper large-v3 vs large-v3-turbo Arabic difference | **NOT FOUND.** No source compares the two on Arabic. Leaderboard figures are for large-v3. |
| Modern commercial WER on MGB-2 / MGB-3 | Only Audar-ASR-V1-Turbo publishes MGB-2 (11.13). **No commercial API publishes MGB-2 or MGB-3.** |
| Gulf-dialect WER for any commercial provider | **NOT PUBLISHED by anyone.** The 68.39 figure is open models only. Audar's 30.02 Gulf-Emirati number is a vendor-internal test set. |
| Speechmatics free-tier exact limits | Sourced from a third-party pricing aggregator, not the vendor page. Verify directly. |
| Cartesia Sonic Arabic *quality* | Language support is documented (42→44 languages incl. Arabic); no Arabic quality or dialect evaluation exists. |
| Artificial Analysis "Scribe v2 first at 2.3% AA-WER (Feb 2026)" | This is an **aggregate multilingual** figure surfaced via search summary; I did not verify it on Artificial Analysis directly and it is **not** an Arabic number. |

---

## Sources

- [Arab Voices: Mapping Standard and Dialectal Arabic Speech Technology, arXiv 2601.13319](https://arxiv.org/html/2601.13319v1) — 19 Jan 2026
- [Benchmarking Commercial ASR Systems on Code-Switching Speech, arXiv 2605.19069](https://arxiv.org/abs/2605.19069) — May 2026
- [Open Universal Arabic ASR Leaderboard](https://huggingface.co/spaces/elmresearchcenter/open_universal_arabic_asr_leaderboard) · [Interspeech 2025 paper](https://www.isca-archive.org/interspeech_2025/wang25_interspeech.pdf)
- [Casablanca: Data and Models for Multidialectal Arabic Speech Recognition, arXiv 2410.04527](https://arxiv.org/pdf/2410.04527)
- [Cohere Transcribe Arabic](https://cohere.com/blog/transcribe-arabic) — 7 Jul 2026
- [Audar-ASR-V1](https://www.audarai.com/news/introducing-audar-asr-v1) — 9 Jul 2026
- [Best Arabic Speech to Text in 2026 (Munsit)](https://munsit.com/blog/best-arabic-speech-to-text) — 3 Aug 2026
- [Speechmatics: Arabic–English bilingual model](https://www.speechmatics.com/company/articles-and-news/arabic-english-bilingual-speech-to-text) — 6 Mar 2026
- [Speechmatics: Arabic–English medical model (press)](https://finance.yahoo.com/news/speechmatics-achieves-world-first-bilingual-125400210.html) — 10 Mar 2026
- [Speechmatics: Your voice agent speaks perfect Arabic. That's the problem.](https://www.speechmatics.com/company/articles-and-news/your-voice-agent-speaks-perfect-arabic-thats-the-problem) — 5 Mar 2026
- [Speechmatics: Melia 1 code-switching](https://www.speechmatics.com/company/articles-and-news/melia-code-switching-arabic-mandarin-tamil) — 1 Sep 2026
- [Speechmatics languages docs](https://docs.speechmatics.com/speech-to-text/languages) · [LiveKit plugin](https://docs.livekit.io/agents/integrations/speechmatics/) · [Pipecat service](https://docs.pipecat.ai/server/services/stt/speechmatics)
- [ElevenLabs models](https://elevenlabs.io/docs/overview/models) · [STT capabilities](https://elevenlabs.io/docs/overview/capabilities/speech-to-text) · [Scribe v2 announcement](https://elevenlabs.io/blog/introducing-scribe-v2) (9 Jan 2026) · [Scribe v2 Realtime](https://elevenlabs.io/realtime-speech-to-text)
- [Deepgram models & languages overview](https://developers.deepgram.com/docs/models-languages-overview) · [Nova-3 Arabic](https://deepgram.com/learn/nova-3-arabic-speech-to-text-production-grade-stt)
- [Soniox Arabic platform](https://soniox.com/platform/arabic) · [Soniox pricing](https://soniox.com/pricing)
- [Groq whisper-large-v3-turbo](https://console.groq.com/docs/model/whisper-large-v3-turbo)
- [SILMA Arabic TTS latency benchmark](https://silma.ai/blog/best-low-latency-arabic-text-to-speech-apis-for-developers-2026-benchmark) — 15 Sep 2026
- [Best Arabic TTS Tools (Munsit)](https://munsit.com/blog/best-arabic-tts) — 30 Jul 2026
- [Azure AI Arabic voices, improved pronunciation](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/azure-ai-voices-in-arabic-improved-pronunciation/4360306) · [Azure language support](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support)
- [Google Cloud TTS voices](https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types) · [Chirp 3 HD](https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd)
- [Cartesia TTS models](https://docs.cartesia.ai/build-with-cartesia/tts-models/latest)
- [Gemini Live API capabilities](https://ai.google.dev/gemini-api/docs/live-api/capabilities) · [Gemini Live latency regression report](https://discuss.ai.google.dev/t/gemini-3-1-flash-live-preview-first-audio-16-26-s-since-2026-09-05-09-00-utc-reproduced-on-an-isolated-project-same-model-on-2026-09-03/180927) (5 Sep 2026) · [truncation issue](https://github.com/googleapis/python-genai/issues/2117)
- [OpenAI realtime translation guide](https://developers.openai.com/cookbook/examples/voice_solutions/realtime_translation_guide) · [Arabic transcription issue](https://community.openai.com/t/arabic-transcription-issue-with-openai-realtime-api/1117262) (10 Feb 2025)
- [MedAraBench, arXiv 2602.01714](https://arxiv.org/html/2602.01714) — 2 Feb 2026
- [MedArabiQ, arXiv 2505.03427](https://arxiv.org/html/2505.03427)
- [AraHealthQA 2025 shared task](https://aclanthology.org/2025.arabicnlp-sharedtasks.18/) · [!MSA system paper, arXiv 2509.11365](https://arxiv.org/pdf/2509.11365)
- [Arabic Healthcare Understanding & Reasoning, arXiv 2508.15797](https://arxiv.org/html/2508.15797v1) · [QIMMA, arXiv 2604.03395](https://arxiv.org/pdf/2604.03395)
- [Falcon-H1-Arabic](https://falcon-lm.github.io/blog/falcon-h1-arabic/) — 5 Jan 2026 · [Fanar 2.0, arXiv 2603.16397](https://arxiv.org/pdf/2603.16397)
- [ArzEn-ST, arXiv 2211.12000](https://arxiv.org/pdf/2211.12000) · [ArzEn-LLM, arXiv 2406.18120](https://arxiv.org/pdf/2406.18120) · [SAGE, arXiv 2506.22143](https://arxiv.org/pdf/2506.22143)
- [Fine-Tashkeel, KSAA-2026](https://aclanthology.org/2026.osact-1.31/) · [Thaka, arXiv 2605.25928](https://arxiv.org/pdf/2605.25928)
- [Direction is not alignment](https://dev.to/shayan_salehirad/direction-is-not-alignment-rendering-mixed-persian-and-english-text-2e67) — 13 Sep 2026 · [bidi-dir](https://github.com/avizeapp/bidi-dir) · [BidiLens](https://github.com/CodeinScrubs/BidiLens) · [HTML bdi](https://codelucky.com/html-bdi-tag/) · [RTL in React (LeanCode)](https://leancode.co/blog/right-to-left-in-react) · [next-i18next direction discussion](https://github.com/i18next/next-i18next/discussions/1738)
- [Rime TTS best practices 2026](https://www.rime.ai/resources/tts-voice-best-practices) · [Telnyx pronunciation dictionaries](https://telnyx.com/release-notes/tts-pronunciation-dictionaries)

*Compiled 18 September 2026.*
