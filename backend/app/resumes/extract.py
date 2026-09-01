"""Plain-text extraction from uploaded résumé files."""

from __future__ import annotations

import io

_PDF = "application/pdf"
_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_MIN_CHARS = 40

_BY_EXT = {"pdf": _PDF, "docx": _DOCX}


class ExtractionError(Exception):
    """The file could not be read, or produced too little text to be a résumé."""


def content_type_for_key(key: str) -> str:
    ext = key.rsplit(".", 1)[-1].lower()
    if ext not in _BY_EXT:
        raise ExtractionError(f"unsupported file type: .{ext}")
    return _BY_EXT[ext]


def extract_text(data: bytes, content_type: str) -> str:
    if content_type == _PDF:
        text = _from_pdf(data)
    elif content_type == _DOCX:
        text = _from_docx(data)
    else:
        raise ExtractionError(f"unsupported content type: {content_type}")

    text = text.strip()
    if len(text) < _MIN_CHARS:
        raise ExtractionError("the file produced almost no text (scanned image?)")
    return text


def _from_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise ExtractionError(f"could not parse the PDF: {exc}") from exc


def _from_docx(data: bytes) -> str:
    import docx

    try:
        document = docx.Document(io.BytesIO(data))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception as exc:
        raise ExtractionError(f"could not parse the DOCX: {exc}") from exc
