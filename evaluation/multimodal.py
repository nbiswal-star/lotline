"""Full-cohort multimodal audit, reported as review signals rather than truth.

There are no independent present-condition image labels. Accordingly this
experiment reports coverage, abstention, and discordance with a dated
assessment classification; it does not call either modality ground truth and
does not report accuracy.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from evaluation.common import Checks, REPO_ROOT, Section, md_table, scope_note, screen_all, snapshot
from lotline.ai import visual
from lotline.models import Outcome

REPEATABILITY = REPO_ROOT / "data" / "multimodal" / "repeatability.json"


def summarize() -> dict[str, Any]:
    snap = snapshot()
    outcomes = screen_all()
    categories: Counter[str] = Counter()
    by_record: dict[str, Counter[str]] = {
        "assessment_structure": Counter(), "assessment_vacant": Counter()
    }
    valid_assets = valid_reads = 0
    structure_discordant = routed_structure_discordant = 0
    rows: list[dict[str, Any]] = []
    for pin in sorted(snap.treasury):
        item = snap.treasury[pin]
        asset = visual.asset_for(pin)
        valid_assets += asset is not None
        read = visual.load_cached(asset) if asset is not None else None
        valid_reads += read is not None
        if read is None:
            continue
        category = read.structure_footprint
        record_class = "assessment_structure" if item.is_structure else "assessment_vacant"
        categories[category] += 1
        by_record[record_class][category] += 1
        discordant = item.is_structure and category == "not_visible"
        routed = outcomes[pin].outcome is Outcome.STRUCTURE
        structure_discordant += discordant
        routed_structure_discordant += discordant and routed
        rows.append({
            "pin": pin,
            "record_class": record_class,
            "engine_outcome": outcomes[pin].outcome.value,
            "visual_category": category,
            "image_quality": read.image_quality,
            "review_flag": bool(discordant),
        })
    return {
        "cohort_n": len(snap.treasury),
        "valid_assets": valid_assets,
        "valid_reads": valid_reads,
        "categories": dict(categories),
        "assessment_structure_n": sum(by_record["assessment_structure"].values()),
        "assessment_vacant_n": sum(by_record["assessment_vacant"].values()),
        "by_record": {key: dict(value) for key, value in by_record.items()},
        "structure_discordant_n": structure_discordant,
        "routed_structure_discordant_n": routed_structure_discordant,
        "rows": rows,
    }


def run() -> Section:
    result = summarize()
    repeat = json.loads(REPEATABILITY.read_text(encoding="utf-8"))
    checks = Checks()
    checks.check("every sale-feed parcel has a hash-verified image",
                 result["valid_assets"] == result["cohort_n"],
                 f"{result['valid_assets']}/{result['cohort_n']}")
    checks.check("every image has a schema-validated cached visual read",
                 result["valid_reads"] == result["cohort_n"],
                 f"{result['valid_reads']}/{result['cohort_n']}")
    checks.check("fixed visual categories partition all valid reads",
                 sum(result["categories"].values()) == result["valid_reads"],
                 str(result["categories"]))
    engine_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((REPO_ROOT / "lotline" / "engine").glob("*.py"))
    )
    checks.check("screening engine has no visual-model dependency", "ai.visual" not in engine_sources,
                 "visual reads are an audit layer only")
    checks.check("two-run stability artifact matches the frozen current run",
                 repeat["run_b"]["categories"] == result["categories"] and
                 repeat["run_b"]["assessment_structure_review_flags"] ==
                 result["structure_discordant_n"],
                 f"exact category agreement {repeat['exact_category_agreement_n']}/"
                 f"{repeat['exact_category_agreement_denominator']}")

    structure = result["by_record"]["assessment_structure"]
    vacant = result["by_record"]["assessment_vacant"]
    comparison = [
        ("Assessment: structure", result["assessment_structure_n"],
         structure.get("clearly_visible", 0), structure.get("not_visible", 0),
         structure.get("unclear", 0)),
        ("Assessment: vacant land", result["assessment_vacant_n"],
         vacant.get("clearly_visible", 0), vacant.get("not_visible", 0),
         vacant.get("unclear", 0)),
    ]
    markdown = "\n\n".join([
        "Claude classified only coarse visible properties inside a County parcel outline. The dated "
        "assessment class is a comparison field, **not an image label or ground truth**. `not_visible` "
        "alongside `assessment_structure` creates a human-review flag; it does not reclassify the parcel.",
        md_table(["Record field", "N", "Footprint visible", "Not visible", "Unclear"],
                 comparison, sort=False),
        f"**AI-versus-no-image counterfactual.** The record-only route performs zero visual–record "
        f"comparisons. The current bounded-observer run adds **{result['structure_discordant_n']}** review flags "
        f"across the 96-record feed, including **{result['routed_structure_discordant_n']}** among "
        "records routed as structures, while abstaining as `unclear` on "
        f"**{result['categories'].get('unclear', 0)}** images. Engine outcomes remain identical.",
        f"**Two-run stability.** Exact footprint categories agreed on "
        f"**{repeat['exact_category_agreement_n']}/{repeat['exact_category_agreement_denominator']}** "
        f"parcels. Total review flags varied {repeat['run_a']['assessment_structure_review_flags']}–"
        f"{repeat['run_b']['assessment_structure_review_flags']} and abstentions varied "
        f"{repeat['run_a']['categories']['unclear']}–{repeat['run_b']['categories']['unclear']}; the "
        f"**same {repeat['structure_routed_review_set_agreement_n']} structure-routed records** were flagged "
        "in both runs. The first raw cache was overwritten, so this is a build-time stability record, "
        "not a preregistered reliability estimate.",
        checks.markdown(),
        scope_note(
            "No blind present-condition image labels or imagery acquisition dates are available. "
            "Therefore these counts measure multimodal coverage and record discordance, not visual "
            "accuracy, demolition, vacancy, decision improvement, or LLM superiority. Each flag must "
            "be resolved against dated imagery, permits, inspection, or field verification."
        ),
    ])
    return Section(
        id="multimodal",
        title="Full-cohort parcel imagery × records audit",
        markdown=markdown,
        data={**result, "repeatability": repeat},
        verdict_inputs={
            "cohort_n": result["cohort_n"],
            "review_flags": result["structure_discordant_n"],
            "routed_structure_review_flags": result["routed_structure_discordant_n"],
            "abstentions": result["categories"].get("unclear", 0),
            "two_run_exact_agreement": repeat["exact_category_agreement_n"],
        },
        assertions=checks.items,
    )
