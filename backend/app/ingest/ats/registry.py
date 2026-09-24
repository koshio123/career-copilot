from __future__ import annotations

from app.ingest.ats.ashby import AshbyAdapter
from app.ingest.ats.base import AtsAdapter
from app.ingest.ats.greenhouse import GreenhouseAdapter
from app.ingest.ats.lever import LeverAdapter

ADAPTERS: dict[str, AtsAdapter] = {
    a.vendor: a for a in (GreenhouseAdapter(), LeverAdapter(), AshbyAdapter())
}


def get_adapter(vendor: str) -> AtsAdapter | None:
    return ADAPTERS.get(vendor)
