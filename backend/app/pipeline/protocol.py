"""WebSocket message shapes. Decide these before writing either end.

Client -> server:
    binary            16 kHz PCM16 audio frames
    {"t": "start"}    begin a turn (client VAD detected speech)
    {"t": "end"}      end of turn (client VAD endpointed)
    {"t": "barge"}    user began speaking during playback

Server -> client:
    {"t": "state", "value": "idle|listening|thinking|speaking"}
    {"t": "transcript", "text": ..., "final": bool}
    {"t": "segments", "segments": [...]}   rendered, gated, with citations
    {"t": "quota", "remaining": int}
    {"t": "error", "message": ..., "recoverable": bool}
    binary            PCM audio to play

State changes are sent IMMEDIATELY, before the work that follows them. Silence
with no visible state is the worst thing this UI can do.
"""
