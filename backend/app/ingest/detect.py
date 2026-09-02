"""Route A detection — is this URL (or page) served by a known ATS?

Two signals, in order:

1. The registered URL's host/path is itself an ATS board
   (`boards.greenhouse.io/acme`, `jobs.lever.co/acme`, `acme.ashbyhq.com`).
2. The registered URL is a company careers page that *embeds* an ATS board — a
   `<script>` / `<iframe>` / `<a>` pointing at one of the hosts above.

Either way we return ``(vendor, board_id)``; the caller hands that to the
matching adapter. No match ⇒ fall through to route B (JSON-LD) then C.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

_SLUG = r"[A-Za-z0-9][A-Za-z0-9._-]*"

# (vendor, host-path regex on the registered URL itself)
_URL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("greenhouse", re.compile(rf"^(?:boards|job-boards)\.greenhouse\.io/({_SLUG})")),
    ("lever", re.compile(rf"^jobs(?:\.eu)?\.lever\.co/({_SLUG})")),
    ("ashby", re.compile(rf"^jobs\.ashbyhq\.com/({_SLUG})")),
]
_ASHBY_SUBDOMAIN = re.compile(rf"^({_SLUG})\.ashbyhq\.com$")

# In-page embeds, matched against the whole HTML.
_EMBED_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("greenhouse", re.compile(rf"greenhouse\.io/embed/job_board[^\"'?]*[?&]for=({_SLUG})")),
    ("greenhouse", re.compile(rf"(?:boards|job-boards)\.greenhouse\.io/({_SLUG})")),
    ("lever", re.compile(rf"jobs(?:\.eu)?\.lever\.co/({_SLUG})")),
    ("ashby", re.compile(rf"jobs\.ashbyhq\.com/({_SLUG})")),
    ("ashby", re.compile(rf"api\.ashbyhq\.com/posting-api/job-board/({_SLUG})")),
]

_NOT_A_BOARD = {"embed", "api", "www", "job_board", "job-board", "shared"}


@dataclass(frozen=True, slots=True)
class AtsMatch:
    vendor: str
    board_id: str


def detect_ats(url: str, html: str | None = None) -> AtsMatch | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    host_path = f"{host}{parsed.path}"

    for vendor, pattern in _URL_PATTERNS:
        m = pattern.search(host_path)
        if m and m.group(1) not in _NOT_A_BOARD:
            return AtsMatch(vendor, m.group(1))

    sub = _ASHBY_SUBDOMAIN.match(host)
    if sub and sub.group(1) not in _NOT_A_BOARD:
        return AtsMatch("ashby", sub.group(1))

    if html:
        for vendor, pattern in _EMBED_PATTERNS:
            m = pattern.search(html)
            if m and m.group(1) not in _NOT_A_BOARD:
                return AtsMatch(vendor, m.group(1))

    return None
