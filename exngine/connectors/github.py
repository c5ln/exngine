"""GitHub 커넥터.

본인 소유 repo의 메타데이터 + README를 수집한다.
(commit/PR/issue 본문 수집은 후속 단계에서 확장)
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

import httpx

from ..models import RawDoc

API = "https://api.github.com"


class GitHubAuthError(RuntimeError):
    pass


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


class GitHubConnector:
    source = "github"

    def __init__(self, token: str):
        if not token:
            raise GitHubAuthError("GitHub 토큰이 없습니다. `exngine connect github` 먼저 실행하세요.")
        self._client = httpx.Client(
            base_url=API,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

    def whoami(self) -> str:
        r = self._client.get("/user")
        r.raise_for_status()
        return r.json()["login"]

    def _repos(self) -> Iterable[dict]:
        page = 1
        while True:
            r = self._client.get(
                "/user/repos",
                params={
                    "per_page": 100,
                    "page": page,
                    "affiliation": "owner",
                    "sort": "updated",
                },
            )
            r.raise_for_status()
            batch = r.json()
            if not batch:
                return
            yield from batch
            if len(batch) < 100:
                return
            page += 1

    def _readme(self, full_name: str) -> str:
        r = self._client.get(
            f"/repos/{full_name}/readme",
            headers={"Accept": "application/vnd.github.raw+json"},
        )
        if r.status_code == 404:
            return ""
        r.raise_for_status()
        return r.text

    def fetch(self) -> Iterable[RawDoc]:
        for repo in self._repos():
            full_name = repo["full_name"]
            topics = repo.get("topics", []) or []
            language = repo.get("language")
            tech = topics + ([language] if language else [])

            readme = self._readme(full_name)
            parts = [
                f"# {full_name}",
                repo.get("description") or "",
                ("Topics: " + ", ".join(topics)) if topics else "",
                ("Language: " + language) if language else "",
                "",
                readme,
            ]
            content = "\n".join(p for p in parts if p).strip()

            yield RawDoc(
                source="github",
                external_id=str(repo["id"]),
                title=full_name,
                url=repo["html_url"],
                content=content,
                created_at=_parse_dt(repo.get("created_at")),
                updated_at=_parse_dt(repo.get("pushed_at") or repo.get("updated_at")),
                tech_stack=sorted(set(t for t in tech if t)),
                raw_meta={
                    "stars": repo.get("stargazers_count"),
                    "fork": repo.get("fork"),
                    "private": repo.get("private"),
                },
            )

    def close(self) -> None:
        self._client.close()
