"""Identity -- name + PIN, and exactly what it protects (D3).

This is a NAMEPLATE, not authentication. It exists so two reviewers on the
same deployed URL never see each other's facts, and so a name collision
refuses rather than silently opening someone else's record. A four-digit PIN
spoken out loud is weak by construction: what it does NOT protect is anyone
who *hears* the PIN, or guesses a common name and a common PIN -- 10**4 is
not a keyspace, and there is no lockout that survives a reload. That trade is
deliberate (AGENTS.md's scope guard forbids real auth here; the deep dive is
the grounding gate, not identity) and is written up again in PR_MEMORY.md.

The fixed phrases below contain number words ON PURPOSE ("four seven one
two") and must NOT be added to tests/test_prompts.py's FIXED_PHRASES dict --
that dict's own rule exists so a caveat or refusal never smuggles an ungated
number; a spoken PIN is neither of those things.
"""

import hashlib
import os
import re

MAX_PIN_ATTEMPTS = 5
MAX_NAME_CHARS = 32

_WHITESPACE_RE = re.compile(r"\s+")


def normalise_name(raw: str) -> str | None:
    """Casefold, collapse whitespace, cap length -- the Dict key suffix.
    Returns None for an empty or whitespace-only name (M13): the Pydantic
    field on SignInIn already rejects the empty string via min_length=1, but
    "   " passes that check and must still be caught here."""
    collapsed = _WHITESPACE_RE.sub(" ", raw).strip().casefold()
    if not collapsed:
        return None
    return collapsed[:MAX_NAME_CHARS]


def _salt() -> str:
    """Read directly from the environment, not app.config.load_settings() --
    that function raises when a PROVIDER key is missing, and memory must not
    inherit that failure mode (main.py's own LOG_LEVEL read is the
    precedent this follows)."""
    return os.environ.get("SARJY_MEMORY_SALT", "sarjy-dev-salt")


def pin_hash(name_key: str, pin: str) -> str:
    """Salted, so the PIN never appears in the panel, the wire, or the logs
    -- only this hash does. Keyed on name_key too, so the same PIN typed by
    two different names hashes to two different values."""
    return hashlib.sha256(f"{name_key}:{pin}:{_salt()}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# Voice sign-in (D8) -- a deterministic sub-flow, never an LLM intent. Two
# turns, no model involved, so the deep dive's prompts stay untouched.
# ---------------------------------------------------------------------------

_SIGN_IN_PHRASES = ("remember me", "sign me in", "remember this for next time")

# Numerals, or the number words "zero" through "nine" -- plus "oh", the
# common spoken stand-in for zero ("four seven oh two").
_DIGIT_WORDS = {
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}

_TOKEN_RE = re.compile(r"[a-zA-Z']+|\d")


def parse_sign_in_request(text: str) -> bool:
    """True if the transcript asks Sarjy to remember the user across
    sessions. Substring match, lowercased -- deliberately simple: a false
    positive just starts a sign-in flow the user can ignore by not
    supplying a PIN next turn (one retry, then out -- D8)."""
    lowered = text.lower()
    return any(phrase in lowered for phrase in _SIGN_IN_PHRASES)


def _digit_tokens(text: str) -> list[tuple[int, str]]:
    """Every token that is a bare digit (a Whisper transcription of "4712"
    splits into "4", "7", "1", "2" as separate tokens the same way spoken
    digit words do) or a digit word, as (position, digit) pairs -- position
    is what lets the caller take the LAST four regardless of how many other
    number-shaped tokens (a house number, an age) came earlier."""
    tokens = _TOKEN_RE.findall(text)
    digits: list[tuple[int, str]] = []
    for i, tok in enumerate(tokens):
        if tok.isdigit():
            for ch in tok:  # "4712" as one token -> four separate digits
                digits.append((i, ch))
        elif tok.lower() in _DIGIT_WORDS:
            digits.append((i, _DIGIT_WORDS[tok.lower()]))
    return digits


def parse_spoken_pin(text: str) -> tuple[str, str] | None:
    """(display_name, "4712") from an utterance like "Omar, four seven one
    two" or "omar 4712" -- or None if fewer than four digit-shaped tokens
    were heard. The PIN is the LAST four digit tokens; the name is
    everything in the transcript before the FIRST digit token, so a name
    that itself sounds like a number word never breaks this (there is no
    realistic name that collides with "four"/"one"/etc.)."""
    tokens = _TOKEN_RE.findall(text)
    digits = _digit_tokens(text)
    if len(digits) < 4:
        return None

    pin = "".join(d for _, d in digits[-4:])
    first_digit_pos = digits[0][0]
    name_tokens = [t for t in tokens[:first_digit_pos] if t not in (",",)]
    name = " ".join(name_tokens).strip(" ,").title()
    if not name:
        return None
    return name, pin


SIGNIN_ASK = (
    "Sure — tell me a name to remember you by, then four digits, one at a "
    "time. Like: Omar, four seven one two."
)
SIGNIN_OK = "Got it, {name} — pin {spoken}. I'll remember you."
SIGNIN_RETRY = (
    "I didn't catch a four-digit PIN — say it digit by digit, or type it "
    "into the panel on screen."
)
SIGNIN_BACK = "Welcome back, {name}."
SIGNIN_NEW = "Nice to meet you, {name}."
SIGNIN_CLASH = (
    "I already know someone called {name}, and that PIN doesn't match. "
    "Try again, or pick a different name."
)
SIGNIN_LOCKED = "That's too many tries — reload the page and start again."


def spoken_digits(pin: str) -> str:
    """"4712" -> "four seven one two" -- SIGNIN_OK reads the PIN back the
    same way it was asked for, never as a bare number (which would also
    trip test_prompts.py's "no fixed phrase has a digit" rule if this were
    interpolated as-is)."""
    words = {v: k for k, v in _DIGIT_WORDS.items() if k != "oh"}
    return " ".join(words[d] for d in pin)
