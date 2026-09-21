"""RoutedTTS -- language picks the adapter. No network."""

from collections.abc import AsyncIterator

import pytest

from app.providers.factory import RoutedTTS


class _CaptureTTS:
    def __init__(self, name: str) -> None:
        self.model = name
        self.seen: list[tuple[str, str | None]] = []

    async def synthesize(self, text: str, *, language: str | None = None) -> AsyncIterator[bytes]:
        self.seen.append((text, language))
        yield b"\x00\x00"


@pytest.mark.asyncio
async def test_routed_tts_sends_arabic_to_orpheus() -> None:
    en = _CaptureTTS("aura")
    ar = _CaptureTTS("orpheus")
    routed = RoutedTTS(en=en, ar=ar)  # type: ignore[arg-type]
    chunks = [c async for c in routed.synthesize("مرحبا", language="ar")]
    assert chunks == [b"\x00\x00"]
    assert ar.seen == [("مرحبا", "ar")]
    assert en.seen == []
    assert routed.model == "orpheus"


@pytest.mark.asyncio
async def test_routed_tts_defaults_to_english() -> None:
    en = _CaptureTTS("aura")
    ar = _CaptureTTS("orpheus")
    routed = RoutedTTS(en=en, ar=ar)  # type: ignore[arg-type]
    async for _ in routed.synthesize("hello", language="en"):
        pass
    async for _ in routed.synthesize("hello"):
        pass
    assert [t for t, _ in en.seen] == ["hello", "hello"]
    assert ar.seen == []
    assert routed.model == "aura"
