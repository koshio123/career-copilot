from __future__ import annotations

from app.ingest.jsonld import extract_job_postings
from app.models.enums import SourceType

_SINGLE = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "JobPosting",
  "title": "Backend Engineer",
  "description": "<p>Build &amp; run services.</p>",
  "hiringOrganization": {"@type": "Organization", "name": "Acme"},
  "jobLocation": {
    "@type": "Place",
    "address": {"addressLocality": "Tokyo", "addressCountry": "JP"}
  },
  "employmentType": "FULL_TIME",
  "jobLocationType": "TELECOMMUTE",
  "baseSalary": {
    "@type": "MonetaryAmount",
    "currency": "JPY",
    "value": {
      "@type": "QuantitativeValue",
      "minValue": 8000000, "maxValue": 12000000, "unitText": "YEAR"
    }
  },
  "url": "https://acme.com/jobs/be"
}
</script></head><body></body></html>
"""

_GRAPH = """
<script type="application/ld+json">
{"@graph": [
  {"@type": "WebPage"},
  {"@type": ["JobPosting"], "title": "SRE", "description": "Ops.",
   "hiringOrganization": "Acme", "url": "/jobs/sre"}
]}
</script>
"""


def test_single_job_posting() -> None:
    jobs = extract_job_postings(_SINGLE, base_url="https://acme.com/careers")
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source_type is SourceType.JSON_LD
    assert j.structured.title == "Backend Engineer"
    assert j.structured.company_name == "Acme"
    assert "Build & run services." in j.structured.description
    assert j.structured.location == "Tokyo, JP"
    assert j.structured.remote is True
    assert j.structured.salary_min == 8_000_000
    assert j.structured.apply_url == "https://acme.com/jobs/be"


def test_graph_wrapper_and_relative_url() -> None:
    jobs = extract_job_postings(_GRAPH, base_url="https://acme.com/careers/")
    assert len(jobs) == 1
    assert jobs[0].structured.title == "SRE"
    assert jobs[0].url == "https://acme.com/jobs/sre"
    assert "salary" in jobs[0].structured.needs_review
    assert "description" not in jobs[0].structured.needs_review


def test_ignores_non_job_and_broken_json() -> None:
    html = """
    <script type="application/ld+json">{"@type": "Organization", "name": "Acme"}</script>
    <script type="application/ld+json">{ broken json </script>
    """
    assert extract_job_postings(html, base_url="https://acme.com") == []
