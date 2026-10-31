"""X post URL parsing — the one place that knows what a post permalink looks like.

The backend never fetches these URLs (ARCHITECTURE §10); it only validates and
canonicalizes them so the same post always has the same ``post_url`` string.
That matters beyond cosmetics: the archive worker's URL short-circuit (ADR-022)
and the CLI merge rule (ADR-010) both match on it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

HANDLE_PATTERN = r"^[A-Za-z0-9_]{1,15}$"
REST_ID_PATTERN = r"^\d{1,25}$"

_STATUS_URL = re.compile(
    r"^https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/"
    r"(?P<handle>[A-Za-z0-9_]{1,15})/status(?:es)?/(?P<post_id>\d{1,25})"
    r"(?:[/?#].*)?$",
    re.IGNORECASE,
)

X_HOSTS = frozenset(
    {"x.com", "twitter.com", "www.x.com", "www.twitter.com", "mobile.twitter.com", "mobile.x.com"}
)


@dataclass(frozen=True)
class StatusUrl:
    handle: str
    post_id: str

    @property
    def canonical(self) -> str:
        return f"https://x.com/{self.handle}/status/{self.post_id}"


def parse_status_url(url: str) -> StatusUrl | None:
    match = _STATUS_URL.match((url or "").strip())
    if not match:
        return None
    return StatusUrl(handle=match["handle"], post_id=match["post_id"])


def is_x_host(url: str) -> bool:
    """ADR-025: hosts SPN2 refuses at the domain level."""
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return False
    return host in X_HOSTS


def same_handle(a: str | None, b: str | None) -> bool:
    """X handles are case-insensitive identifiers; display case varies."""
    return bool(a) and bool(b) and a.lower() == b.lower()
