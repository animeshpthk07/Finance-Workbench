"""Bounded local ingestion for CSV, Excel, and PDF finance documents.

These checks limit accepted workload; they are not a parser sandbox. In particular,
PDF decoded-stream/text checks run after pypdf has allocated those values, and XLS
parsing can allocate internal structures before the frame limits are checked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO, StringIO
from itertools import islice
from pathlib import Path
from typing import Any, Iterable, Optional
from zipfile import ZipFile, is_zipfile

import pandas as pd
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".pdf"}
_READ_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class IngestionLimits:
    """Per-run limits; lower values can be supplied by an authenticated service."""

    max_files: int = 10
    max_file_bytes: int = 20 * 1024 * 1024
    max_total_bytes: int = 40 * 1024 * 1024
    max_rows: int = 50_000
    max_columns: int = 100
    max_xlsx_members: int = 512
    max_xlsx_member_bytes: int = 16 * 1024 * 1024
    max_xlsx_uncompressed_bytes: int = 64 * 1024 * 1024
    max_xlsx_compression_ratio: int = 200
    max_pdf_pages: int = 50
    max_pdf_stream_bytes: int = 4 * 1024 * 1024
    max_pdf_total_stream_bytes: int = 16 * 1024 * 1024
    max_pdf_text_chars: int = 1_000_000

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer.")


DEFAULT_LIMITS = IngestionLimits()


class InputLimitExceeded(ValueError):
    """The complete file or batch must be rejected, never silently truncated."""


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
    return str(getattr(source, "name", "uploaded_document"))


def _read_bounded(stream: Any, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        # Ask for just one byte beyond the limit to detect oversize streams.
        chunk = stream.read(min(_READ_CHUNK_BYTES, max_bytes - total + 1))
        if chunk in (b"", ""):
            return b"".join(chunks)
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8")
        if not isinstance(chunk, bytes):
            raise TypeError("Document stream must return bytes or text.")
        total += len(chunk)
        if total > max_bytes:
            raise InputLimitExceeded(f"File exceeds the {max_bytes:,}-byte input limit.")
        chunks.append(chunk)


def _source_bytes(source: Any, max_bytes: int) -> bytes:
    if isinstance(source, (str, Path)):
        with Path(source).open("rb") as stream:
            return _read_bounded(stream, max_bytes)
    if isinstance(source, bytes):
        if len(source) > max_bytes:
            raise InputLimitExceeded(f"File exceeds the {max_bytes:,}-byte input limit.")
        return source
    if hasattr(source, "read"):
        # Uploaded files are often reused after a Streamlit rerun. Read from their
        # start while leaving the caller's cursor unchanged when seeking works.
        position = None
        try:
            position = source.tell()
            source.seek(0)
        except (AttributeError, OSError):
            position = None
        try:
            return _read_bounded(source, max_bytes)
        finally:
            if position is not None:
                source.seek(position)
    raise TypeError("Document must be a path, bytes, or readable file-like object.")


def _check_frame(frame: pd.DataFrame, limits: IngestionLimits) -> pd.DataFrame:
    if len(frame.index) > limits.max_rows:
        raise InputLimitExceeded(f"Table exceeds the {limits.max_rows:,}-row limit.")
    if len(frame.columns) > limits.max_columns:
        raise InputLimitExceeded(f"Table exceeds the {limits.max_columns:,}-column limit.")
    return frame


def _check_xlsx_archive(payload: bytes, limits: IngestionLimits) -> None:
    """Validate compressed workbook expansion before passing it to pandas."""
    with ZipFile(BytesIO(payload)) as archive:
        members = archive.infolist()
        if len(members) > limits.max_xlsx_members:
            raise InputLimitExceeded(f"Workbook exceeds the {limits.max_xlsx_members:,}-member archive limit.")
        if sum(member.file_size for member in members) > limits.max_xlsx_uncompressed_bytes:
            raise InputLimitExceeded("Workbook exceeds the total expanded archive size limit.")
        total_expanded = 0
        for member in members:
            if member.file_size > limits.max_xlsx_member_bytes:
                raise InputLimitExceeded("Workbook contains an archive member above the expanded size limit.")
            if member.file_size > max(member.compress_size, 1) * limits.max_xlsx_compression_ratio:
                raise InputLimitExceeded("Workbook exceeds the archive compression-ratio limit.")
            if member.flag_bits & 1:
                raise ValueError("Encrypted workbook archives are not supported.")
            # Check actual expansion as well as ZIP metadata, in bounded chunks.
            expanded = 0
            with archive.open(member) as stream:
                while chunk := stream.read(_READ_CHUNK_BYTES):
                    expanded += len(chunk)
                    total_expanded += len(chunk)
                    if expanded > limits.max_xlsx_member_bytes or total_expanded > limits.max_xlsx_uncompressed_bytes:
                        raise InputLimitExceeded("Workbook exceeds the expanded archive size limit.")


def _parse_payload(payload: bytes, document_name: str, limits: IngestionLimits) -> ParsedDocument:
    extension = Path(document_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        return ParsedDocument(
            name=document_name,
            kind="unsupported",
            errors=[f"Unsupported file type: {extension or 'no extension'}"],
        )

    if extension == ".csv":
        try:
            frame = pd.read_csv(BytesIO(payload), nrows=limits.max_rows + 1)
        except UnicodeDecodeError:
            frame = pd.read_csv(StringIO(payload.decode("latin-1")), nrows=limits.max_rows + 1)
        return ParsedDocument(name=document_name, kind="csv", frame=_check_frame(frame, limits))

    if extension in {".xlsx", ".xls"}:
        # Detect archives by content, not just their user-controlled suffix.
        # pandas can recognize an XLSX renamed to .xls; letting it auto-select an
        # engine would otherwise bypass the archive expansion checks below.
        if extension == ".xlsx" or is_zipfile(BytesIO(payload)):
            _check_xlsx_archive(payload, limits)
            engine = "openpyxl"
        else:
            engine = "xlrd"
        # As before, the first worksheet is the supported input contract.
        # Explicit engines also prevent implicit parsing of ZIP-based formats
        # outside the XLSX/XLS input contract (such as ODS and XLSB).
        frame = pd.read_excel(BytesIO(payload), engine=engine, nrows=limits.max_rows + 1)
        return ParsedDocument(name=document_name, kind="excel", frame=_check_frame(frame, limits))

    reader = PdfReader(BytesIO(payload))
    if len(reader.pages) > limits.max_pdf_pages:
        raise InputLimitExceeded(f"PDF exceeds the {limits.max_pdf_pages:,}-page limit.")
    pages: list[str] = []
    total_text = 0
    total_stream = 0
    for page in reader.pages:
        # This is a post-decoding size guard. pypdf can allocate memory while
        # opening the PDF or decoding streams before these checks can run.
        contents = page.get_contents()
        stream_size = len(contents.get_data()) if contents is not None else 0
        total_stream += stream_size
        if stream_size > limits.max_pdf_stream_bytes or total_stream > limits.max_pdf_total_stream_bytes:
            raise InputLimitExceeded("PDF exceeds the decoded content-stream size limit.")
        page_text = page.extract_text() or ""
        total_text += len(page_text) + bool(pages)
        if total_text > limits.max_pdf_text_chars:
            raise InputLimitExceeded(f"PDF exceeds the {limits.max_pdf_text_chars:,}-character extracted-text limit.")
        pages.append(page_text)
    return ParsedDocument(name=document_name, kind="pdf", text="\n".join(pages))


def _error_document(name: str, exc: Exception) -> ParsedDocument:
    return ParsedDocument(name=name, kind=Path(name).suffix.lower().lstrip("."), errors=[str(exc)])


def parse_document(source: Any, name: Optional[str] = None, *, limits: IngestionLimits = DEFAULT_LIMITS) -> ParsedDocument:
    """Read a complete supported document locally, or return a visible error."""
    document_name = _source_name(source, name)
    try:
        return _parse_payload(_source_bytes(source, limits.max_file_bytes), document_name, limits)
    except Exception as exc:
        return _error_document(document_name, exc)


def parse_documents(sources: Iterable[Any], *, limits: IngestionLimits = DEFAULT_LIMITS) -> list[ParsedDocument]:
    """Preflight the batch before parsing; a limit violation rejects the batch.

    Malformed files retain the previous per-file error behavior. A capacity limit
    never returns a partial table, PDF, or successfully parsed subset of the batch.
    """
    inputs = list(islice(sources, limits.max_files + 1))
    if len(inputs) > limits.max_files:
        return [ParsedDocument(name="Upload batch", kind="batch", errors=[f"Batch exceeds the {limits.max_files:,}-file limit. No files were processed."])]
    prepared: list[tuple[str, bytes | None, Exception | None]] = []
    total_bytes = 0
    try:
        for source in inputs:
            name = _source_name(source, None)
            try:
                payload = _source_bytes(source, min(limits.max_file_bytes, limits.max_total_bytes - total_bytes))
            except InputLimitExceeded as exc:
                raise InputLimitExceeded(f"{name}: {exc} Batch file/total byte limits are {limits.max_file_bytes:,}/{limits.max_total_bytes:,}.") from exc
            except Exception as exc:
                prepared.append((name, None, exc))
                continue
            total_bytes += len(payload)
            prepared.append((name, payload, None))
        documents = []
        for name, payload, error in prepared:
            if error is not None:
                documents.append(_error_document(name, error))
                continue
            try:
                documents.append(_parse_payload(payload, name, limits))
            except InputLimitExceeded as exc:
                raise InputLimitExceeded(f"{name}: {exc}") from exc
            except Exception as exc:
                documents.append(_error_document(name, exc))
        return documents
    except InputLimitExceeded as exc:
        return [ParsedDocument(name="Upload batch", kind="batch", errors=[f"{exc} Entire batch rejected; no analysis was produced."])]
