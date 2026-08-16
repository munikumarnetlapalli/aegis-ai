"""Check which corpus_answerable items have ANY matching chunk in the corpus."""
import asyncio
import json
import sys
sys.path.insert(0, "/app")

from app.core.database import AsyncSessionLocal
from sqlalchemy import text


async def main():
    with open("/app/data/golden-set/golden_set_200.json") as f:
        gs = json.load(f)

    answerable = [i for i in gs if i.get("corpus_classification") == "corpus_answerable"]
    print(f"Total corpus_answerable: {len(answerable)}")

    missing = []
    found = []

    async with AsyncSessionLocal() as db:
        for item in answerable:
            kws = item.get("expected_chunks", [])
            if not kws:
                found.append(item["id"])
                continue
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
                found.append(item["id"])
            else:
                missing.append((item["id"], kws[:2], item["question"][:70]))

    print()
    print(f"Found in corpus: {len(found)}")
    print(f"MISSING from corpus: {len(missing)}")
    print()
    for iid, kws, q in missing:
        print(f"  MISSING: {iid}  kws={kws}  |  {q}")

    # Write results
    result = {
        "total_answerable": len(answerable),
        "found_count": len(found),
        "missing_count": len(missing),
        "found_ids": found,
        "missing_items": [{"id": m[0], "kws": m[1], "q": m[2]} for m in missing],
    }
    with open("/app/data/corpus_coverage_check.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\nSaved to /app/data/corpus_coverage_check.json")


asyncio.run(main())
