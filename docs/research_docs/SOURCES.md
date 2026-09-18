# Source quality map — add these to NotebookLM alongside the PDFs

**Date:** 2026-09-18 · **Purpose:** the eight audio-AI research docs are Perplexity syntheses. This maps which parts rest on primary sources and which don't, and lists the papers to add directly so NotebookLM has something authoritative to ground against.

## Read this first

**Ranked by citation count, the top sources in these docs are content farms and vendor marketing** — gradium.ai (56 citations), inworld.ai (39), arunbaby.com (39), heardright.app (26), praveentn.live (25), smallest.ai (22), theorempath.com (13), localaimaster.com (13). Across all eight docs there are only ~43 arXiv citations.

That matters because **NotebookLM will synthesise confident study notes from whatever it is given**, and you will carry those into a technical interview where someone builds voice agents for a living.

**The fix is cheap:** add the primary papers below as sources alongside the PDFs. NotebookLM accepts arXiv URLs directly. Where a paper and a blog disagree, the paper wins — and you will be able to see the disagreement, which you cannot do now.

## Where the docs are weakest — and it's the load-bearing part

| Doc | Primary-source citations | Verdict |
|---|---|---|
| TTS architectures | 37 | Well sourced |
| Turn detection and endpointing | 36 | Well sourced |
| Full-duplex conversation modelling | 30 | Well sourced |
| Evaluating voice agents | 15 | Adequate |
| ASR architectures | 13 | Adequate |
| **Cascaded vs. end-to-end** | **0** | **Blogs only** |
| **How audio becomes consumable** | **0** | **Blogs only** |
| **Streaming and latency engineering** | **0** | **Blogs only** |

The three unsourced docs cover **the architecture decision you are making and the system you are building**. That's where to spend the effort.

## Primary sources already cited in the docs

Verified present in the markdown — safe to add directly.

| Source | Topic |
|---|---|
| [arxiv.org/abs/2510.07037](https://arxiv.org/abs/2510.07037) | — |
| [arxiv.org/abs/2608.09930](https://arxiv.org/abs/2608.09930) | — |
| [arxiv.org/html/2601.04233v1](https://arxiv.org/html/2601.04233v1) | — |
| [arxiv.org/html/2602.05207v1](https://arxiv.org/html/2602.05207v1) | — |
| [arxiv.org/html/2604.01760v1](https://arxiv.org/html/2604.01760v1) | — |
| [ICLR 2026 conference paper](https://proceedings.iclr.cc/paper_files/paper/2026/file/ddeadff481e7ddf478234961ea7aae8b-Paper-Conference.pdf) | — |
| [EMNLP 2025 main.1266](https://aclanthology.org/2025.emnlp-main.1266.pdf) | — |
| [PMC12517399](https://pmc.ncbi.nlm.nih.gov/articles/PMC12517399/) | — |
| [IEEE TPAMI — Discrete Speech Tokens survey (2026)](https://www.computer.org/csdl/journal/tp/2026/04/11298521/2cojfroKS0U) | Semantic vs. acoustic tokenizers |

Named in prose with IDs:

- **Moshi** — `arXiv:2410.00037` — full-duplex speech model, Mimi codec
- **Beyond Word Error Rate** — `arXiv:2609.11786` — evaluation
- **SteerDuplex** — `arXiv:2609.12623` — full-duplex steering
- **SoundStream** — `arXiv:2107.03312` — RVQ for neural audio codecs
- **EnCodec** — `arXiv:2210.13438` — high-fidelity neural audio compression
- **AudioLM** — `arXiv:2209.03143` — two-stage semantic + acoustic generation
- Also cited without titles: `arXiv:2606.19453`, `arXiv:2608.09930`, `arXiv:2609.11786`, `arXiv:2609.12623`

## Papers to add for the three weak docs

> ⚠️ These are from my own knowledge, not extracted from your docs. The IDs for SoundStream / EnCodec / AudioLM / Moshi are corroborated by your docs; **Whisper's is not — verify it resolves before relying on it.** Everything here should be opened once before being trusted.

**For "How audio becomes something a model can consume":**
- SoundStream `arXiv:2107.03312` — where RVQ came from
- EnCodec `arXiv:2210.13438` — the codec most systems actually use
- AudioLM `arXiv:2209.03143` — the semantic/acoustic token split
- IEEE TPAMI discrete speech tokens survey (linked above) — the best single overview

**For "Cascaded vs. end-to-end speech-to-speech":**
- Moshi `arXiv:2410.00037` — the clearest end-to-end architecture, and its paper is explicit about the latency argument
- The GPT-4o and Gemini Live system cards — vendor, but primary for what those systems actually do
- Search NotebookLM for the trade-off directly: the honest answer is that **cascaded gives you a text checkpoint to inspect and gate**, which is the reason your PRD picks it

**For "Streaming and latency engineering":**
- Whisper `arXiv:2212.04356` — **verify this ID** — explains why it is architecturally non-streaming
- RNN-Transducer literature for the streaming-ASR contrast
- Vendor engineering docs below are legitimate here, because latency numbers are properties of their systems

## Vendor docs — legitimate, with a caveat

Fine as primary sources **for their own products' behaviour**; not for claims about the field.

- [Deepgram docs](https://developers.deepgram.com) — 19 citations, streaming ASR and endpointing
- [LiveKit Agents](https://docs.livekit.io/agents/) — turn detection, pipeline architecture
- [ElevenLabs docs](https://elevenlabs.io/docs) — TTS latency, language tagging
- Also cited: inworld.ai, smallest.ai, bland.ai — vendor blogs, treat as marketing unless they publish method

## Sources to treat with suspicion

Heavily cited in the docs, no editorial standard, several appear to be AI-generated content aggregators: **gradium.ai, arunbaby.com, heardright.app, praveentn.live, made-in-jurgistan.github.io, studocu.vn, aiwiki.ai, theorempath.com, localaimaster.com, themoonlight.io, qubittool.com**.

Not necessarily wrong — but nothing in them is checkable, and several of the confident numbers in your docs trace back only to these. **Do not quote a figure in the presentation whose only source is one of these.**

## Suggested NotebookLM setup

1. Add the eight PDFs.
2. Add the arXiv links above as separate sources.
3. Add the three project research docs (`voice-stack`, `arabic-voice`, `travel-api`) — those were researched with sources and dates, and they carry their own "what I could not verify" sections.
4. First question to ask it: *"Where do these sources disagree with each other, and which claims appear in only one source?"* That surfaces the soft spots before an interviewer does.
