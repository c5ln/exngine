# exngine

Experience Search Engine — GitHub·Notion·Tistory에 흩어진 내 경험 기록을 한곳에 모아
**자소서 소재를 통합 검색**하는 개인용 CLI 도구.

> 현재 상태: **M0–M1 구현 완료** — SQLite 색인, GitHub 로그인(OAuth Device Flow),
> 수집, 하이브리드 검색(BM25 + 벡터). (Notion/Tistory = M2, LLM 태깅 = M3, 소재 추천 = M4)

## 설치

```bash
pip install -e .            # 기본 (검색·수집)
pip install -e ".[embed]"   # + 로컬 BGE-m3 임베딩 (한국어 의미 검색)
```

`[embed]` 없이 쓰려면 `~/.exngine/config.toml`의 `[embed] backend = "hash"`로 바꾼다
(의존성 없는 개발·검증용 임베더, 의미 검색 품질은 없음).

## 준비: GitHub 로그인

**GitHub CLI(`gh`)만 있으면 앱 등록·토큰 복붙 없이 그냥 웹 로그인된다.**
exngine이 `gh`의 로그인을 빌려 쓴다.

```bash
sudo apt install gh        # 또는 https://cli.github.com
exngine connect github     # 브라우저 로그인 (gh가 처리)
```

> `gh`가 없으면 OAuth App을 직접 등록해 `client_id`를 설정하는 대체 경로(Device Flow)도
> 지원하지만, `gh` 설치가 훨씬 간단해서 권장한다.

## 사용법

```bash
exngine init                       # ~/.exngine 디렉터리·설정·DB 생성
exngine connect github             # 브라우저로 GitHub 로그인 (gh CLI)
exngine auth status                # 연동 상태
exngine sync                       # 수집 → 색인 (증분: 안 바뀐 문서는 스킵)
exngine search "쿠버네티스 트러블슈팅" --top 10
exngine search "협업 경험" --source github --since 2024
exngine status                     # 색인 통계
exngine auth logout github
```

토큰은 OS 키체인(keyring)에 저장하며, 사용 가능한 백엔드가 없으면
`~/.exngine/credentials.json`(권한 600)으로 폴백한다.

## 구조

```
exngine/
├── auth/          로그인(OAuth Device Flow) + 토큰 보관(keyring)
├── connectors/    소스 커넥터 (base, github)
├── store/         SQLite + sqlite-vec(벡터) + FTS5(키워드)
├── index/         청킹 + 임베딩(BGE-m3 / hash)
├── search/        하이브리드 검색 (RRF)
├── pipeline.py    sync: fetch → normalize → chunk → embed → index
└── cli.py         Typer CLI
```
