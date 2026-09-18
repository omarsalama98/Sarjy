"""FastAPI app and the conversation WebSocket.

The client sends binary audio frames (16 kHz PCM16) and JSON control messages;
the server replies with JSON events and binary audio.

Protocol shapes live in app/pipeline/protocol.py — decide them before writing
either end (.claude/rules/voice/pipeline.md).
"""

from fastapi import FastAPI, WebSocket

app = FastAPI(title="Sarjy")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws")
async def conversation(ws: WebSocket) -> None:
    """One conversation. Lives for the length of the call.

    NOTE: on Modal this is bounded by the Function `timeout` (default 300 s).
    A ten-minute call dies at five minutes unless it is set explicitly.
    This is inference, not documented — verify with a 10-minute connection
    before building on it (docs/plans/TDD.md §Deployment).
    """
    await ws.accept()
    raise NotImplementedError("Day 1: echo loop first, then the pipeline.")
