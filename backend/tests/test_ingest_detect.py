from __future__ import annotations

import pytest

from app.ingest.detect import detect_ats


@pytest.mark.parametrize(
    ("url", "vendor", "board"),
    [
        ("https://boards.greenhouse.io/acme", "greenhouse", "acme"),
        ("https://job-boards.greenhouse.io/acme/jobs/123", "greenhouse", "acme"),
        ("https://jobs.lever.co/acme", "lever", "acme"),
        ("https://jobs.eu.lever.co/acme/1-2-3", "lever", "acme"),
        ("https://jobs.ashbyhq.com/acme", "ashby", "acme"),
        ("https://acme.ashbyhq.com/", "ashby", "acme"),
    ],
)
def test_detect_from_url(url: str, vendor: str, board: str) -> None:
    match = detect_ats(url)
    assert match is not None
    assert (match.vendor, match.board_id) == (vendor, board)


def test_detect_from_embed_script() -> None:
    html = """
    <html><body>
      <div id="grnhse_app"></div>
      <script src="https://boards.greenhouse.io/embed/job_board/js?for=acmecorp"></script>
    </body></html>
    """
    match = detect_ats("https://acme.com/careers", html)
    assert match is not None
    assert match.vendor == "greenhouse"
    assert match.board_id == "acmecorp"


def test_no_match_on_plain_careers_page() -> None:
    assert detect_ats("https://acme.com/careers", "<html><body>Join us</body></html>") is None


def test_embed_host_but_reserved_slug_is_ignored() -> None:
    assert detect_ats("https://boards.greenhouse.io/embed") is None
