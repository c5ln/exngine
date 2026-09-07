"""GitHub OAuth Device Flow.

CLI에 적합한 로그인 방식: 로컬 서버/리다이렉트 없이 터미널에 코드를 표시하고
사용자가 브라우저에서 입력하면 토큰을 폴링해서 받아온다. (`gh auth login`과 동일 방식)
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

DEVICE_CODE_URL = "https://github.com/login/device/code"
TOKEN_URL = "https://github.com/login/oauth/access_token"
JSON = {"Accept": "application/json"}


class DeviceFlowError(RuntimeError):
    pass


@dataclass
class DeviceCode:
    device_code: str
    user_code: str
    verification_uri: str
    interval: int
    expires_in: int


def request_device_code(client_id: str, scope: str) -> DeviceCode:
    r = httpx.post(
        DEVICE_CODE_URL,
        data={"client_id": client_id, "scope": scope},
        headers=JSON,
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    if "error" in d:
        raise DeviceFlowError(f"{d['error']}: {d.get('error_description', '')}")
    return DeviceCode(
        device_code=d["device_code"],
        user_code=d["user_code"],
        verification_uri=d["verification_uri"],
        interval=int(d.get("interval", 5)),
        expires_in=int(d.get("expires_in", 900)),
    )


def poll_for_token(client_id: str, dc: DeviceCode) -> str:
    """사용자가 인증을 마칠 때까지 폴링한다. 성공 시 access_token 반환."""
    interval = dc.interval
    deadline = time.monotonic() + dc.expires_in
    while time.monotonic() < deadline:
        time.sleep(interval)
        r = httpx.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "device_code": dc.device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers=JSON,
            timeout=30,
        )
        r.raise_for_status()
        d = r.json()
        if "access_token" in d:
            return d["access_token"]
        err = d.get("error")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval = int(d.get("interval", interval + 5))
            continue
        if err in ("expired_token", "access_denied"):
            raise DeviceFlowError(f"인증 실패: {err}")
        raise DeviceFlowError(f"예상치 못한 응답: {d}")
    raise DeviceFlowError("인증 시간 초과 — 다시 시도하세요.")
