"""문서 CRUD + 색인 + 검색 쿼리."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import sqlite_vec

from ..models import ExperienceDoc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def upsert_document(conn: sqlite3.Connection, doc: ExperienceDoc) -> bool:
    """문서를 upsert한다. 내용이 바뀌어 재색인이 필요하면 True를 반환."""
    row = conn.execute(
        "SELECT content_hash FROM documents WHERE id = ?", (doc.id,)
    ).fetchone()
    if row and row["content_hash"] == doc.content_hash:
        return False

    conn.execute(
        """
        INSERT INTO documents
            (id, source, external_id, title, url, content, summary,
             tech_stack, competencies, created_at, updated_at, content_hash, indexed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title, url=excluded.url, content=excluded.content,
            summary=excluded.summary, tech_stack=excluded.tech_stack,
            competencies=excluded.competencies, created_at=excluded.created_at,
            updated_at=excluded.updated_at, content_hash=excluded.content_hash,
            indexed_at=excluded.indexed_at
        """,
        (
            doc.id, doc.source, doc.external_id, doc.title, doc.url, doc.content,
            doc.summary, json.dumps(doc.tech_stack, ensure_ascii=False),
            json.dumps(doc.competencies, ensure_ascii=False),
            _iso(doc.created_at), _iso(doc.updated_at), doc.content_hash, _now(),
        ),
    )
    return True


def reindex_document(
    conn: sqlite3.Connection,
    doc: ExperienceDoc,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    """문서의 FTS·청크·벡터를 통째로 교체한다."""
    # 기존 벡터/청크/FTS 제거
    conn.execute(
        "DELETE FROM vec_chunks WHERE chunk_id IN "
        "(SELECT id FROM chunks WHERE doc_id = ?)",
        (doc.id,),
    )
    conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc.id,))
    conn.execute("DELETE FROM documents_fts WHERE doc_id = ?", (doc.id,))

    # FTS (문서 단위 1행)
    conn.execute(
        "INSERT INTO documents_fts (title, content, doc_id) VALUES (?,?,?)",
        (doc.title, doc.content, doc.id),
    )

    # 청크 + 벡터
    for ordinal, (text, emb) in enumerate(zip(chunks, embeddings)):
        cur = conn.execute(
            "INSERT INTO chunks (doc_id, ordinal, text) VALUES (?,?,?)",
            (doc.id, ordinal, text),
        )
        chunk_id = cur.lastrowid
        conn.execute(
            "INSERT INTO vec_chunks (chunk_id, embedding) VALUES (?, ?)",
            (chunk_id, sqlite_vec.serialize_float32(emb)),
        )


# ---- 검색 ----

def fts_search(conn: sqlite3.Connection, query: str, k: int) -> list[str]:
    """BM25 상위 문서 id 리스트(점수 좋은 순)."""
    q = query.strip()
    if len(q) < 3:  # trigram은 3자 미만 매칭 불가
        return []
    match = '"' + q.replace('"', '""') + '"'
    try:
        rows = conn.execute(
            """
            SELECT doc_id FROM documents_fts
            WHERE documents_fts MATCH ?
            ORDER BY bm25(documents_fts)
            LIMIT ?
            """,
            (match, k),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [r["doc_id"] for r in rows]


def vec_search(conn: sqlite3.Connection, embedding: list[float], k: int) -> list[str]:
    """벡터 KNN 결과를 문서 단위로 집계한 id 리스트(가까운 순)."""
    # vec0 KNN은 k 제약을 벡터 스캔에 직접 줘야 한다(JOIN 뒤 LIMIT은 인식 안 됨).
    rows = conn.execute(
        """
        WITH knn AS (
            SELECT chunk_id, distance
            FROM vec_chunks
            WHERE embedding MATCH ? AND k = ?
        )
        SELECT c.doc_id AS doc_id, knn.distance AS distance
        FROM knn JOIN chunks c ON c.id = knn.chunk_id
        ORDER BY knn.distance
        """,
        (sqlite_vec.serialize_float32(embedding), k),
    ).fetchall()
    seen: dict[str, float] = {}
    for r in rows:
        d = r["doc_id"]
        if d not in seen or r["distance"] < seen[d]:
            seen[d] = r["distance"]
    return [d for d, _ in sorted(seen.items(), key=lambda kv: kv[1])]


def get_documents(conn: sqlite3.Connection, ids: list[str]) -> dict[str, sqlite3.Row]:
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT * FROM documents WHERE id IN ({placeholders})", ids
    ).fetchall()
    return {r["id"]: r for r in rows}


def stats(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    by_source = conn.execute(
        "SELECT source, COUNT(*) AS n FROM documents GROUP BY source"
    ).fetchall()
    chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    return {
        "total": total,
        "by_source": {r["source"]: r["n"] for r in by_source},
        "chunks": chunks,
    }
