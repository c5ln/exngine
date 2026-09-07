"""통합 문서 모델."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["github", "notion", "tistory"]


class RawDoc(BaseModel):
    """connector가 반환하는 정규화 직전 문서."""

    source: Source
    external_id: str  # 소스 내 고유 id (멱등 키)
    title: str
    url: str
    content: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    tech_stack: list[str] = Field(default_factory=list)
    raw_meta: dict = Field(default_factory=dict)


class ExperienceDoc(RawDoc):
    """색인 대상 문서. (요약·역량 태깅은 M3에서 추가)"""

    summary: str | None = None
    competencies: list[str] = Field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.source}:{self.external_id}"

    @property
    def content_hash(self) -> str:
        """본문 변경 감지용 해시. 증분 동기화에 사용."""
        payload = json.dumps(
            {
                "title": self.title,
                "content": self.content,
                "tech_stack": sorted(self.tech_stack),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def from_raw(cls, raw: RawDoc) -> "ExperienceDoc":
        return cls(**raw.model_dump())
