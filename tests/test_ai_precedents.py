"""ZBA extraction: provenance, semantic-kind checks, cache, and deterministic matching."""

from __future__ import annotations

from lotline.ai import precedents as p


ROCKLAND = "rockland-avenue-96-of-2026"
DECISION = (
    "The Applicant's request for a use variance from Section 911.02 to allow a two-unit "
    "residential use on the Subject Property is hereby DENIED and the request for a dimensional "
    "variance from the exterior side setback requirement in Section 903.03.D.2 to allow a 5' "
    "exterior side setback for the proposed structure is hereby APPROVED."
)


def raw_card(*, kind: str = "use_variance", description: str | None = None) -> dict:
    return {
        "case_number": "96 of 2026",
        "decision_date": "2026-08-18",
        "address": "Rockland Avenue",
        "district": "R1D-H",
        "lot_description": None,
        "reliefs": [{
            "kind": kind,
            "description": description or "request for a use variance from Section 911.02",
            "outcome": "denied",
            "quote": DECISION,
        }],
        "rationale_quote": None,
    }


def test_valid_card_keeps_semantically_supported_relief_kind() -> None:
    text = p.decision_text(ROCKLAND)
    assert text is not None
    card = p.verify_card(ROCKLAND, raw_card(), text, "https://example.test/decision.pdf")
    assert card.verified
    assert card.reliefs[0].kind == "use_variance"
    assert card.reliefs[0].outcome == "denied"


def test_exact_quote_cannot_smuggle_wrong_relief_kind() -> None:
    text = p.decision_text(ROCKLAND)
    assert text is not None
    raw = raw_card(kind="special_exception", description="exterior side setback requirement")
    card = p.verify_card(ROCKLAND, raw, text)
    assert not card.verified
    assert card.reliefs == ()
    assert card.rejected_fields >= 1


def test_dimensional_text_cannot_be_labeled_use_variance() -> None:
    text = p.decision_text("camp-street-16-of-2026")
    assert text is not None
    quote = ("The Applicant's request for variances from Section 903.03.B.2 to allow the "
             "construction of a house with limited front and rear setbacks is hereby APPROVED.")
    raw = {
        "case_number": "16 of 2026",
        "decision_date": "2026-04-29",
        "address": "3315 Camp Street",
        "district": "R2-L",
        "lot_description": None,
        "reliefs": [{"kind": "use_variance", "description": "rear setback required",
                     "outcome": "approved", "quote": quote}],
        "rationale_quote": None,
    }
    card = p.verify_card("camp-street-16-of-2026", raw, text)
    assert card.reliefs == ()


def test_all_indexed_documents_have_text_and_stable_metadata() -> None:
    index = p.read_index()
    assert len(index) == 8
    for slug, row in index.items():
        text = p.decision_text(slug)
        assert text and row["case_number"] in p.normalize(text)
        assert row["source_url"].startswith("https://")
        assert row["sha256"] and row["decision_date"]


def test_invalid_slug_cannot_escape_data_directory() -> None:
    assert p.decision_text("../secrets") is None
