"""임베딩 백엔드.

- BGEEmbedder: 로컬 BGE-m3 (한국어 강함, 무료). sentence-transformers 필요.
- HashEmbedder: 의존성 없는 결정적 해시 임베더. 오프라인 개발·테스트용
  (의미 검색 품질은 없음, 파이프라인 검증용).
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

from ..config import EMBED_DIM


class Embedder(Protocol):
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class HashEmbedder:
    """단어 해시를 차원에 누적하는 bag-of-words 식 결정적 임베더."""

    def __init__(self, dim: int = EMBED_DIM):
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in text.lower().split():
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        return _normalize(vec)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class BGEEmbedder:
    """BAAI/bge-m3 dense 임베딩 (1024차원, L2 정규화)."""

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.dim = EMBED_DIM
        self._model_name = model_name
        self._model = None  # 지연 로딩

    def _ensure(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise RuntimeError(
                    "BGE-m3 백엔드에는 sentence-transformers가 필요합니다.\n"
                    '  pip install -e ".[embed]"\n'
                    "또는 config.toml의 [embed] backend = \"hash\" 로 변경하세요."
                ) from e
            self._model = SentenceTransformer(self._model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._ensure()
        embs = self._model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        return [e.tolist() for e in embs]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def get_embedder(backend: str) -> Embedder:
    if backend == "hash":
        return HashEmbedder()
    if backend == "bge":
        return BGEEmbedder()
    raise ValueError(f"알 수 없는 임베딩 백엔드: {backend}")
