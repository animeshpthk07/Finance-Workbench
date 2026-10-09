"""Boundary and adversarial-input checks; no network or model calls."""

from dataclasses import FrozenInstanceError, replace
from io import BytesIO, StringIO
from itertools import count
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pandas as pd
import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from backend.ingestion import DEFAULT_LIMITS, IngestionLimits, parse_document, parse_documents


ROOT = Path(__file__).parent


def uploaded(payload=b"Category,Amount\nRevenue,10\n", name="Actuals.csv"):
    stream = BytesIO(payload)
    stream.name = name
    return stream


def workbook(rows=2, columns=2):
    stream = BytesIO()
    pd.DataFrame({f"column_{i}": range(rows) for i in range(columns)}).to_excel(stream, index=False)
    return stream.getvalue()


def archive(entries, compression=ZIP_STORED):
    stream = BytesIO()
    with ZipFile(stream, "w", compression=compression) as zipped:
        for name, contents in entries:
            zipped.writestr(name, contents)
    return stream.getvalue()


def pdf(texts):
    stream = BytesIO()
    document = canvas.Canvas(stream)
    for text in texts:
        document.drawString(50, 750, text)
        document.showPage()
    document.save()
    return stream.getvalue()


def assert_rejected(document, fragment):
    assert document.frame is None
    assert document.text == ""
    assert fragment in " ".join(document.errors)


def forbidden_parser(*args, **kwargs):
    raise AssertionError("Parser must not run before batch/archive preflight passes.")


def test_limits_are_immutable_and_validate_configuration():
    with pytest.raises(FrozenInstanceError):
        DEFAULT_LIMITS.max_files = 100
    for value in (0, -1, 1.5, True):
        with pytest.raises(ValueError, match="positive integer"):
            IngestionLimits(max_rows=value)


def test_included_csv_excel_and_pdf_are_still_accepted():
    documents = parse_documents([ROOT / "Q2_Budget.xlsx", ROOT / "Q2_Actuals.csv", ROOT / "Q2_Report.pdf"])
    assert len(documents) == 3
    assert not any(document.errors for document in documents)
    assert all(not document.frame.empty for document in documents[:2])
    assert documents[2].text.strip()


@pytest.mark.parametrize("source_kind", ["bytes", "path", "file"])
def test_file_byte_limit_accepts_exact_boundary_and_rejects_one_extra(tmp_path, source_kind):
    payload = b"Amount\n10\n"
    path = tmp_path / "Actuals.csv"
    path.write_bytes(payload)
    sources = {"bytes": payload, "path": path, "file": uploaded(payload)}
    accepted = parse_document(sources[source_kind], "Actuals.csv", limits=replace(DEFAULT_LIMITS, max_file_bytes=len(payload)))
    assert not accepted.errors
    rejected = parse_document(sources[source_kind], "Actuals.csv", limits=replace(DEFAULT_LIMITS, max_file_bytes=len(payload) - 1))
    assert_rejected(rejected, "byte input limit")


def test_bounded_reader_stops_infinite_stream_without_unbounded_read():
    class Endless:
        name = "Actuals.csv"
        requested = []

        def read(self, size):
            assert 0 < size <= 65_536
            self.requested.append(size)
            return b"x" * size

    source = Endless()
    assert_rejected(parse_document(source, limits=replace(DEFAULT_LIMITS, max_file_bytes=5)), "byte input limit")
    assert sum(source.requested) == 6


def test_reader_preserves_uploaded_file_cursor_on_success_and_rejection():
    source = uploaded()
    source.seek(7)
    assert not parse_document(source).errors
    assert source.tell() == 7
    assert parse_document(source, limits=replace(DEFAULT_LIMITS, max_file_bytes=2)).errors
    assert source.tell() == 7


def test_text_stream_uses_encoded_byte_size():
    source = StringIO("Amount\n\u20ac\n")
    document = parse_document(source, "Actuals.csv", limits=replace(DEFAULT_LIMITS, max_file_bytes=10))
    assert_rejected(document, "byte input limit")


def test_nonseekable_stream_with_tell_still_reads():
    class NonSeekable:
        name = "Actuals.csv"

        def __init__(self):
            self.stream = uploaded()

        def read(self, size):
            return self.stream.read(size)

        def tell(self):
            return self.stream.tell()

        def seek(self, position):
            raise OSError("Not seekable")

    assert not parse_document(NonSeekable()).errors


def test_file_count_rejects_batch_without_reading_or_exhausting_generator(monkeypatch):
    consumed = []

    def sources():
        for index in count():
            consumed.append(index)
            yield uploaded()

    monkeypatch.setattr("backend.ingestion.pd.read_csv", forbidden_parser)
    documents = parse_documents(sources(), limits=replace(DEFAULT_LIMITS, max_files=2))
    assert len(documents) == 1
    assert_rejected(documents[0], "2-file limit")
    assert consumed == [0, 1, 2]


def test_total_byte_limit_rejects_entire_batch_before_parsing(monkeypatch):
    payload = b"Amount\n10\n"
    monkeypatch.setattr("backend.ingestion.pd.read_csv", forbidden_parser)
    documents = parse_documents([uploaded(payload), uploaded(payload)], limits=replace(DEFAULT_LIMITS, max_total_bytes=2 * len(payload) - 1))
    assert len(documents) == 1
    assert_rejected(documents[0], "Entire batch rejected")


def test_total_byte_limit_accepts_exact_boundary():
    payload = b"Amount\n10\n"
    documents = parse_documents([uploaded(payload), uploaded(payload)], limits=replace(DEFAULT_LIMITS, max_total_bytes=2 * len(payload)))
    assert len(documents) == 2
    assert not any(document.errors for document in documents)


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_row_limit_accepts_boundary_and_rejects_complete_oversized_file(extension):
    if extension == "csv":
        valid, oversized = b"Amount\n1\n2\n", b"Amount\n1\n2\n3\n"
    else:
        valid, oversized = workbook(rows=2), workbook(rows=3)
    limits = replace(DEFAULT_LIMITS, max_rows=2)
    accepted = parse_document(valid, f"Actuals.{extension}", limits=limits)
    assert not accepted.errors
    assert len(accepted.frame) == 2
    assert_rejected(parse_document(oversized, f"Actuals.{extension}", limits=limits), "2-row limit")


def test_row_limit_rejects_batch_instead_of_returning_partial_analysis():
    documents = parse_documents([uploaded(b"Amount\n1\n"), uploaded(b"Amount\n1\n2\n3\n")], limits=replace(DEFAULT_LIMITS, max_rows=2))
    assert len(documents) == 1
    assert_rejected(documents[0], "Entire batch rejected")


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_column_limit_rejects_wide_tables(extension):
    payload = b"Category,Amount,Secret\nSales,1,x\n" if extension == "csv" else workbook(columns=3)
    assert_rejected(parse_document(payload, f"Actuals.{extension}", limits=replace(DEFAULT_LIMITS, max_columns=2)), "2-column limit")


def test_latin1_csv_fallback_preserves_data_and_limits():
    document = parse_document(b"Category,Amount\nCaf\xe9,10\n", "Actuals.csv", limits=replace(DEFAULT_LIMITS, max_rows=1, max_columns=2))
    assert not document.errors
    assert document.frame.iloc[0, 0] == "Caf\u00e9"


@pytest.mark.parametrize(
    "payload,changed_limit,fragment",
    [
        (archive([("a", b"a"), ("b", b"b")]), {"max_xlsx_members": 1}, "member archive limit"),
        (archive([("a", b"1234")]), {"max_xlsx_member_bytes": 3}, "member above the expanded size limit"),
        (archive([("a", b"123"), ("b", b"456")]), {"max_xlsx_uncompressed_bytes": 5}, "total expanded archive size limit"),
        (archive([("a", b"x" * 10_000)], ZIP_DEFLATED), {"max_xlsx_compression_ratio": 5}, "compression-ratio limit"),
    ],
)
@pytest.mark.parametrize("extension", ["xlsx", "xls"])
def test_xlsx_archive_limits_reject_before_excel_parser(monkeypatch, payload, changed_limit, fragment, extension):
    monkeypatch.setattr("backend.ingestion.pd.read_excel", forbidden_parser)
    assert_rejected(parse_document(payload, f"Actuals.{extension}", limits=replace(DEFAULT_LIMITS, **changed_limit)), fragment)


def test_renamed_xlsx_preserves_data_with_archive_checks():
    payload = workbook(rows=3, columns=2)
    ordinary = parse_document(payload, "Actuals.xlsx")
    renamed = parse_document(payload, "Actuals.xls")
    assert not ordinary.errors
    assert not renamed.errors
    pd.testing.assert_frame_equal(ordinary.frame, renamed.frame)


def test_renamed_oversized_xlsx_rejects_entire_batch():
    documents = parse_documents(
        [uploaded(), uploaded(workbook(rows=3), "Actuals.xls")],
        limits=replace(DEFAULT_LIMITS, max_rows=2),
    )
    assert len(documents) == 1
    assert_rejected(documents[0], "Entire batch rejected")


def test_other_zip_spreadsheet_formats_are_not_auto_detected(monkeypatch):
    # An ODS archive disguised as .xls must not select pandas' ODF parser.
    payload = archive([("mimetype", b"application/vnd.oasis.opendocument.spreadsheet")])
    monkeypatch.setattr("pandas.io.excel._odfreader.ODFReader.__init__", forbidden_parser)
    document = parse_document(payload, "Actuals.xls")
    assert document.errors
    assert "Parser must not run" not in " ".join(document.errors)


def test_invalid_archive_is_an_error_not_a_partial_workbook():
    assert_rejected(parse_document(b"not a zip", "Actuals.xlsx"), "not a zip file")


def test_pdf_page_limit_accepts_boundary_and_rejects_extra_page():
    limits = replace(DEFAULT_LIMITS, max_pdf_pages=1)
    assert not parse_document(pdf(["one"]), "Report.pdf", limits=limits).errors
    assert_rejected(parse_document(pdf(["one", "two"]), "Report.pdf", limits=limits), "1-page limit")


def test_pdf_text_limit_returns_no_partial_text():
    payload = pdf(["Financial evidence"])
    baseline = parse_document(payload, "Report.pdf")
    assert baseline.text
    accepted = parse_document(payload, "Report.pdf", limits=replace(DEFAULT_LIMITS, max_pdf_text_chars=len(baseline.text)))
    assert accepted.text == baseline.text
    assert_rejected(parse_document(payload, "Report.pdf", limits=replace(DEFAULT_LIMITS, max_pdf_text_chars=len(baseline.text) - 1)), "extracted-text limit")


def test_pdf_stream_limit_is_checked_before_text_extraction(monkeypatch):
    payload = pdf(["Financial evidence"])
    monkeypatch.setattr("pypdf._page.PageObject.extract_text", forbidden_parser)
    assert_rejected(parse_document(payload, "Report.pdf", limits=replace(DEFAULT_LIMITS, max_pdf_stream_bytes=1)), "decoded content-stream size limit")


def test_pdf_total_decoded_stream_limit():
    payload = pdf(["one", "two"])
    page_sizes = [len(page.get_contents().get_data()) for page in PdfReader(BytesIO(payload)).pages]
    assert sum(page_sizes) > max(page_sizes)
    limits = replace(DEFAULT_LIMITS, max_pdf_stream_bytes=max(page_sizes), max_pdf_total_stream_bytes=sum(page_sizes) - 1)
    assert_rejected(parse_document(payload, "Report.pdf", limits=limits), "decoded content-stream size limit")


def test_unsupported_and_malformed_files_keep_visible_errors():
    assert "Unsupported file type" in parse_document(b"data", "Notes.txt").errors[0]
    documents = parse_documents([uploaded(), uploaded(b"invalid", "Report.pdf")])
    assert len(documents) == 2
    assert not documents[0].errors
    assert documents[1].errors


def test_empty_batch_returns_no_documents():
    assert parse_documents([]) == []
