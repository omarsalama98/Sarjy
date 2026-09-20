"""Exercises the real handler through FastAPI's TestClient -- no network, but
a real ASGI request/response cycle, which is the strongest test the handler
gets without an actual deployment.
"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import PROTOCOL_VERSION, app

client = TestClient(app)


def _hello(session_id: str | None = None) -> dict[str, object]:
    return {"t": "hello", "v": PROTOCOL_VERSION, "session_id": session_id, "client_ts_ms": 0}


def test_hello_then_ready_then_state_idle() -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json(_hello())

        ready = ws.receive_json()
        assert ready["t"] == "ready"
        assert ready["resumed"] is False
        assert ready["connection_n"] == 1
        assert ready["v"] == PROTOCOL_VERSION

        state = ws.receive_json()
        assert state["t"] == "state"
        assert state["value"] == "idle"


def test_ping_gets_a_pong() -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json(_hello())
        ws.receive_json()  # ready
        ws.receive_json()  # state

        ws.send_json({"t": "ping", "id": "c7", "client_ts_ms": 123})
        pong = ws.receive_json()
        assert pong["t"] == "pong"
        assert pong["id"] == "c7"
        assert pong["client_ts_ms"] == 123


def test_malformed_text_gets_an_error_and_the_socket_stays_usable() -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json(_hello())
        ws.receive_json()
        ws.receive_json()

        ws.send_text("{")
        err = ws.receive_json()
        assert err["t"] == "error"
        assert err["code"] == "bad_message"
        assert err["recoverable"] is True

        # One bad frame must not cost a conversation -- prove the socket is
        # still usable with an ordinary ping.
        ws.send_json({"t": "ping", "id": "still-alive", "client_ts_ms": 0})
        pong = ws.receive_json()
        assert pong["t"] == "pong"
        assert pong["id"] == "still-alive"


def test_binary_frame_is_unsupported_not_fatal() -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json(_hello())
        ws.receive_json()
        ws.receive_json()

        ws.send_bytes(b"\x00\x01")
        err = ws.receive_json()
        assert err["t"] == "error"
        assert err["code"] == "unsupported"
        assert err["recoverable"] is True


def test_reconnect_with_the_returned_id_resumes() -> None:
    """The whole block's thesis: a session outlives its connection."""
    with client.websocket_connect("/ws") as ws1:
        ws1.send_json(_hello())
        ready1 = ws1.receive_json()
        session_id = ready1["session_id"]
        assert ready1["resumed"] is False
        assert ready1["connection_n"] == 1
        ws1.receive_json()  # state

    with client.websocket_connect("/ws") as ws2:
        ws2.send_json(_hello(session_id))
        ready2 = ws2.receive_json()
        assert ready2["resumed"] is True
        assert ready2["session_id"] == session_id
        assert ready2["connection_n"] == 2


def test_protocol_version_mismatch_gets_error_then_closing() -> None:
    with client.websocket_connect("/ws") as ws:
        bad_hello = {"t": "hello", "v": PROTOCOL_VERSION + 1, "session_id": None, "client_ts_ms": 0}
        ws.send_json(bad_hello)

        err = ws.receive_json()
        assert err["t"] == "error"
        assert err["code"] == "protocol_version"
        assert err["recoverable"] is False

        closing = ws.receive_json()
        assert closing["t"] == "closing"
        assert closing["reason"] == "protocol_version"
        assert closing["reconnect"] is False


def test_bye_closes_without_error() -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json(_hello())
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"t": "bye", "reason": "leave"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_non_hello_first_message_closes_without_a_reply() -> None:
    """The handshake is the one place a bad message is fatal -- even a
    well-formed message is fatal here if it isn't `hello`."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"t": "ping", "id": "too-early", "client_ts_ms": 0})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
