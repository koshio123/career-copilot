"""Company normalisation and the fallback dedup key (ADR-0009)."""

from __future__ import annotations

import pytest

from app.jobs.normalize import dedup_key, normalize_company


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("株式会社メルカリ", "メルカリ"),
        ("メルカリ（株）", "メルカリ"),
        ("Acme, Inc.", "acme"),
        ("Foo Bar Co., Ltd.", "foo bar"),
        ("  Spaced   Out  ", "spaced out"),
        ("ＡＢＣ Corp", "abc"),
    ],
)
def test_normalize_company(raw: str, expected: str) -> None:
    assert normalize_company(raw) == expected


def test_dedup_key_is_stable_across_surface_differences() -> None:
    a = dedup_key(company="株式会社Acme", title="Senior Backend Engineer", location="Tokyo")
    b = dedup_key(company="Acme  Inc.", title="senior backend engineer", location="tokyo")
    assert a == b


def test_dedup_key_differs_on_real_difference() -> None:
    a = dedup_key(company="Acme", title="Backend Engineer", location="Tokyo")
    b = dedup_key(company="Acme", title="Frontend Engineer", location="Tokyo")
    assert a != b
