"""커넥터 인터페이스.

새 소스 추가 = Connector를 구현하고 fetch()에서 RawDoc 리스트를 반환하면 끝.
인증 토큰은 auth.store에서 꺼내 쓰고, 커넥터는 토큰의 출처를 알 필요가 없다.
"""

from __future__ import annotations

from typing import Iterable, Protocol

from ..models import RawDoc


class Connector(Protocol):
    source: str

    def fetch(self) -> Iterable[RawDoc]: ...
