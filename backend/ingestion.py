"""Safe local ingestion for CSV, Excel, and PDF finance documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".pdf"}


@dataclass
class ParsedDocument:
    name: str
    kind: str
    frame: Optional[pd.DataFrame] = None
    text: str = ""
    errors: list[str] = field(default_factory=list)


def _source_name(source: Any, supplied_name: Optional[str]) -> str:
    if supplied_name:
        return supplied_name
    if isinstance(source, (str, Path)):
        return Path(source).name
    return getattr(source, "name", "uploaded_document")


def _source_bytes(source: Any) -> bytes:
    if isinstance(source, (str, Path)):
        return Path(source).read_bytes()
    if isinstance(source, bytes):
        return source
    if hasattr(source, "getvalue"):
        return source.getvalue()
    if hasattr(source, "read"):
        payload = source.read()
        return payload.encode("utf-8") if isinstance(payload, str) else payload
    raise TypeError("Document must be a path, bytes, or uploaded file-like object.")


def parse_document(source: Any, name: Optional[str] = None) -> ParsedDocument:
    """Read one supported document without performing any external upload."""

    document_name = _source_name(source, name)
    extension = Path(document_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        return ParsedDocument(
            name=document_name,
            kind="unsupported",
            errors=[f"Unsupported file type: {extension or 'no extension'}"],
        )

    try:
        payload = _source_bytes(source)
        if extension == ".csv":
            try:
                frame = pd.read_csv(BytesIO(payload))
            except UnicodeDecodeError:
                frame = pd.read_csv(StringIO(payload.decode("latin-1")))
            return ParsedDocument(name=document_name, kind="csv", frame=frame)

        if extension in {".xlsx", ".xls"}:
            frame = pd.read_excel(BytesIO(payload))
            return ParsedDocument(name=document_name, kind="excel", frame=frame)

        reader = PdfReader(BytesIO(payload))
        pages = [page.extract_text() or "" for page in reader.pages]
        return ParsedDocument(name=document_name, kind="pdf", text="
".join(pages))
    except Exception as exc:
        return ParsedDocument(name=document_name, kind=extension.lstrip("."), errors=[str(exc)])


def parse_documents(sources: Iterable[Any]) -> list[ParsedDocument]:
    return [parse_document(source) for source in sources]
