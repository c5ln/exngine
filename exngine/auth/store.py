"""토큰 보관소.

기본은 OS 키체인(keyring). 헤드리스 리눅스 등 사용 가능한 백엔드가 없으면
~/.exngine/credentials.json(권한 600)으로 폴백한다.
"""

from __future__ import annotations

import json
import os
import stat

from .. import config

SERVICE = "exngine"


def _fallback_path():
    return config.home_dir() / "credentials.json"


def _keyring_ok() -> bool:
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring

        return not isinstance(keyring.get_keyring(), FailKeyring)
    except Exception:
        return False


def _file_load() -> dict:
    p = _fallback_path()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _file_save(data: dict) -> None:
    p = _fallback_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)  # 600


def set_token(provider: str, token: str) -> None:
    if _keyring_ok():
        import keyring

        keyring.set_password(SERVICE, provider, token)
    else:
        data = _file_load()
        data[provider] = token
        _file_save(data)


def get_token(provider: str) -> str | None:
    if _keyring_ok():
        import keyring

        return keyring.get_password(SERVICE, provider)
    return _file_load().get(provider)


def delete_token(provider: str) -> bool:
    if _keyring_ok():
        import keyring

        try:
            keyring.delete_password(SERVICE, provider)
            return True
        except Exception:
            return False
    data = _file_load()
    if provider in data:
        del data[provider]
        _file_save(data)
        return True
    return False


def backend_name() -> str:
    return "keyring" if _keyring_ok() else "file(~/.exngine/credentials.json)"
