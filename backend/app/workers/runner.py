"""Local worker entrypoint (``make worker``).

In Phase 04 this becomes a loop that polls SQS and dispatches each message to
the same handler functions the Lambda deployment uses.
"""

from __future__ import annotations


def main() -> None:
    raise SystemExit("Worker runner is not implemented yet (Phase 04).")


if __name__ == "__main__":
    main()
