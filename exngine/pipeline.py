"""동기화 파이프라인: fetch → normalize → (증분) chunk → embed → index."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .connectors.base import Connector
from .index.chunk import chunk_text
from .index.embed import Embedder
from .models import ExperienceDoc
from .store import repo


@dataclass
class SyncResult:
    fetched: int = 0
    changed: int = 0
    skipped: int = 0


def sync_connector(
    conn: sqlite3.Connection,
    connector: Connector,
    embedder: Embedder,
    *,
    on_progress=None,
) -> SyncResult:
    res = SyncResult()
    for raw in connector.fetch():
        res.fetched += 1
        doc = ExperienceDoc.from_raw(raw)
        changed = repo.upsert_document(conn, doc)
        if not changed:
            res.skipped += 1
            continue

        chunks = chunk_text(doc.content)
        embeddings = embedder.embed_documents(chunks) if chunks else []
        repo.reindex_document(conn, doc, chunks, embeddings)
        res.changed += 1
        conn.commit()
        if on_progress:
            on_progress(doc, res)
    conn.commit()
    return res
