"""문서 청킹.

문단 경계를 우선 보존하면서 ~chunk_size 글자 창으로 묶고, 인접 청크 간 overlap을 둔다.
한국어는 토큰 경계가 모호하므로 글자 기반으로 단순화한다.
"""

from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(p) > chunk_size:
            # 너무 긴 문단은 글자 창으로 강제 분할
            if buf:
                chunks.append(buf)
                buf = ""
            for i in range(0, len(p), chunk_size - overlap):
                chunks.append(p[i : i + chunk_size])
            continue
        if buf and len(buf) + len(p) + 2 > chunk_size:
            chunks.append(buf)
            # overlap: 직전 청크 꼬리를 다음 버퍼 머리로
            tail = buf[-overlap:] if overlap else ""
            buf = (tail + "\n\n" + p).strip()
        else:
            buf = (buf + "\n\n" + p).strip() if buf else p
    if buf:
        chunks.append(buf)
    return chunks
