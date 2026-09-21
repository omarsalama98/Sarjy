"""Deepgram Aura-2 adapter -- streaming TTS over a WebSocket.

Two requests per turn is Block 4's rule (one opener, one answer); this
block only ever makes one, but the adapter itself has no idea how many
times it will be called per turn -- that policy lives in run_turn(), not
here.
"""

import asyncio
import json
import logging
import ssl
import time
from collections.abc import AsyncIterator

import certifi
import websockets

logger = logging.getLogger("sarjy")

SAMPLE_RATE = 24_000

# httpx (Groq's and Gemini's SDKs both use it) bundles certifi and verifies
# against it automatically, on any OS. `websockets` does not -- it trusts
# whatever CA store the interpreter/OS provides, which a debian_slim
# container is not guaranteed to have populated. Built once at import time;
# handshakes are cheap enough that a shared context is fine to reuse.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# `open_timeout` bounds the initial handshake; MAX_SYNTHESIS_S bounds the
# whole call. Never leave a provider's default retry/backoff in place on a
# voice call (TDD.md §Provider traps) -- a hang here is worse than an error,
# and run_turn's except turns either into a fast, visible turn_failed.
OPEN_TIMEOUT_S = 5.0
MAX_SYNTHESIS_S = 20.0


class DeepgramTTS:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self.model = model

    async def synthesize(self, text: str, *, language: str | None = None) -> AsyncIterator[bytes]:
        # container=none is mandatory: Deepgram defaults to wrapping every
        # chunk in its own WAV/RIFF header even for encoding=linear16, which
        # would corrupt playback (a stream of headers, not one stream of
        # samples). The assertion below is what stops this regressing
        # silently after a future URL edit.
        url = (
            "wss://api.deepgram.com/v1/speak"
            f"?model={self.model}&encoding=linear16&container=none&sample_rate={SAMPLE_RATE}"
        )

        async with websockets.connect(
            url,
            # `additional_headers=` -- websockets 16's current name.
            # `extra_headers=` is the legacy-API name and raises TypeError.
            additional_headers={"Authorization": f"Token {self._api_key}"},
            open_timeout=OPEN_TIMEOUT_S,
            ssl=_SSL_CONTEXT,
        ) as ws:
            await ws.send(json.dumps({"type": "Speak", "text": text}))
            t_flush_sent = time.monotonic()
            await ws.send(json.dumps({"type": "Flush"}))
            # Told up front, not after waiting for a reply: no more text is
            # coming in this call. The server keeps streaming whatever
            # audio is still owed, then sends Flushed.
            await ws.send(json.dumps({"type": "Close"}))

            first_chunk = True
            async with asyncio.timeout(MAX_SYNTHESIS_S):
                while True:
                    message = await ws.recv()

                    if isinstance(message, bytes):
                        if first_chunk:
                            if message[:4] == b"RIFF":
                                raise RuntimeError(
                                    "Deepgram sent a WAV container despite container=none "
                                    "-- check the query string wasn't edited"
                                )
                            # Named _after_connect deliberately: this excludes the
                            # WebSocket handshake above, so it is NOT the number a
                            # user waits for. TurnTimings.tts_ttfb_ms (timed at the
                            # call site in run_turn(), from before the connect) is
                            # the one that belongs in a user-facing measurement.
                            logger.info(
                                "tts_ttfb_after_connect_ms=%d",
                                round((time.monotonic() - t_flush_sent) * 1000),
                            )
                            first_chunk = False
                        yield message
                        continue

                    # A JSON control frame: Metadata | Flushed | Cleared | Warning.
                    event = json.loads(message)
                    if event.get("type") == "Flushed":
                        return
