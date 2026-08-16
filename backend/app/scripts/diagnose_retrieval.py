"""Live retrieval diagnostic — traces pipeline stages for failing golden-set items."""
import asyncio
import sys
sys.path.insert(0, "/app")

from app.core.database import AsyncSessionLocal
from app.retrieval.service import RetrievalService
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.rrf import reciprocal_rank_fusion
from app.reranking.reranker import get_reranker
from app.core.config import get_settings

settings = get_settings()

TEST_CASES = [
    ("gs-007", "What is underinsured motorist coverage and when does it apply?",
     ["underinsured motorist", "limits are not enough"]),
    ("gs-027", "What is split limits notation and how are limits expressed?",
     ["split"]),
    ("gs-029", "What is permissive user coverage and who is covered?",
     ["permissive"]),
    ("gs-036", "How do annual mileage rating tiers affect auto insurance premiums?",
     ["annual", "mileage"]),
    ("gs-058", "What is the definition and coverage for custom equipment on autos?",
     ["custom"]),
    ("gs-063", "What is the indemnity principle in property and casualty insurance?",
     ["indemnity"]),
    ("gs-071", "What is normalized Discounted Cumulative Gain and how is it calculated?",
     ["nDCG", "Discounted Cumulative Gain"]),
]


def find_rank(chunks, kws):
    for i, c in enumerate(chunks, 1):
        if any(kw.lower() in c.content.lower() for kw in kws):
            return i
    return 0


async def run():
    async with AsyncSessionLocal() as db:
        failure_stages = {"dense": 0, "bm25": 0, "rrf": 0, "reranker": 0, "none": 0}

        print(f"\n{'ID':<8} {'Dense@20':<10} {'BM25@20':<10} {'RRF@20':<10} {'Rnk@5':<8} Stage")
        print("-" * 60)

        for qid, q, kws in TEST_CASES:
            dense_svc = RetrievalService()
            dense = await dense_svc.retrieve(
                query=q, jurisdiction="GLOBAL",
                allowed_roles=["viewer"], top_k=20, db=db
            )
            bm25_svc = BM25Retriever()
            bm25 = await bm25_svc.retrieve(
                query=q, jurisdiction="GLOBAL",
                allowed_roles=["viewer"], top_k=20, db=db
            )
            fused = reciprocal_rank_fusion(dense, bm25, k=settings.rrf_k, top_n=20)
            reranker = get_reranker()
            reranked = reranker.rerank(query=q, results=fused, top_k=5)

            dr = find_rank(dense, kws)
            br = find_rank(bm25, kws)
            rr = find_rank(fused, kws)
            rrk = find_rank(reranked, kws)

            stage = (
                "dense" if not dr else
                "bm25" if not br else
                "rrf" if not rr else
                "reranker" if not rrk else
                "none"
            )
            failure_stages[stage] = failure_stages.get(stage, 0) + 1

            d = str(dr) if dr else "MISS"
            b = str(br) if br else "MISS"
            r2 = str(rr) if rr else "MISS"
            rk = str(rrk) if rrk else "MISS"
            print(f"{qid:<8} {d:<10} {b:<10} {r2:<10} {rk:<8} {stage}")

            if not rrk:
                print(f"  Top reranked sources: " + ", ".join(
                    c.provenance.filename[:25] + " p" + str(c.provenance.page)
                    for c in reranked
                ))
                # Show top dense chunk snippet
                if dense:
                    top_d = dense[0]
                    print(f"  Top dense chunk: ...{top_d.content[:80]}... (score={top_d.score:.3f})")

        print()
        print("Failure stages:", failure_stages)


asyncio.run(run())
