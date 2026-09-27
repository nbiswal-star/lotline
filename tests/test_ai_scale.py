"""The citywide AI-reader report regenerates offline from cached model outputs."""

from __future__ import annotations

import pytest

from evaluation import ai_scale

pytestmark = pytest.mark.skipif(not ai_scale.OUTPUTS.exists(), reason="no cached model outputs")


def test_report_regenerates_offline_and_deterministically(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    a = ai_scale.render(ai_scale.compute())
    b = ai_scale.render(ai_scale.compute())
    assert a == b
    out = tmp_path / "report.md"
    r = ai_scale.write_report(out)
    assert out.read_text(encoding="utf-8") == a
    # Pre-registered primary numbers from the frozen verifier over the cached pass-1 outputs.
    m = r["metrics"]
    assert len(r["pins"]) == 150 and r["status_counts"] == {"ok": 150}
    assert (m["AI"]["tp"], m["AI"]["fp"]) == (30, 0)
    assert m["NONE"]["tp"] + m["NONE"]["fp"] == 0


def test_model_never_saw_reference_data():
    records = ai_scale.load_records()
    assert {r.source_id for recs in records.values() for r in recs} == {"pli_violations"}
