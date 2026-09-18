# Python Realtime Voice Stack

**Deployment targets and free-tier reality for a FastAPI WebSocket voice agent.**

**Date of research: 18 September 2026.** Everything below was verified against live
sources on that date. All prices, model IDs and rate limits are volatile —
re-check the two dashboards named in §0.3 before you commit code.

---

## 0. One-page summary

### 0.1 Recommended stack

| Layer | Choice | Why |
|---|---|---|
| **Deploy target** | **Modal**, `@modal.asgi_app()` + FastAPI `WebSocket` | Only option here with first-class documented WebSocket support, ~1s container boot, a `me`/`eu` region, and $30/mo of free compute that actually covers an always-warm container. |
| **STT** | **Groq `whisper-large-v3-turbo`** (batch) | 216x real-time, ~200–400 ms round trip, genuinely free at 20 RPM / 2 000 RPD / 7 200 audio-sec-per-hour. |
| **LLM** | **Gemini `gemini-3.5-flash-lite`** primary, **Groq `openai/gpt-oss-20b`** as hot fallback | Groq's free LLM tier is capped at **8 000 TPM**, which throttles a real conversation (see §4.3). Gemini's free tier is more generous but unpublished. Run both; fail over on 429. |
| **TTS** | **Gemini `gemini-3.1-flash-tts-preview`** with `stream: true` | **Groq's TTS free tier is unusable** — 10 RPM / 100 requests *per day* / 200 chars per request (§4.2). This is the single biggest finding in this document. |
| **Endpointing** | **`@ricky0123/vad-web@0.0.31`** (Silero v5/v6 via onnxruntime-web) in the browser | Batch STT needs client-side turn detection. Ships today, 2.3 MB model + ~14 MB wasm, works in-browser. |
| **Framework** | **Raw FastAPI `WebSocket` + `asyncio`.** No Pipecat, no LiveKit. | Pipecat 1.11.0 pulls 110 dependencies; LiveKit Agents 1.8.2 pulls 106 and wants a LiveKit server. For a 3-day build you need code you can explain line-by-line in a review. |

### 0.2 The three risks that will actually bite you

1. **Groq TTS free tier cannot run even one conversation.** `canopylabs/orpheus-v1-english` is capped at **10 RPM, 100 RPD, 1 200 TPM** with a **200-character maximum per request** and WAV-only output. One assistant turn of 400 characters = 2 requests. A 5-minute conversation is 30–50 requests. You get **two or three conversations per day**, and the 10 RPM cap means you will hit 429 *mid-sentence*. → **Use Gemini TTS. Budget a day to discover this yourself if you ignore it.**
2. **Modal's WebSocket lifetime is bounded by the Function `timeout`, which defaults to 300 s (5 min).** A 10-minute conversation dies silently at 5 minutes unless you pass `timeout=` explicitly. Modal documents "a single function call per connection" but publishes **no maximum WebSocket duration** — set `timeout=3600` and *test a real 10-minute call on day one*.
3. **Groq's free LLM tier is 8 000 TPM.** With a 1 500-token system prompt plus growing history, each turn costs ~2 000 input tokens → **~4 turns per minute before throttling**. A brisk voice conversation is 6–8. Mitigate with aggressive history trimming, a short system prompt, and Gemini as the primary.

### 0.3 What to verify yourself before writing code

Google **no longer publishes free-tier per-model rate limits**. Groq does, but per-org
limits can differ. Open both, screenshot them, and pin the numbers into your repo:

- **`https://aistudio.google.com/rate-limit`** — your live Gemini RPM/TPM/RPD
- **`https://console.groq.com/settings/limits`** — your live Groq limits

### 0.4 Ranked deployment recommendation

| Rank | Platform | Verdict |
|---|---|---|
| **1** | **Modal** | Documented WebSocket support (RFC 6455), ~1 s container boot, `min_containers=1` to eliminate cold start, `me`/`eu`/`us` regions, $30/mo free compute ≈ 1 500 container-hours at 0.25 core / 1 GiB. Modal ships its own WebSocket voice examples. **Use this.** |
| **2** | **Fly.io** | Real VMs, WebSockets are a non-issue, `fra`/`ams`/`lhr` near Europe. But **the free tier is gone for new accounts** (Oct 2024); ~$2–6/mo for a shared-cpu-1x, and auto-stop means a cold start on the reviewer's first click. Good fallback if Modal's serverless model fights you. |
| **3** | **Hugging Face Spaces** | Free 2 vCPU / 16 GB, but there is an **unresolved, reproduced report of the HF proxy returning HTTP 404 to WebSocket upgrades on Docker Spaces**, with no official statement either way. Do not stake a reviewer-facing demo on it. |
| **4** | **Render** | Free tier is **0.1 CPU / 512 MB**, spins down after 15 min idle, and takes **~1 minute to spin back up**. A reviewer clicking your link waits a minute for a 0.1-CPU box. Disqualifying for this use case. |

---

## 1. Modal — WebSockets, timeouts, warmth, cost

### 1.1 WebSocket support: yes, first-class, documented

From the [Web Functions guide](https://modal.com/docs/guide/webhooks) (accessed 2026-09-18), verbatim:

> Functions annotated with `@modal.web_server`, `@modal.asgi_app`, or `@modal.wsgi_app` also support the WebSocket protocol. […] **WebSockets on Modal maintain a single function call per connection**, which can be useful for keeping state around. Most of the time, you will want to set your handler function to allow concurrent inputs […]
>
> We support the full WebSocket protocol as per RFC 6455, but we do not yet have support for RFC 8441 (WebSockets over HTTP/2) or RFC 7692 (`permessage-deflate` extension). **WebSocket messages can be up to 2 MiB each.**

WebSocket support shipped publicly on [2024-02-27](https://modal.com/blog/websocket-launch).
The infrastructure post [*Lambda on hard mode*](https://modal.com/blog/serverless-http)
(2024-03-14) explains the mechanism: the HTTP/1.1 upgrade handshake is terminated at
`modal-http`, then "we transmit messages between `modal-http` and the serverless
function via data channels in the same way as we did for HTTP."

### 1.2 Timeout semantics — the part people get wrong

There are **two** timeouts and they are frequently conflated.

**(a) The 150-second HTTP request timeout — does NOT apply to WebSockets.**
The [Request timeouts](https://modal.com/docs/guide/webhook-timeouts) page says:

> All Web Function types (`modal.fastapi_endpoint`, `modal.asgi_app`, `modal.wsgi_app`, and `modal.web_server`) have a maximum HTTP request timeout of 150 seconds enforced. However, the underlying Modal Function can have a longer timeout. In case the Function takes more than 150 seconds to complete, an **HTTP status 303 redirect** response is returned pointing at the original URL with a special query parameter linking it that request.

> ⚠️ I fetched this page's full rendered text and **the word "WebSocket" does not appear on it at all**. The escape hatch it describes — a 303 redirect the browser follows — is structurally impossible for a WebSocket. Combined with Modal shipping its own long-lived WebSocket examples (QuiLLMan, streaming Parakeet, streaming Kyutai STT), the strong inference is that the 150 s ceiling is HTTP-request-only. **I could not find an explicit sentence in Modal's docs stating that WebSockets are exempt.** Treat this as high-confidence inference, not documented fact, and validate with a 10-minute connection on day one.

**(b) The Function `timeout` — this DOES bound your WebSocket.**
From [Timeouts](https://modal.com/docs/guide/timeouts):

> The default execution timeout is **300 seconds** (5 minutes). […] users may specify timeout durations between 1 second and **24 hours**.

Because a WebSocket is "a single function call per connection," a 2–10 minute
conversation on the default timeout **will be cut off at 5 minutes**. Set it explicitly.

There is **no documented maximum WebSocket connection duration** on Modal. Also
undocumented: whether the call's timeout clock starts at the upgrade or at container
entry. Assume the former.

### 1.3 Current parameter names (the old ones now hard-error)

Modal 1.0 renamed the autoscaling parameters, and **backwards compatibility was
removed in client 1.4.0** — the old spellings raise `DeprecationError`, they do not warn.

| Old (dead) | Current |
|---|---|
| `keep_warm` | **`min_containers`** |
| `container_idle_timeout` | **`scaledown_window`** |
| `concurrency_limit` | **`max_containers`** |
| `allow_concurrent_inputs` | **`@modal.concurrent(max_inputs=…)`** |

Plus `buffer_containers` (extra idle containers provisioned while the Function is active).

From [Cold start performance](https://modal.com/docs/guide/cold-start):
`scaledown_window` **defaults to 60 seconds** and is configurable from **2 seconds to
20 minutes**. `min_containers` sets a floor so the Function never scales to zero —
and the docs are explicit that "you will be billed for any resources used while the
container is idle."

From [Input concurrency](https://modal.com/docs/guide/concurrent-inputs), verbatim:

```python
@app.cls()
@modal.concurrent(max_inputs=100)
class MyCls:
    @modal.method()
    def my_method(self, input: str):
        ...
```

> The decorator must be applied **at the class level, not on individual methods**.

### 1.4 The shape of the thing

```python
import modal
from fastapi import FastAPI, WebSocket

app = modal.App("sarjy")
image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "fastapi[standard]", "groq", "google-genai", "numpy"
)

@app.cls(
    image=image,
    cpu=0.25,               # billed on max(request, actual usage)
    memory=1024,            # MiB
    timeout=3600,           # ← THE ONE THAT MATTERS: bounds each WebSocket
    scaledown_window=300,   # keep container alive 5 min after last connection
    min_containers=1,       # no cold start for the reviewer; ~$14/mo — see §1.6
    region="us-east",       # or "eu" (1.15x) / "me" (1.75x) — see §1.5
    secrets=[modal.Secret.from_name("sarjy-keys")],
)
@modal.concurrent(max_inputs=20)   # class level, many WS per container
class Sarjy:
    @modal.enter()
    def boot(self):
        ...  # clients, warm HTTP pools, prompt cache — moves latency to warm-up

    @modal.asgi_app()
    def web(self):
        api = FastAPI()

        @api.websocket("/ws")
        async def ws(sock: WebSocket):
            await sock.accept()
            ...  # your loop
        return api
```

### 1.5 Regions

From [Region selection](https://modal.com/docs/guide/region-selection), verbatim region list:

> Broad regions: `us`, `eu`, `ap`. Narrow regions include `us-east`, `us-central`, `us-south`, `us-west`, `eu-west`, `eu-north`, `eu-south`, `ap-northeast`, `ap-southeast`, `ap-south`, `ap-melbourne`, `jp`, `au`, `uk`, `ca`, **`me`**, `sa`, `af`, `mx`

Price multipliers: **1.15x** for a broad region (`eu`, `ap`), **1.75x** for a narrow one
(`eu-west`, `me`, …). If multiple regions spanning both categories are given, the lower
multiplier applies — so `region=["eu", "me"]` bills at 1.15x.

There **is** a Middle East region (`me`), which matters if the reviewer is in the Gulf.
At 1.75x it eats your $30 fast; `region=["eu","me"]` at 1.15x is the pragmatic compromise.

### 1.6 What $30/month actually buys

From [modal.com/pricing](https://modal.com/pricing) (accessed 2026-09-18):

- CPU: **$0.0000131 / core / sec** = **$0.04716 / core / hour**
- Memory: **$0.00000222 / GiB / sec** = **$0.007992 / GiB / hour**
- Default container request: **0.125 core, 128 MiB**
- Billing: *"For CPU and memory, you'll be charged based on whichever is higher: your request or actual usage."*
- **Starter plan: $30 / month free compute.** (Team: $100/mo free, $250/mo base.)
- Egress: **$0.04 / GiB** beyond **1 TiB included** on Starter. Irrelevant here — a 10-minute Opus call is a few MB.

CPU-only, always-on, US region:

| Container config | $/hour | Hours for $30 | Cost for 730 h (24/7) |
|---|---|---|---|
| 0.125 core / 128 MiB (default) | $0.00689 | **4 350 h** | $5.03 |
| 0.25 core / 512 MiB | $0.01579 | **1 900 h** | $11.52 |
| **0.25 core / 1 GiB** | **$0.01978** | **1 517 h** | **$14.44** |
| 0.5 core / 1 GiB | $0.03157 | 950 h | $23.05 |
| 1 core / 2 GiB | $0.06314 | 475 h | $46.10 ❌ |
| 2 core / 4 GiB | $0.12629 | 238 h | $92.19 ❌ |

**Read this as:** one always-warm 0.25-core / 1 GiB container costs **~$14.44/mo** —
half your credit, 24/7, forever. In `eu` (1.15x) it's $16.61. In `me` (1.75x) it's
$25.27, which leaves no headroom.

> ⚠️ The floor is not the bill. Because billing is `max(request, usage)`, any second
> where your Python actually consumes a full core (audio resampling, WAV muxing, numpy)
> is billed at a full core for that second. Keep audio work off the server — send Opus
> from the browser and hand bytes straight to Groq — or budget ~1.5–2x the table above.

**The cheap play:** don't run warm 24/7. `min_containers=0` normally, and flip
`min_containers=1` only for the demo window — a warm container is ~$0.02/hour, so a
three-hour review session costs six cents. Modal supports `f.update_autoscaler(min_containers=1)`
and scheduled adjustment via `modal.Cron()`.

### 1.7 Cold starts

Modal's own claim: *"Containers boot in about one second."* That is infrastructure only —
your image pull and Python imports sit on top. Community-measured CPU-only cold starts
land in the **2–5 second** range for simple functions. For a reviewer clicking a link,
2–5 seconds of dead air before the socket opens is a failed first impression.
`min_containers=1` during the demo window removes it entirely.

Advice from the cold-start guide that applies directly: move initialization into
`@modal.enter()` (moves the cost to warm-up), and consider Memory Snapshots.

### 1.8 Official Modal examples for realtime audio — yes, several

| Example | What it shows |
|---|---|
| [**QuiLLMan**](https://github.com/modal-labs/quillman) ([docs](https://modal.com/docs/examples/llm-voice-chat)) | Full voice chat over bidirectional WebSocket with Opus, `@modal.asgi_app()` with `@web_app.websocket("/ws")` on a `@app.cls(gpu="A10G", scaledown_window=300)`. The canonical reference. |
| [**Streaming Parakeet**](https://modal.com/docs/examples/streaming_parakeet) | FastAPI `/ws` endpoint, `@modal.concurrent(max_inputs=100)`, `await ws.receive_bytes()` / `await ws.send_text()`, `END_OF_STREAM` sentinel, **server-side silence detection via pydub** (1 000 ms silence at −45 dB) rather than VAD. |
| [Streaming Kyutai STT](https://modal.com/docs/examples/streaming_kyutai_stt) | Streaming ASR over WebSocket. |
| [**One-second voice-to-voice latency with Modal, Pipecat, and open models**](https://modal.com/blog/low-latency-voice-bot) (2025-11-04) | Parakeet STT → Qwen3-4B (vLLM) → KokoroTTS. Achieved *"a median voice-to-voice latency of one second"* when client and container were geographically close. Used **Modal Tunnels** serving FastAPI/uvicorn WebSocket endpoints rather than the standard web-endpoint path. |

**Gotchas surfaced by those examples:**
- The 1-second latency result depended on **region pinning**, and Modal warns pinning "can limit the available GPU pool and increase wait times."
- The Pipecat post bypassed Modal's input plane via Tunnels, which "comes at the cost of autoscaling."
- Neither the Parakeet nor the QuiLLMan example sets an explicit `timeout=` — do not copy that omission.
- Only one open issue matching "websocket timeout" exists in `modal-labs/modal-client` ([#3610](https://github.com/modal-labs/modal-client/issues/3610), an `UnboundLocalError` in the WebSocket tunnel proxy path, closed 2025-09-29). There is no pile of WebSocket reliability complaints.

Workspace rate limit worth knowing: **200 Function calls or HTTP requests per second**
for a new account, burst multiplier 5 s, 429 beyond that. Not a constraint here.

---

## 2. Hugging Face Spaces — viable for a demo? Probably not

### 2.1 Free tier mechanics

- **Free CPU Basic: 2 vCPU, 16 GB RAM, 50 GB non-persistent disk, $0/hour.** More RAM than Modal gives you.
- **Sleeps after 48 hours of inactivity** on `cpu-basic`; any visitor restarts it automatically. (Far more forgiving than Render's 15 minutes.)
- Docker Spaces: set `sdk: docker` and `app_port: 7860` in `README.md` frontmatter; container runs as UID 1000; disk is wiped on restart.

### 2.2 The WebSocket problem

There is **no statement about WebSockets, connection duration, or proxy timeouts
anywhere in the [Docker Spaces documentation](https://huggingface.co/docs/hub/en/spaces-sdks-docker)** — I fetched the full page.

What exists instead is a pattern of unresolved failure reports:

- [**FastAPI WebSocket returns HTTP 404 on Spaces**](https://discuss.huggingface.co/t/fastapi-websocket-returns-http-404-on-spaces/159865) (opened 2025-06-19). WebSocket upgrades return `server rejected WebSocket connection: HTTP 404` while plain `GET` to the same Space returns 200. Critically: **the connection attempt never appears in the container logs**, meaning the HF proxy rejects it before it reaches uvicorn. Failed at `/`, `/ws`, and `/queue/join`. Suggested fixes (add `websockets` to requirements, use `wss://`) did not work. **Thread is unresolved and has no HF staff reply.**
- A cluster of adjacent threads report Docker Space proxy/routing 404s more generally ([app_port ignored](https://discuss.huggingface.co/t/persistent-404-on-docker-space-app-port-routing-seems-to-be-ignored-user-josejar/159665), [POST never reaches FastAPI](https://discuss.huggingface.co/t/docker-space-post-endpoint-404-html-error-routing-never-reaches-fastapi-container/163440), [proxy not forwarding requests](https://discuss.huggingface.co/t/docker-spaces-returning-data-proxy-not-forwarding-requests-to-container-all-spaces-affected/175500)).
- An older [*Websocket no longer allowed?*](https://discuss.huggingface.co/t/websocket-no-longer-allowed/42707) thread (June 2023) was a `wsproto` vs `websockets` library incompatibility, resolved by the reporter — not a platform block.

### 2.3 Counter-evidence

Gradio Spaces historically used WebSockets for their queue and worked, and HF's own
[**FastRTC**](https://huggingface.co/blog/fastrtc) (announced 2025-02-25) advertises
*"WebRTC and Websocket support"*. But FastRTC's Spaces story is **WebRTC via Cloudflare
TURN** (the [HF×Cloudflare partnership](https://huggingface.co/blog/fastrtc-cloudflare),
2025-04-09), explicitly because *"when deploying in cloud environments with firewalls
like Hugging Face Spaces, WebRTC connections may be blocked from making direct
connections, requiring a TURN server."* That is a statement that HF Spaces' network
path is awkward, not a reassurance about raw WebSockets. FastRTC on PyPI is at
**0.0.34, last published 2025-11-24** — nearly ten months stale.

> 🚨 **Verdict:** I could not verify that a raw FastAPI WebSocket works through the HF
> Spaces proxy today, and the only specific evidence I found says it returns 404 at the
> proxy. It may well work — the failure reports could be misconfiguration — but
> "may well work" is not a basis for a URL a hiring reviewer opens once. If you want to
> use HF, **spend 30 minutes deploying a hello-world WebSocket Docker Space and prove it
> before building on it.**

---

## 3. Fly.io and Render compared

### 3.1 Fly.io

| | |
|---|---|
| **Free tier** | **Gone for new accounts since October 2024.** Legacy accounts keep 3× shared-cpu-1x 256 MB + 3 GB volume + 160 GB egress. New signups get a trial of *2 hours of compute or 7 days, whichever comes first*. |
| **Cost** | `shared-cpu-1x` 256 MB = **$1.94/mo** on the [official pricing page](https://fly.io/pricing/). Secondary sources put 512 MB at ~$3.32 and 1 GB at ~$5.92. Bandwidth $0.02/GB NA+EU, $0.12/GB Africa & India. |
| **WebSockets** | Real Firecracker VMs behind a proxy that has handled WebSockets since day one. Non-issue. |
| **Cold start** | Machines auto-stop when idle (typically 5 min) and cold-start on next request. A stopped machine still bills rootfs storage. |
| **Regions** | `ams arn bom cdg dfw ewr fra gru iad jnb lax lhr nrt ord sin sjc` — good European coverage (`fra`, `ams`, `cdg`, `lhr`, `arn`). **No Middle East region** in the region list I could retrieve. |

**Fly is the right answer if Modal's serverless model fights you** — it's a normal Linux
box, you control the process, and WebSockets are boring. The cost is ~$2–6/mo out of
pocket and losing your $30 Modal credit.

### 3.2 Render

From [Deploy for Free](https://render.com/docs/free), verbatim:

> Render **spins down** a Free web service that goes 15 minutes without receiving any inbound traffic […] both HTTP requests and WebSocket messages from existing connections.
> […] A Free web service spins back up whenever it next receives an HTTP request or new WebSocket connection. **This process takes about one minute.**
> Render grants **750 Free instance hours** to each workspace per calendar month.

Free instances are **512 MB RAM / 0.1 CPU** (this figure is from Render's community
forum and secondary sources — it is **not stated on the `/docs/free` page** I fetched).
Free services also get: no persistent disk, no scaling beyond one instance, no SSH,
no edge caching.

> 🚨 **Disqualifying combination:** 0.1 CPU is a tenth of a core — you cannot run
> audio handling plus three concurrent HTTP client sessions on it — and a reviewer
> opening a cold link waits **a full minute**. Render's own spin-down rule *does* treat
> WebSocket messages as activity, which is thoughtful, but it doesn't save you.

### 3.3 Ranking, restated

**Modal > Fly.io > Hugging Face Spaces > Render**, for *this* use case (Python,
persistent WS, free/cheap, reviewer-facing cold-start sensitivity, Gulf/Europe latency).
Modal wins on the combination of free credit that covers a warm container, documented
WebSocket support with working first-party voice examples, sub-second boot, and a `me` region.

---

## 4. Groq free tier — today's actual numbers

All figures below are the **Free plan** table from
[console.groq.com/docs/rate-limits](https://console.groq.com/docs/rate-limits),
fetched 2026-09-18. ASH = audio-seconds per hour, ASD = audio-seconds per day.

| Model ID | RPM | RPD | TPM | TPD | ASH | ASD |
|---|---|---|---|---|---|---|
| `whisper-large-v3-turbo` | 20 | 2 K | — | — | **7.2 K** | **28.8 K** |
| `whisper-large-v3` | 20 | 2 K | — | — | 7.2 K | 28.8 K |
| `openai/gpt-oss-120b` | 30 | 1 K | **8 K** | 200 K | — | — |
| `openai/gpt-oss-20b` | 30 | 1 K | **8 K** | 200 K | — | — |
| `openai/gpt-oss-safeguard-20b` | 30 | 1 K | 8 K | 200 K | — | — |
| `qwen/qwen3.8-27b` | 30 | 1 K | 8 K | 200 K | — | — |
| `groq/compound` | 30 | 250 | 70 K | — | — | — |
| `groq/compound-mini` | 30 | 250 | 70 K | — | — | — |
| `meta-llama/llama-prompt-guard-2-22m` | 30 | 14.4 K | 15 K | 500 K | — | — |
| `meta-llama/llama-prompt-guard-2-86m` | 30 | 14.4 K | 15 K | 500 K | — | — |
| **`canopylabs/orpheus-v1-english`** | **10** | **100** | **1.2 K** | **3.6 K** | — | — |
| **`canopylabs/orpheus-arabic-saudi`** | **10** | **100** | **1.2 K** | **3.6 K** | — | — |

Groq's docs add: *"You can view the current, exact rate limits for your organization on
the limits page"* — so treat the table as the published default, not a guarantee.

### 4.1 STT — `whisper-large-v3-turbo` ✅ usable

From [console.groq.com/docs/speech-to-text](https://console.groq.com/docs/speech-to-text):

| Model | Cost/hour audio | Speed factor | WER |
|---|---|---|---|
| `whisper-large-v3-turbo` | $0.04 | **216x real-time** | 12% |
| `whisper-large-v3` | $0.111 | 189x real-time | 10.3% |

- Max file: **25 MB free tier**, 100 MB dev tier. Formats: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm.
- **Minimum billed duration: 10 seconds.** Min audio length 0.01 s.
- Optional `prompt` (≤224 tokens) for spelling/context steering; `language` as ISO-639-1 improves accuracy.
- `verbose_json` gives segment- and word-level timestamps — useful if your deep-dive is word-highlighted captions.
- **No streaming transcription endpoint.** Batch only.

**Latency for a 3–8 s utterance:** the compute is negligible (5 s ÷ 216 ≈ 23 ms). The
cost is network. [llmlatency.dev/provider/groq](https://llmlatency.dev/provider/groq)
measured (as of 2026-09-10) **131 ms p50 edge TTFB from US Central** — Groq's fastest
region — and **292 ms p50 from Europe (Germany)**. Add upload of the audio body.
**Realistic round trip: 200–450 ms** from a US-region container, 350–600 ms from Europe.

Groq operates 13 data centres including **Dammam, Saudi Arabia** (announced at LEAP 2025
with Aramco Digital) and **Helsinki** (July 2025). I could **not verify** whether the
public `api.groq.com` endpoint geo-routes free-tier traffic to them.

**Headroom check:** 7 200 ASH = 2 hours of audio per clock hour; 20 RPM = one utterance
every 3 seconds. A single-user demo is comfortable. **Two reviewers talking
simultaneously can breach 20 RPM.** If the demo is multiplayer, this is your first 429.

*(Unverified: whether the ASH counter uses actual audio duration or the 10-second
minimum-billed duration. If the latter, 7 200 ASH = 720 requests/hour, still above the
20 RPM ceiling, so RPM binds first either way.)*

### 4.2 TTS — Orpheus 🚨 NOT usable on the free tier

`playai-tts` and `playai-tts-arabic` were **deprecated 2025-12-31** and replaced by
Canopy Labs' Orpheus. From
[console.groq.com/docs/text-to-speech/orpheus](https://console.groq.com/docs/text-to-speech/orpheus):

| | |
|---|---|
| Model IDs | `canopylabs/orpheus-v1-english`, `canopylabs/orpheus-arabic-saudi` |
| Voices | EN: Autumn, Diana, Hannah, Austin, Daniel, Troy · AR-SA: Abdullah, Fahad, Sultan, Lulwa, Noura, Aisha |
| Endpoint | `https://api.groq.com/openai/v1/audio/speech` |
| Price (paid) | **$22 / 1 M chars** (EN), **$40 / 1 M chars** (AR) |
| **Max input** | **200 characters per request** |
| Output | **WAV only** |
| Vocal direction | EN only, bracketed: `[cheerful]`, `[whisper]` |
| Batch | *"Not supported at this time for Orpheus models"* |
| Status | Listed under **Preview Models**, not Production |
| Streaming | **Not documented** |

**Why this kills it.** Do the arithmetic against 10 RPM / 100 RPD:

- One assistant turn of ~400 characters = **2 requests** (200-char cap).
- A 5-minute conversation ≈ 15–25 assistant turns = **30–50 requests**.
- **100 RPD ⇒ two to three conversations per day, total, for your whole org.**
- Worse, **10 RPM**: at a natural pace of one turn every ~10 s and 2 requests per turn,
  you need ~12 RPM. **You will 429 mid-conversation on the very first call.**
- Plus **1 200 TPM / 3 600 TPD** on top.

Third-party Orpheus deployments report ~130–280 ms TTFB (Baseten, Simplismart, Canopy's
own issue tracker) — but those are *other people's GPUs*. **Groq publishes no TTFB
number for Orpheus**, only *"low-latency inference"*. Even if it were fast, the free
quota makes it moot.

**Conclusion: do not build your voice output on Groq's free tier.** Either pay
(Orpheus at $22/1M chars is cheap in absolute terms — a 5-min conversation is ~6 000
chars ≈ $0.13) or use Gemini TTS, which is free.

### 4.3 LLMs — usable with discipline

**Currently on Groq's free tier:** `openai/gpt-oss-120b`, `openai/gpt-oss-20b`,
`openai/gpt-oss-safeguard-20b`, `qwen/qwen3.8-27b`, `groq/compound`, `groq/compound-mini`.

> ⚠️ **The Llama models are on their way out.** [Groq's deprecations page](https://console.groq.com/docs/deprecations) lists **2026-08-16**: `llama-3.1-8b-instant` → `openai/gpt-oss-20b`, and `llama-3.3-70b-versatile` → `openai/gpt-oss-120b` or `qwen/qwen3.6-27b`. They still appear under "Production Models" on the models page but **do not appear in the free-tier rate-limit table at all**. Do not write `llama-3.3-70b-versatile` into new code. Also gone: `qwen/qwen3-32b` and `meta-llama/llama-4-scout-17b-16e-instruct` (2026-07-17).

**Tool calling** ([console.groq.com/docs/tool-use](https://console.groq.com/docs/tool-use)):
*"All models on Groq support tool use."* But the capability matrix matters:

| Capability | Models |
|---|---|
| **Parallel tool calls** | `qwen/qwen3.6-27b`, `minimaxai/minimax-m2.7`, `llama-3.3-70b-versatile`, `llama-3.1-8b-instant` |
| **No parallel tool calls** | **`openai/gpt-oss-20b`, `openai/gpt-oss-120b`**, `qwen/qwen3.8-27b` |
| Built-in tools (web search, code exec) | Groq Compound systems, GPT-OSS variants |
| JSON mode | Most models |

So the models you can actually use for free (`gpt-oss-*`) **do not do parallel tool
calls**. For a single-API-call assistant that's fine; for anything fan-out, you serialise.

**The real constraint is 8 000 TPM.** Worked example:

- System prompt with guardrails + tool schemas: ~1 200–1 800 tokens
- Rolling history after 6 turns: ~600 tokens
- Tool result injected: ~200 tokens
- Output: ~120 tokens
- **≈ 2 200 tokens per turn** → **8 000 ÷ 2 200 ≈ 3.6 turns per minute**

A brisk voice conversation runs 6–8 turns/minute. **You will be throttled.**
Mitigations: cut the system prompt hard, summarise history beyond 4 turns, prefer
`gpt-oss-20b`, and keep Gemini as the primary with Groq as failover (not the reverse).

**1 000 RPD** is the other ceiling: with tool round-trips costing 2 calls per turn,
that's ~500 turns/day ≈ 25–30 full conversations. Adequate for a take-home, tight
for a week of iteration plus a live review.

---

## 5. Google Gemini free tier — today's reality

### 5.1 What Google will and will not tell you

> 🚨 **Google no longer publishes free-tier per-model rate limits.** The
> [rate limits page](https://ai.google.dev/gemini-api/docs/rate-limits) states verbatim:
> *"Rate limits depend on a variety of factors (such as your usage tier) and can be
> viewed in Google AI Studio. As your tier and account status change over time, your
> rate limits will automatically update."* It contains numeric tables for **Tier 1, 2
> and 3** (paid), and describes the Free tier only qualitatively
> (*"Active project or free trial, no billing tier cap"*). **There is no published
> Free-tier RPM/TPM/RPD table.** The page also warns that specified limits are not guaranteed.

Tier qualification, for reference: **Tier 1** = billing account linked ($250 cap);
**Tier 2** = $100+ paid and 3 days since first payment ($2 000 cap); **Tier 3** =
$1 000+ paid and 30 days ($20 000+).

**What secondary sources report** for the free tier, consistently but unofficially:
**~15 RPM and ~1 000–1 500 RPD** for Flash-class models, with Flash-Lite sometimes at
30 RPM; **Pro models were removed from the free tier in April 2026**. Treat these as
folklore. **Go read `aistudio.google.com/rate-limit` for your project.**

### 5.2 Which models are free

From [ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing),
"Free of charge" on the Standard tier for input and output:

| Model | Free? | Paid (per 1M tokens) |
|---|---|---|
| `gemini-3.8-flash` | ✅ | — |
| `gemini-3.5-flash-lite` | ✅ | $0.30 in / $2.50 out |
| `gemini-3.1-flash-lite` | ✅ | $0.25 in / $1.50 out |
| `gemini-2.5-flash` | ✅ | — |
| `gemini-2.5-flash-lite` | ✅ | — |
| **`gemini-3.1-flash-tts-preview`** | ✅ | $1.00 in / **$20.00 out (audio)** |
| `gemini-2.5-flash-preview-tts` | ✅ | $0.50 in / $10.00 out |
| **`gemini-3.8-live`** | ✅ | — |

**Recommended fast tool-calling model: `gemini-3.5-flash-lite`** (or `gemini-3.1-flash-lite`
if your project's limits favour it). `gemini-3.8-flash` is the most capable Flash but is
tuned for "long-horizon software engineering" — overkill and slower for turn-level
dialogue. Also now shipping: `gemini-3.5-transcribe` / `gemini-3.5-transcribe-live`
(STT with diarization) if you ever want to drop Groq.

### 5.3 Gemini TTS ✅ — this is your voice

From [ai.google.dev/gemini-api/docs/speech-generation](https://ai.google.dev/gemini-api/docs/speech-generation):

| | |
|---|---|
| Models | `gemini-3.1-flash-tts-preview`, `gemini-2.5-flash-preview-tts`, `gemini-2.5-pro-preview-tts` |
| **Streaming** | ✅ *"Streaming is supported for Text-to-Speech (TTS) models starting with version 3.1"* — set `stream: true` |
| Output | **PCM, 24 000 Hz, mono**, base64 |
| Voices | **30** (Kore, Puck, Zephyr, Enceladus, Sulafat, …) |
| Languages | 90+ BCP-47 codes, **including Arabic (`ar`)**, auto-detected from input |
| Context | 32 k tokens per session; quality drifts past "a few minutes" of generated output — segment long transcripts |
| Status | **Preview** |

**This beats Groq Orpheus on every axis that matters here:** it streams (Orpheus doesn't
document streaming), it has no 200-character cap, it outputs raw PCM you can push
straight down the WebSocket without WAV demuxing, it's free, and it does Arabic.

**Unverified: Gemini TTS time-to-first-byte.** Google publishes no latency figure. This
is the single number you should measure on day one, because it sits directly on your
time-to-first-audio critical path. Budget 300–600 ms and be pleasantly surprised or not.

### 5.4 Function calling and structured output — strong

Gemini's function calling and structured output are in good shape for a
grounding-critical application:

- **Schema-constrained decoding.** As of 2026 all three major labs enforce JSON Schema
  at the sampling level rather than by prompting. Google
  [announced JSON Schema support and implicit property ordering](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-structured-outputs/),
  and JSON Schema support has been added to **all actively supported Gemini models**,
  so Pydantic / Zod models work out of the box.
- **The strict-mode gotcha:** you must set **both** `response_schema` **and**
  `response_mime_type: "application/json"`. Setting the mime type alone is *"only a
  strong hint"* and does **not** guarantee valid JSON.
- **Caveats:** not all JSON Schema features are supported, and very large or deeply
  nested schemas may be rejected — and Gemini's exact limits are undisclosed. Keep tool
  schemas flat and small (which you want anyway for TPM reasons).

For a guardrails/grounding deep dive, the pattern that works: constrain the model to a
schema with an explicit `"source"` or `"grounded_in"` field per claim, and refuse to
speak any field the tool response didn't supply. Schema-level enforcement makes that
mechanical rather than prompt-hopeful.

### 5.5 The Live API — the road not taken (but look at it)

**`gemini-3.8-live` launched 2026-09-15**, three days before this document. It is a
**stateful WebSocket speech-to-speech API** that would collapse your entire STT → LLM →
TTS pipeline into one connection.

| | |
|---|---|
| Protocol | *"Stateful WebSocket connection (WSS)"* |
| Audio in | raw 16-bit PCM, **16 kHz**, little-endian |
| Audio out | raw 16-bit PCM, **24 kHz**, little-endian |
| Models | `gemini-3.8-live`, `gemini-3.8-live-extended-thinking`; older `gemini-2.5-flash-native-audio-preview-12-2025` |
| Context | 131 072 in / 65 536 out |
| Tools | Function calling **with `behavior: NON_BLOCKING` async execution as the default** — tools run in the background without halting speech |
| **Session limits** | *"Without compression, **audio-only sessions are limited to 15 minutes**, and audio-video sessions are limited to 2 minutes."* |
| **Connection resets** | The underlying WebSocket **resets roughly every 10 minutes**; `SessionResumptionUpdate` tokens let you reconnect into the same session (valid up to 2 hours). Server sends `GoAway` with a `timeLeft` field before terminating. |
| Free tier | Listed as "Free of charge" on the pricing page; per-tier concurrent-session limits **not published for the Developer API free tier**. |

**Why I am not recommending it as the primary:** your 2–10 minute target sits right on
top of the ~10-minute WebSocket reset, so you'd be implementing session resumption
during a 3-day build; it's a black box you cannot decompose in a latency deep-dive; and
"I called Google's realtime API" is exactly the one-shot baseline a reviewer is
comparing against.

**Why you should still spike it for an hour:** if your time-to-first-audio with the
pipeline stack lands above ~1.5 s and won't come down, Live is the escape hatch, and
having measured both is itself a strong answer to "what did you try?"

---

## 6. The batch-STT latency problem

### 6.1 How much does batch Whisper actually cost you?

Two numbers, and they disagree — so here is both, with the arithmetic.

**The industry figure:** voice-agent vendor writeups put batch transcription at
**600–1 200 ms** of added latency before the LLM call even starts, and argue it makes
sub-300 ms voice-to-voice unreachable. Streaming STT with interim results is quoted at
~80 ms first-word latency over WebSocket.

**My arithmetic for Groq specifically**, which is a better model of your case:

| Stage | Streaming STT | Groq batch Whisper |
|---|---|---|
| Transcription of speech *while user talks* | overlapped, free | **not possible** — nothing is sent yet |
| Detect end of turn | 250–700 ms silence (same either way) | 250–700 ms silence (same) |
| Upload utterance | already uploaded | 5 s Opus ≈ 10 KB, 5 s PCM16 mono ≈ 160 KB → **30–150 ms** |
| Inference | ~50–100 ms to finalise | 5 s ÷ 216x = **~23 ms** |
| Network RTT + queue | — | **130–290 ms p50** (US Central / Europe) |
| **Delta** | baseline | **+200 to +450 ms** |

**So: batch Groq Whisper costs you roughly 200–450 ms versus a streaming STT, not
600–1 200 ms.** Groq's 216x speed factor is doing a lot of work here — the whole point
is that the inference is nearly free and you're paying network, once.

**Full realistic time-to-first-audio for the recommended stack:**

| Stage | ms |
|---|---|
| VAD redemption silence (client) | 250–500 |
| Utterance upload + Groq Whisper round trip | 200–450 |
| LLM time-to-first-token (Gemini Flash-Lite / Groq gpt-oss-20b) | 150–600 |
| TTS time-to-first-byte (Gemini streaming — **unmeasured**) | 300–600 |
| Browser decode + playback start | 30–80 |
| **Total** | **≈ 930 ms – 2.2 s** |

Modal's own Pipecat post achieved a **median 1 s voice-to-voice** with everything
co-located on their GPUs. **1.2–1.5 s is a good, honest target for this stack** —
and being able to show that table, measured, *is* the latency deep dive.

### 6.2 The biggest lever is your VAD, not your STT

> ⚠️ *"A misconfigured VAD is the single easiest way to add 500 ms of latency without
> touching any model. If you wait for, say, 700 ms of silence before declaring the turn
> over, you have added 700 ms to every turn."*

Practical guidance from the turn-detection literature: model-based turn detection
(reading intonation and rhythm rather than pure silence) cuts **300–500 ms** off the
average turn. Pure VAD always waits for a pause; semantic endpointing doesn't have to.
For a 3-day build, tune the silence window down to **250–350 ms** and accept occasional
early cut-offs — it is the cheapest 300 ms you will ever find.

### 6.3 Browser VAD options — what works today

**Recommendation: `@ricky0123/vad-web`.** Verified live against the npm registry and
jsDelivr on 2026-09-18:

| Package | Latest | Published | Notes |
|---|---|---|---|
| **`@ricky0123/vad-web`** | **0.0.31** | **2026-09-12** (6 days ago) | 6.76 MB unpacked. Peer dep `onnxruntime-web ^1.17.0`. |
| `@ricky0123/vad-react` | 0.0.37 | 2026-09-12 | 15 KB, pins `vad-web@0.0.31`. |
| `onnxruntime-web` | 1.30.0 | 2026-09-14 | 144 MB unpacked (you serve a fraction). |

**Actual bytes the browser downloads** (measured from jsDelivr):

| Asset | Size |
|---|---|
| `silero_vad_v6.onnx` | **2 327 524 B** (2.33 MB) |
| `silero_vad_v5.onnx` | 2 327 524 B (different checksum — genuinely a different model) |
| `silero_vad_legacy.onnx` | 1 807 522 B |
| `vad.worklet.bundle.min.js` | 2 480 B |
| `bundle.min.js` (vad-web) | 69 345 B |
| `ort-wasm-simd-threaded.wasm` | **14 239 897 B** (14.2 MB) |
| `ort-wasm-simd-threaded.jsep.wasm` (WebGPU) | 28 312 028 B (28.3 MB) |
| `ort.wasm.min.js` | 50 196 B |

**Realistic first-load cost: ~16.6 MB** (v6 model + non-JSEP wasm + JS), gzipped
substantially less over the wire. Serve the CPU wasm, not the JSEP/WebGPU build, unless
you need it. Cache aggressively; it's static.

**API and configuration:**

```js
const vad = await MicVAD.new({
  onSpeechEnd: (audio) => { /* Float32Array @ 16 000 Hz */ },
  baseAssetPath: "/vad/",        // where the .onnx + worklet live
  onnxWASMBasePath: "/ort/",     // where the ort wasm/.mjs live
});
vad.start();
```

Three model versions ship: `legacy`, `v5`, `v6`. **Silero VAD v6.0 released 2025-08-25**;
**v6.2 on 2025-12-10**. Output is a `Float32Array` at **16 000 Hz** — exactly what you
send to Groq Whisper, no resampling on either side. Default `getUserMedia` constraints
are `channelCount: 1, echoCancellation: true, autoGainControl: true, noiseSuppression: true`
(keep echo cancellation on — you're playing TTS into the same room). Docs cover Webpack 5
and Vite config; assets load from CDN by default. `NonRealTimeVAD` exists for offline use.

**Alternatives, briefly:**

| Option | Verdict |
|---|---|
| **Energy/RMS threshold in an `AudioWorklet`** | ~30 lines, zero bytes, zero dependencies. Works in a quiet room; falls apart with background noise or a fan. **Worth writing as a fallback path** so a 16 MB download failure doesn't kill the demo. |
| **WebRTC VAD (Google, via wasm)** | Tiny and battle-tested, but noticeably worse than Silero on noisy input and the JS wrappers are unmaintained. |
| **Server-side silence detection (pydub)** | What Modal's own Parakeet example does: 1 000 ms silence at −45 dB. Simple, but you pay to stream all audio up *and* you inherit a 1 s endpointing delay. Worse on both latency and bandwidth than client-side VAD. |
| **Picovoice Cobra** | Pure C, small, good — but commercial licensing. |
| Model-based semantic turn detection | The real win (300–500 ms), but out of scope for 3 days. Name it as "what I'd do with another week." |

---

## 7. Python realtime audio: what people actually use

### 7.1 Verified current versions (PyPI, 2026-09-18)

| Package | Version | Published | Python | Core deps |
|---|---|---|---|---|
| `fastapi` | **0.141.1** | 2026-07-29 | ≥3.10 | — |
| `uvicorn` | **0.53.0** | 2026-09-14 | ≥3.10 | — |
| `websockets` | **17.1** | 2026-08-26 | **≥3.11** | — |
| `groq` | 1.7.0 | 2026-08-26 | ≥3.10 | 6 |
| `google-genai` | 2.24.0 | 2026-09-16 | ≥3.10 | 18 (incl. `websockets`) |
| **`pipecat-ai`** | **1.11.0** | **2026-09-18** (today) | **≥3.11** | **110** |
| **`livekit-agents`** | **1.8.2** | 2026-09-15 | ≥3.10, <3.15 | **106** |
| `fastrtc` | 0.0.34 | **2025-11-24** (10 months stale) | ≥3.10 | 20 (incl. `gradio`, `aiortc`, `librosa`, `numba`) |

### 7.2 Recommendation: raw FastAPI WebSocket

**Use `FastAPI` + `WebSocket` + `asyncio` directly.** Reasons, in priority order for a
take-home:

1. **You have to explain it live.** 300 lines of your own asyncio is defensible in a
   code walkthrough. A Pipecat pipeline is 110 transitive dependencies of someone
   else's frame abstractions, and every question becomes "I'd have to check."
2. **Deployment footprint.** `fastapi[standard] + groq + google-genai + numpy` is a
   small image and a fast Modal cold start. `pipecat-ai` drags in `numba`,
   `onnxruntime`, `resampy`, `soundfile`, `soxr`, `nltk`, `Pillow`, `protobuf`,
   `openai` — that is a multi-hundred-MB image and seconds of import time on every
   cold start. On a 0.25-core container, `numba` alone is painful.
3. **Your stack is already three HTTP calls.** With client-side VAD you receive one
   complete utterance per turn. That's `receive_bytes()` → Groq → Gemini → stream PCM
   back with `send_bytes()`. A pipeline framework earns its keep when you're managing
   continuous frame flow, interruption, and ten transports. You are not.
4. **FastAPI's async model scales fine here.** One worker handles thousands of
   concurrent WebSockets provided you never block the event loop — so keep every
   provider call on `httpx`/`aiohttp` async clients and never call `time.sleep`,
   `pydub`, or synchronous `soundfile` in the handler.

Production patterns to actually implement (these are what a reviewer probes for):
a `ConnectionManager` with a connection cap, heartbeat ping/pong (Modal supports RFC
6455 ping/pong; use it to keep intermediaries from dropping the socket), graceful
disconnect handling, per-connection state, and reconnection with session ID on the client.

### 7.3 If you did want a framework

**Pipecat** ([`FastAPIWebsocketTransport`](https://docs.pipecat.ai/api-reference/server/services/transport/fastapi-websocket))
serves Pipecat sessions over a WebSocket inside your own FastAPI app, with configurable
serializers, session timeouts, WAV header generation, and built-in VAD/turn-taking/
interruption handling. It is the more lightweight path of the two — Pipecat's own docs
note *"by default, in order to minimize dependencies, only the basic framework
functionality is available"*, and extras are opt-in. Modal's own 1-second voice-bot demo
used Pipecat. If you want interruption handling for free and are willing to pay the
image size, this is the one.

**LiveKit Agents** is the heavier choice: it wants a LiveKit server (self-hosted or
LiveKit Cloud), and its room model — your agent joins as a participant — is genuine
value *if* multiplayer is your deep dive, since multi-participant is native rather than
bolted on. For single-user voice on Modal it is architecture you don't need.

**FastRTC** is HF's option and is genuinely one line to mount (`stream.mount(app)`) —
but it pulls `gradio`, `aiortc`, `librosa` and `numba`, and it's been stale on PyPI
since November 2025.

---

## 8. Explicit list of what I could NOT verify

| # | Claim | Status |
|---|---|---|
| 1 | WebSockets are exempt from Modal's 150 s HTTP request timeout | **Inferred, not documented.** The timeouts page never mentions WebSockets, and its 303-redirect workaround cannot apply to a WS. Modal ships long-lived WS examples. **Test a 10-min connection before relying on it.** |
| 2 | Maximum WebSocket connection duration on Modal | **Not documented anywhere.** Only the Function `timeout` (1 s – 24 h) is documented as bounding a call. |
| 3 | Whether the WS call's timeout clock starts at upgrade or container entry | **Not documented.** |
| 4 | Gemini free-tier per-model RPM / TPM / RPD | **Not published by Google.** The docs explicitly defer to `aistudio.google.com/rate-limit`. Third-party figures (~15 RPM / ~1 000–1 500 RPD) are unofficial. |
| 5 | Gemini Live API free-tier concurrent session limit | **Not published for the Developer API.** (Vertex/Firebase quotes 1 000 concurrent per project — a different product.) |
| 6 | Gemini TTS time-to-first-byte | **No published number.** Measure it — it's on your critical path. |
| 7 | Groq Orpheus TTFB on Groq hardware | **No published number.** The 130–280 ms figures circulating are from Baseten / Simplismart / Canopy on their own GPUs. |
| 8 | Whether Groq Orpheus supports streaming output | **Not documented** on Groq's TTS pages. WAV-only output implies no. |
| 9 | Whether Groq's ASH counter uses actual duration or the 10 s minimum-billed duration | **Not documented.** RPM binds first either way. |
| 10 | Whether `api.groq.com` geo-routes free-tier traffic to Dammam / Helsinki | **Could not verify.** The DCs exist; routing policy is unstated. |
| 11 | Whether raw FastAPI WebSockets work through the HF Spaces proxy today | **Could not verify either way.** No documentation; one unresolved 2025 report of HTTP 404 at the proxy with no staff reply. |
| 12 | Render free instance CPU/RAM (0.1 CPU / 512 MB) | **Not on Render's `/docs/free` page.** Figure comes from Render's community forum and secondary sources. |
| 13 | Fly.io Middle East region | **None found** in the region list I could retrieve. Absence of evidence. |
| 14 | Current status of `llama-3.3-70b-versatile` / `llama-3.1-8b-instant` on Groq | **Contradictory.** Listed under "Production Models" but flagged deprecated 2026-08-16 *and* absent from the free-tier rate-limit table. Assume unavailable on free tier. |
| 15 | Modal's exact billing behaviour for a container idling on an open WebSocket | **Inferred.** The container is running, so it bills. Not stated explicitly for the WS case. |

---

## 9. Sources

**Modal**
- [Web Functions](https://modal.com/docs/guide/webhooks) · [Request timeouts](https://modal.com/docs/guide/webhook-timeouts) · [Timeouts](https://modal.com/docs/guide/timeouts) · [Cold start performance](https://modal.com/docs/guide/cold-start) · [Scaling out](https://modal.com/docs/guide/scale) · [Input concurrency](https://modal.com/docs/guide/concurrent-inputs) · [Configuring CPU, memory, and disk](https://modal.com/docs/guide/resources) · [Region selection](https://modal.com/docs/guide/region-selection) · [Network egress billing](https://modal.com/docs/guide/network-egress-billing) · [Servers](https://modal.com/docs/guide/servers) — all accessed 2026-09-18
- [Pricing](https://modal.com/pricing) — accessed 2026-09-18
- [Introducing: WebSockets on Modal](https://modal.com/blog/websocket-launch) — 2024-02-27
- [Lambda on hard mode: Inside Modal's web infrastructure](https://modal.com/blog/serverless-http) — 2024-03-14
- [One-second voice-to-voice latency with Modal, Pipecat, and open models](https://modal.com/blog/low-latency-voice-bot) — 2025-11-04
- [QuiLLMan: Voice Chat with Moshi](https://modal.com/docs/examples/llm-voice-chat) · [repo](https://github.com/modal-labs/quillman) · [README_DOCS](https://github.com/modal-labs/quillman/blob/main/README_DOCS.md)
- [Streaming audio transcription using Parakeet](https://modal.com/docs/examples/streaming_parakeet) · [Stream transcriptions with Kyutai STT](https://modal.com/docs/examples/streaming_kyutai_stt)
- [modal-client issue #3610](https://github.com/modal-labs/modal-client/issues/3610) — closed 2025-09-29

**Hugging Face**
- [Docker Spaces](https://huggingface.co/docs/hub/en/spaces-sdks-docker) · [Spaces Overview](https://huggingface.co/docs/hub/en/spaces-overview) — accessed 2026-09-18
- [FastAPI WebSocket returns HTTP 404 on Spaces](https://discuss.huggingface.co/t/fastapi-websocket-returns-http-404-on-spaces/159865) — opened 2025-06-19, unresolved
- [Websocket no longer allowed?](https://discuss.huggingface.co/t/websocket-no-longer-allowed/42707) — June 2023
- [Persistent 404 on Docker Space](https://discuss.huggingface.co/t/persistent-404-on-docker-space-app-port-routing-seems-to-be-ignored-user-josejar/159665) · [POST endpoint 404](https://discuss.huggingface.co/t/docker-space-post-endpoint-404-html-error-routing-never-reaches-fastapi-container/163440) · [proxy not forwarding](https://discuss.huggingface.co/t/docker-spaces-returning-data-proxy-not-forwarding-requests-to-container-all-spaces-affected/175500)
- [FastRTC: The Real-Time Communication Library for Python](https://huggingface.co/blog/fastrtc) — 2025-02-25 · [HF × Cloudflare](https://huggingface.co/blog/fastrtc-cloudflare) — 2025-04-09

**Fly.io / Render**
- [Fly.io Pricing](https://fly.io/pricing/) · [Fly Regions](https://fly.io/docs/reference/regions/) — accessed 2026-09-18
- [Render — Deploy for Free](https://render.com/docs/free) — accessed 2026-09-18 · [Render community: free instance type](https://community.render.com/t/the-free-instance-type-e-g-512mb-ram-0-1-cpu/39044)

**Groq**
- [Rate Limits](https://console.groq.com/docs/rate-limits) · [Supported Models](https://console.groq.com/docs/models) · [Model Deprecations](https://console.groq.com/docs/deprecations) · [Speech to Text](https://console.groq.com/docs/speech-to-text) · [Text to Speech](https://console.groq.com/docs/text-to-speech) · [Orpheus](https://console.groq.com/docs/text-to-speech/orpheus) · [Tool Use](https://console.groq.com/docs/tool-use) — all accessed 2026-09-18
- [llmlatency.dev — Groq](https://llmlatency.dev/provider/groq) — data as of 2026-09-10
- [Groq opens EMEA's largest AI compute centre in Saudi Arabia](https://www.middleeastainews.com/p/groq-emea-largest-ai-compute-centre) · [Groq establishes first European data center in Helsinki](https://rcrwireless.com/20250714/ai-infrastructure/groq-data-center) — 2025-07-14

**Google Gemini**
- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) · [Models](https://ai.google.dev/gemini-api/docs/models) · [Pricing](https://ai.google.dev/gemini-api/docs/pricing) · [Speech generation](https://ai.google.dev/gemini-api/docs/speech-generation) · [Live API](https://ai.google.dev/gemini-api/docs/live) · [Session management](https://ai.google.dev/gemini-api/docs/live-session) · [Gemini 3.8 Live](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live) · [Structured outputs](https://ai.google.dev/gemini-api/docs/structured-output) — all accessed 2026-09-18
- [Google announces support for JSON Schema and implicit property ordering in Gemini API](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-structured-outputs/)
- [Google Launches Gemini 3.8 Live and Extended Thinking Voice Models](https://www.unite.ai/google-launches-gemini-3-8-live-and-extended-thinking-voice-models/) — 2026-09-15 · [Simon Willison: Gemini Live audio](https://simonwillison.net/2026/Sep/15/gemini-live/) — 2026-09-15

**VAD / turn detection**
- [@ricky0123/vad-web on npm](https://www.npmjs.com/package/@ricky0123/vad-web) — 0.0.31, 2026-09-12 (verified via registry API) · [Browser user guide](https://docs.vad.ricky0123.com/user-guide/browser/)
- [silero-vad releases](https://github.com/snakers4/silero-vad/releases) — v6.0 2025-08-25, v6.2 2025-12-10
- [LiveKit: Turn detection for voice agents](https://livekit.com/blog/turn-detection-voice-agents-vad-endpointing-model-based-detection) · [LiveKit: Voice agent architecture](https://livekit.com/blog/voice-agent-architecture-stt-llm-tts-pipelines-explained) · [The Voice Agent Latency Playbook](https://hackernoon.com/the-voice-agent-latency-playbook-stt-turn-detection-and-the-tradeoffs-nobody-talks-about)

**Python frameworks**
- PyPI JSON API for `fastapi`, `uvicorn`, `websockets`, `groq`, `google-genai`, `pipecat-ai`, `livekit-agents`, `fastrtc` — queried 2026-09-18
- [Pipecat FastAPI WebSocket Transport](https://docs.pipecat.ai/api-reference/server/services/transport/fastapi-websocket) · [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
