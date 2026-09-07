"""DB 연결 및 스키마."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec

from ..config import EMBED_DIM

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS documents (
    id           TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    external_id  TEXT NOT NULL,
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    content      TEXT NOT NULL DEFAULT '',
    summary      TEXT,
    tech_stack   TEXT NOT NULL DEFAULT '[]',     -- JSON 배열
    competencies TEXT NOT NULL DEFAULT '[]',     -- JSON 배열
    created_at   TEXT,
    updated_at   TEXT,
    content_hash TEXT NOT NULL,
    indexed_at   TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id  TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    text    TEXT NOT NULL,
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);

-- 키워드 검색(BM25). 한국어 부분일치를 위해 trigram 토크나이저 사용.
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title,
    content,
    doc_id UNINDEXED,
    tokenize = 'trigram'
);

-- 청크 단위 dense 임베딩.
CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
    chunk_id INTEGER PRIMARY KEY,
    embedding FLOAT[{EMBED_DIM}]
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
