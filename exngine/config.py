"""설정·경로 로딩.

- 비밀이 아닌 설정: ~/.exngine/config.toml
- 비밀(클라이언트 시크릿 등): .env 또는 OS 환경변수
- 토큰: OS 키체인(keyring) — auth/store.py 참고
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # 현재 작업 디렉터리의 .env를 환경변수로 로드

# BGE-m3 dense 임베딩 차원. vec0 테이블 스키마가 이 값에 고정되므로 변경 시 DB 재생성 필요.
EMBED_DIM = 1024

DEFAULT_CONFIG = """\
# exngine 설정 (비밀 아님). 토큰은 OS 키체인에 저장됩니다.

[sources]
# 동기화 대상 소스 on/off
github = true
notion = false
tistory = false

[github]
# OAuth Device Flow용 client_id. 없으면 환경변수 GITHUB_CLIENT_ID 사용.
# https://github.com/settings/developers 에서 OAuth App 생성 후 "Enable Device Flow" 체크.
client_id = ""
scope = "repo read:user"

[embed]
# bge: 로컬 BGE-m3 (pip install -e ".[embed]" 필요)
# hash: 의존성 없는 결정적 해시 임베더 (오프라인 테스트·개발용)
backend = "bge"
"""


@dataclass
class Config:
    home: Path
    db_path: Path
    sources: dict
    github: dict
    embed: dict

    @property
    def github_client_id(self) -> str:
        return os.environ.get("GITHUB_CLIENT_ID") or self.github.get("client_id", "")

    @property
    def github_scope(self) -> str:
        return self.github.get("scope", "repo read:user")

    @property
    def embed_backend(self) -> str:
        return os.environ.get("EXNGINE_EMBED_BACKEND") or self.embed.get("backend", "bge")


def home_dir() -> Path:
    return Path(os.environ.get("EXNGINE_HOME", Path.home() / ".exngine"))


def config_path() -> Path:
    return home_dir() / "config.toml"


def db_path() -> Path:
    return home_dir() / "exngine.db"


def load_config() -> Config:
    home = home_dir()
    cfg_file = config_path()
    data: dict = {}
    if cfg_file.exists():
        data = tomllib.loads(cfg_file.read_text(encoding="utf-8"))
    return Config(
        home=home,
        db_path=db_path(),
        sources=data.get("sources", {"github": True, "notion": False, "tistory": False}),
        github=data.get("github", {}),
        embed=data.get("embed", {}),
    )


def ensure_home() -> Path:
    """~/.exngine 디렉터리와 기본 config.toml을 생성한다."""
    home = home_dir()
    home.mkdir(parents=True, exist_ok=True)
    cfg = config_path()
    if not cfg.exists():
        cfg.write_text(DEFAULT_CONFIG, encoding="utf-8")
    return home
