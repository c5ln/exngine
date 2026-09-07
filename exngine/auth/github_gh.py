"""GitHub CLI(`gh`) 기반 로그인.

`gh`는 GitHub 공식 앱으로 OAuth 로그인을 대신 처리해주므로,
사용자가 OAuth App을 직접 등록할 필요가 없다 — 진짜 "그냥 웹 로그인".
exngine은 `gh`의 로그인 상태를 빌려 토큰을 얻는다.
"""

from __future__ import annotations

import shutil
import subprocess


def available() -> bool:
    return shutil.which("gh") is not None


def logged_in() -> bool:
    if not available():
        return False
    r = subprocess.run(
        ["gh", "auth", "status"], capture_output=True, text=True
    )
    return r.returncode == 0


def login() -> None:
    """대화형 `gh auth login` 실행 (브라우저 로그인). 터미널을 그대로 넘겨준다."""
    subprocess.run(["gh", "auth", "login"], check=True)


def token() -> str | None:
    if not available():
        return None
    r = subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True
    )
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def resolve_token() -> str | None:
    """사용할 GitHub 토큰: gh 로그인 우선, 없으면 device flow로 저장한 토큰."""
    t = token()
    if t:
        return t
    from . import store

    return store.get_token("github")

