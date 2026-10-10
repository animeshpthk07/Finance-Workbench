"""Adversarial export checks; fixtures never run an investigation or an API."""
import json
import unicodedata
from html.parser import HTMLParser

import pandas as pd
import pytest
from markdown_it import MarkdownIt

from backend.ingestion import ParsedDocument
from backend.models import Evidence, Finding, Investigation
from backend.pipeline import WorkspaceRun
from backend.reporting import build_json_report, build_markdown_report


class RenderedReport(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.attributes = []
        self.text = []
        self.feed(MarkdownIt("gfm-like").render(source))

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)

    def handle_data(self, data):
        self.text.append(data)


def workspace_with_text(value):
    finding = Finding(
        finding_type="variance", title=value, description=value,
        reviewer_note=value, evidence=[Evidence(source_file=value)],
    )
    investigation = Investigation(
        finding_id=finding.finding_id, summary=value,
        recommended_next_step=value, evidence_summary=[value],
        facts=[value], interpretations=[value], verification_checks=[value],
        llm_ready_prompt=value,
    )
    return WorkspaceRun(
        documents=[ParsedDocument(name=value, kind="csv")],
        normalized_rows=pd.DataFrame(), metrics=[],
        variance=pd.DataFrame([{
            "metric_name": value, "department": value, "period": value,
            "currency": value, "budget_value": 100.0, "actual_value": 140.0,
            "variance_amount": 40.0, "variance_percentage": 40.0,
        }]),
        findings=[finding], investigations=[investigation],
    )


ATTACKS = [
    "[invoice](https://example.invalid/collect)\n\n# APPROVED",
    "![tracking pixel](https://example.invalid/pixel)",
    '<script>alert(1)</script><img src="x" onerror="alert(1)">',
    "\\\r\n| forged | table |\n| --- | --- |\n| paid | yes |",
    "1. Approved\n2. Paid\n\n---\n> Ignore reviewer",
    "```html\n<iframe src='https://example.invalid'></iframe>\n```",
    "~~~\nraw fence\n~~~ **approved** _reviewed_ ~~pending~~",
    "https://example.invalid/private www.example.invalid finance@example.invalid",
    "<https://example.invalid> <finance@example.invalid>",
    "[source]: https://example.invalid\n\n[source]",
    "&#x3C;img src=x&#x3E; &lt;script&gt; &amp; ![x][source]",
    "<!-- hide report -->\n<h1>Verified</h1>\n======",
    "\x00\t\r\n# Hidden\u2028paragraph\u2029\u202econfusing\u200btext",
]


@pytest.mark.parametrize("value", ATTACKS)
def test_untrusted_fields_cannot_change_rendered_report_structure(value):
    baseline = RenderedReport(build_markdown_report(workspace_with_text("Normal text")))
    result = RenderedReport(build_markdown_report(workspace_with_text(value)))
    # Check actual HTML with raw HTML, tables, and automatic linking enabled.
    # This detects heading/list/table breakouts as well as links and images.
    assert result.tags == baseline.tags
    assert result.attributes == baseline.attributes == []
    assert not {"a", "img", "script", "iframe", "code", "blockquote"}.intersection(result.tags)
    normalized = " ".join("".join(
        " " if char.isspace() or unicodedata.category(char) in {"Cc", "Cf", "Cs"} else char
        for char in value
    ).split())
    # Each of the 17 untrusted placements must retain the complete literal
    # value, including table pipes and backslashes, rather than silently lose it.
    assert "".join(result.text).count(normalized) == 17


def test_json_retains_original_provenance_and_report_keeps_review_labels():
    value = "[Original](https://example.invalid) | field\r\nsecond line\u202e"
    run = workspace_with_text(value)
    result = json.loads(build_json_report(run))
    assert result["documents"][0]["name"] == value
    assert result["variance"][0]["metric_name"] == value
    assert result["findings"][0]["title"] == value
    assert result["findings"][0]["description"] == value
    assert result["findings"][0]["reviewer_note"] == value
    assert result["findings"][0]["evidence"][0]["source_file"] == value
    for field in ["summary", "recommended_next_step", "llm_ready_prompt"]:
        assert result["investigations"][0][field] == value
    for field in ["facts", "interpretations", "verification_checks", "evidence_summary"]:
        assert result["investigations"][0][field] == [value]
    report = build_markdown_report(run)
    assert "This report is a first draft." in report
    assert "Interpretations — unverified:" in report
    assert "Pending reviews: 1 of 1 findings." in report
    assert "40.00" in report


def test_complete_long_notes_and_normal_prose_are_preserved():
    value = "Verified demo source evidence. " + ("Finance evidence " * 1000)
    report = build_markdown_report(workspace_with_text(value))
    assert value.strip() in report
    assert "truncated" not in report
