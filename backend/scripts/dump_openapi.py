"""Write the committed OpenAPI schema (``backend/openapi.json``).

The frontend generates its API types from this file, so it stays in the repo and
CI fails if it drifts from the code. Run: ``make openapi``.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

OUT = Path(__file__).resolve().parent.parent / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
