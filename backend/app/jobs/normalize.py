"""Company-name normalisation and the job dedup key (ADR-0009).

``dedup_key`` collapses the same logical posting seen via different routes /
re-fetches into one ``job_postings`` row. For an ATS identity the caller uses
``"{vendor}:{external_id}"`` directly; this module handles the fallback:
``hash(normalize(company) | normalize(title) | normalize(location))``.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

# Legal suffixes / prefixes to drop, case-insensitive. Japanese forms are
# matched anywhere; Latin forms only as trailing tokens. The list holds both
# half- and full-width parenthesised "(株)" because sources use either.
_JP_LEGAL = (
    "株式会社",
    "有限会社",
    "合同会社",
    "合資会社",
    "合名会社",
    "(株)",
    "（株）",  # noqa: RUF001 - full-width form is intentional
)
_LATIN_LEGAL = re.compile(
    r"[\s,]*\b(inc|inc\.|incorporated|llc|l\.l\.c\.|ltd|ltd\.|limited|co|co\.|"
    r"corp|corp\.|corporation|gmbh|k\.k\.|kk|pllc|plc)\b\.?$",
    re.IGNORECASE,
)
_WS = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    """NFKC fold, lowercase, collapse whitespace."""
    folded = unicodedata.normalize("NFKC", value or "").casefold().strip()
    return _WS.sub(" ", folded)


def normalize_company(name: str) -> str:
    folded = unicodedata.normalize("NFKC", name or "").strip()
    for token in _JP_LEGAL:
        folded = folded.replace(token, "")
    folded = folded.casefold().strip()
    prev = None
    while prev != folded:  # strip stacked suffixes ("Foo Co., Ltd.")
        prev = folded
        folded = _LATIN_LEGAL.sub("", folded).strip()
    return _WS.sub(" ", folded)


def dedup_key(*, company: str, title: str, location: str | None = None) -> str:
    basis = "|".join(
        (normalize_company(company), normalize_text(title), normalize_text(location or ""))
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()
