"""하이브리드 검색: BM25 랭킹과 벡터 랭킹을 RRF로 결합."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ..index.embed import Embedder
from ..store import repo

RRF_K = 60  # Reciprocal Rank Fusion 상수


@dataclass
class SearchHit:
    doc_id: str
    score: float
    row: sqlite3.Row


def _rrf(rankings: list[list[str]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    return scores


def search(
    conn: sqlite3.Connection,
    query: str,
    embedder: Embedder,
    *,
    top: int = 10,
    source: str | None = None,
    since: str | None = None,
    pool: int = 50,
) -> list[SearchHit]:
    """하이브리드 검색.

    pool: 각 검색기에서 가져올 후보 수(필터 후 top으로 자름).
    since: ISO 날짜 문자열(예: "2024" / "2024-01-01"). updated_at 기준 필터.
    """
    fts_ids = repo.fts_search(conn, query, pool)
    vec_ids = repo.vec_search(conn, embedder.embed_query(query), pool)

    fused = _rrf([fts_ids, vec_ids])
    if not fused:
        return []

    docs = repo.get_documents(conn, list(fused.keys()))
    hits: list[SearchHit] = []
    for doc_id, score in fused.items():
        row = docs.get(doc_id)
        if row is None:
            continue
        if source and row["source"] != source:
            continue
        if since and (row["updated_at"] or "") < since:
            continue
        hits.append(SearchHit(doc_id=doc_id, score=score, row=row))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top]
