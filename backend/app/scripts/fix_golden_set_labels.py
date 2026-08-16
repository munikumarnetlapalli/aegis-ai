"""Fix golden set labels: reclassify items where keywords don't exist in corpus.

Rule: A corpus_answerable item must have at least one expected_chunk keyword
present in the indexed chunks. If none exist, reclassify as corpus_unanswerable.

This is non-destructive: writes a new golden_set_200_v2.json alongside the original.
"""
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, "/app")

from app.core.database import AsyncSessionLocal
from sqlalchemy import text

# Items identified as missing from corpus (from check_corpus_coverage.py)
MISSING_IDS = {
    "gs-030", "gs-035", "gs-039", "gs-046", "gs-047",
    "gs-048", "gs-055", "gs-063", "gs-077", "gs-085",
    "gs-108", "gs-128", "gs-129",
}


async def verify_and_fix():
    gs_path = Path("/app/data/golden-set/golden_set_200.json")
    out_path = Path("/app/data/golden-set/golden_set_200_v2.json")

    with open(gs_path) as f:
        golden_set = json.load(f)

    fixed_items = []
    reclassified = []
    verified_missing = []

    async with AsyncSessionLocal() as db:
        for item in golden_set:
            iid = item.get("id", "")
            classification = item.get("corpus_classification", item.get("classification", ""))

            # Only check corpus_answerable items
            if classification != "corpus_answerable" or iid not in MISSING_IDS:
                fixed_items.append(item)
                continue

            # Double-check: verify keyword is still missing
            kws = item.get("expected_chunks", [])
            in_corpus = False
            for kw in kws:
                row = (await db.execute(
                    text("SELECT 1 FROM chunks WHERE LOWER(content) LIKE :pat LIMIT 1"),
                    {"pat": "%" + kw.lower() + "%"},
                )).fetchone()
                if row:
                    in_corpus = True
                    break

            if in_corpus:
                # Actually in corpus — leave as-is (shouldn't happen)
                print(f"  NOTE: {iid} IS in corpus (false positive in missing list) — keeping as corpus_answerable")
                fixed_items.append(item)
                verified_missing.append(iid)
            else:
                # Not in corpus — reclassify
                new_item = dict(item)
                new_item["corpus_classification"] = "corpus_unanswerable"
                new_item["classification"] = "corpus_unanswerable"
                new_item["reclassification_reason"] = (
                    f"Keywords {kws[:2]} not found in any indexed chunk. "
                    "Reclassified from corpus_answerable → corpus_unanswerable."
                )
                new_item["expected_chunks"] = []  # no expected sources
                fixed_items.append(new_item)
                reclassified.append(iid)
                print(f"  RECLASSIFIED: {iid}  kws={kws[:2]}  |  {item.get('question','')[:60]}")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fixed_items, f, indent=2, ensure_ascii=False)

    # Stats
    answerable_before = sum(1 for i in golden_set if i.get("corpus_classification") == "corpus_answerable")
    answerable_after = sum(1 for i in fixed_items if i.get("corpus_classification") == "corpus_answerable")
    unanswerable_after = sum(1 for i in fixed_items if i.get("corpus_classification") == "corpus_unanswerable")

    print()
    print("=" * 60)
    print("GOLDEN SET LABEL FIX SUMMARY")
    print("=" * 60)
    print(f"Total items:             {len(fixed_items)}")
    print(f"Reclassified:            {len(reclassified)}")
    print(f"corpus_answerable:       {answerable_before} → {answerable_after}")
    print(f"corpus_unanswerable:     {unanswerable_after}")
    print(f"Output:                  {out_path}")
    print()
    print("Expected Recall@5 impact: +{:.1f}pp (removing {}/{} false labels)".format(
        len(reclassified) / answerable_before * 100,
        len(reclassified), answerable_before
    ))


asyncio.run(verify_and_fix())
