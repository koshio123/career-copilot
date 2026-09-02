"""Small HTML→text helpers shared by the ATS adapters and the JSON-LD parser.

Job descriptions arrive as HTML fragments (Greenhouse `content`, schema.org
`description`, …). We keep them as readable plain text: unescape entities, turn
block tags into newlines, drop the rest, collapse whitespace.
"""

from __future__ import annotations

import html
import re

_BLOCK_END = re.compile(r"</(p|div|li|ul|ol|h[1-6]|br|tr|table|section)\s*>", re.IGNORECASE)
_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_MANY_NL = re.compile(r"\n{3,}")
_TRAILING_WS = re.compile(r"[ \t]+\n")


def html_to_text(fragment: str | None) -> str:
    if not fragment:
        return ""
    text = _BR.sub("\n", fragment)
    text = _BLOCK_END.sub("\n", text)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    text = _TRAILING_WS.sub("\n", text)
    text = _MANY_NL.sub("\n\n", text)
    return text.strip()


def first_nonempty(*values: str | None) -> str | None:
    for value in values:
        if value and value.strip():
            return value.strip()
    return None
