"""Memory — two stores, one per anonymous session.

The deployment is a public URL with no login and two reviewers may open it
minutes apart. Without a session id they share one memory and reviewer B is
told their passport is Saudi. Identity is an anonymous id in localStorage,
one row per id. No auth, no accounts.

Two stores, because the brief's own worked example is "what's my favorite
color?" and a closed travel schema fails it:

    profile  — typed travel facts that drive lookups
    facts    — open key/value, anything the user says about themselves

Both are shown in the "what Sarjy remembers about you" panel, with a clear
button. That panel is how requirement 2 gets demonstrated in one glance.
"""

from dataclasses import dataclass, field


@dataclass
class TravelProfile:
    passport: str | None = None
    home_city: str | None = None
    dietary: list[str] = field(default_factory=list)
    past_destinations: list[str] = field(default_factory=list)


async def get_profile(session_id: str) -> TravelProfile:
    raise NotImplementedError


async def remember_fact(session_id: str, key: str, value: str) -> None:
    """Open-ended. 'favourite colour' -> 'green'."""
    raise NotImplementedError


async def forget_all(session_id: str) -> None:
    """Backs the clear button. A reviewer will use it."""
    raise NotImplementedError
