"""exngine CLI (Typer)."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from . import config
from .auth import github_device, github_gh, store
from .store import db

app = typer.Typer(
    add_completion=False,
    help="exngine — 흩어진 경험 기록을 통합 검색해 자소서 소재를 찾는다.",
)
auth_app = typer.Typer(help="로그인/토큰 관리")
app.add_typer(auth_app, name="auth")

console = Console()
err = Console(stderr=True)


def _open_db():
    cfg = config.load_config()
    if not cfg.db_path.exists():
        err.print("[red]DB가 없습니다. 먼저 `exngine init`을 실행하세요.[/red]")
        raise typer.Exit(1)
    conn = db.connect(cfg.db_path)
    db.init_schema(conn)
    return cfg, conn


# ---------------------------------------------------------------- init
@app.command()
def init():
    """~/.exngine 디렉터리·설정·DB를 생성한다."""
    home = config.ensure_home()
    cfg = config.load_config()
    conn = db.connect(cfg.db_path)
    db.init_schema(conn)
    conn.close()
    console.print(f"[green]초기화 완료[/green]: {home}")
    console.print(f"  설정 : {config.config_path()}")
    console.print(f"  DB   : {cfg.db_path}")
    console.print(f"  토큰 저장소: {store.backend_name()}")


# ---------------------------------------------------------------- connect
connect_app = typer.Typer(help="소스 로그인(OAuth)")
app.add_typer(connect_app, name="connect")


@connect_app.command("github")
def connect_github():
    """GitHub 로그인. gh CLI가 있으면 앱 등록 없이 그대로 웹 로그인."""
    cfg = config.load_config()

    # 1순위: GitHub 공식 CLI(gh) — OAuth App 등록 불필요
    if github_gh.available():
        if not github_gh.logged_in():
            console.print("[bold]GitHub 로그인[/bold] (gh CLI)")
            console.print("브라우저 로그인 창이 열립니다...\n")
            try:
                github_gh.login()
            except Exception as e:  # noqa: BLE001
                err.print(f"[red]gh 로그인 실패:[/red] {e}")
                raise typer.Exit(1)
        if not github_gh.logged_in():
            err.print("[red]로그인이 확인되지 않습니다.[/red]")
            raise typer.Exit(1)

        from .connectors.github import GitHubConnector

        gh = GitHubConnector(github_gh.token())
        try:
            login = gh.whoami()
        finally:
            gh.close()
        console.print(f"[green]로그인 성공[/green]: @{login} (gh CLI 토큰 사용)")
        return

    # gh가 없을 때만 안내: 설치(권장) 또는 OAuth App + device flow
    client_id = cfg.github_client_id
    if not client_id:
        err.print(
            "[yellow]GitHub CLI(gh)가 설치되어 있지 않습니다.[/yellow]\n"
            "가장 간단한 방법은 gh 설치 후 다시 실행:\n"
            "  [cyan]sudo apt install gh[/cyan]   (또는 https://cli.github.com)\n"
            "  → 이후 [cyan]exngine connect github[/cyan] 만 다시 실행하면 끝.\n\n"
            "[dim]gh 없이 쓰려면 OAuth App을 직접 등록하고 client_id를 설정해야 합니다 "
            "(config.toml [github] client_id 또는 GITHUB_CLIENT_ID).[/dim]"
        )
        raise typer.Exit(1)

    try:
        dc = github_device.request_device_code(client_id, cfg.github_scope)
    except Exception as e:  # noqa: BLE001
        err.print(f"[red]Device code 요청 실패:[/red] {e}")
        raise typer.Exit(1)

    console.print("\n[bold]GitHub 로그인[/bold]")
    console.print(f"  1) 브라우저에서 열기: [cyan]{dc.verification_uri}[/cyan]")
    console.print(f"  2) 코드 입력: [bold yellow]{dc.user_code}[/bold yellow]\n")
    typer.launch(dc.verification_uri)
    console.print("브라우저에서 인증을 마치면 자동으로 진행됩니다... (대기 중)")

    try:
        token = github_device.poll_for_token(client_id, dc)
    except Exception as e:  # noqa: BLE001
        err.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    store.set_token("github", token)

    # 로그인 검증
    from .connectors.github import GitHubConnector

    gh = GitHubConnector(token)
    try:
        login = gh.whoami()
    finally:
        gh.close()
    console.print(f"[green]로그인 성공[/green]: @{login}")


@connect_app.command("notion")
def connect_notion():
    """Notion OAuth 로그인 (M2 예정)."""
    err.print(
        "[yellow]Notion 로그인은 M2에서 구현 예정입니다.[/yellow]\n"
        "(Authorization Code + 로컬 루프백 방식)"
    )
    raise typer.Exit(1)


# ---------------------------------------------------------------- auth
@auth_app.command("status")
def auth_status():
    """연동 상태 확인."""
    table = Table("provider", "status")
    gh_token = github_gh.resolve_token()
    via = "gh CLI" if github_gh.token() else "device flow"
    if gh_token:
        try:
            from .connectors.github import GitHubConnector

            gh = GitHubConnector(gh_token)
            login = gh.whoami()
            gh.close()
            table.add_row("github", f"[green]@{login}[/green] ({via})")
        except Exception:  # noqa: BLE001
            table.add_row("github", "[red]토큰 무효(재로그인 필요)[/red]")
    else:
        table.add_row("github", "[dim]미연동[/dim]")
    table.add_row("notion", "[dim]미연동(M2)[/dim]")
    console.print(table)
    console.print(f"토큰 저장소: {store.backend_name()}")


@auth_app.command("logout")
def auth_logout(provider: str):
    """토큰 삭제. (예: exngine auth logout github)"""
    ok = store.delete_token(provider)
    if ok:
        console.print(f"[green]{provider} 로그아웃 완료[/green]")
    else:
        err.print(f"[yellow]{provider}에 exngine이 저장한 토큰이 없습니다.[/yellow]")
    if provider == "github" and github_gh.token():
        console.print(
            "[dim]gh CLI 로그인을 사용 중입니다. 완전히 끊으려면: [cyan]gh auth logout[/cyan][/dim]"
        )


# ---------------------------------------------------------------- sync
@app.command()
def sync(source: str = typer.Option(None, help="특정 소스만 동기화 (예: github)")):
    """소스를 수집·색인한다 (증분)."""
    cfg, conn = _open_db()
    from .index.embed import get_embedder

    embedder = get_embedder(cfg.embed_backend)

    targets = [source] if source else [s for s, on in cfg.sources.items() if on]
    if not targets:
        err.print("[yellow]활성화된 소스가 없습니다. config.toml의 [sources]를 확인하세요.[/yellow]")
        raise typer.Exit(1)

    from .pipeline import sync_connector

    for src in targets:
        if src != "github":
            err.print(f"[dim]{src}: 아직 미구현 — 건너뜀[/dim]")
            continue
        token = github_gh.resolve_token()
        if not token:
            err.print("[red]GitHub 미연동. `exngine connect github` 먼저 실행하세요.[/red]")
            raise typer.Exit(1)

        from .connectors.github import GitHubConnector

        gh = GitHubConnector(token)
        console.print(f"[bold]github[/bold] 동기화 중... (임베딩 백엔드: {cfg.embed_backend})")

        def _progress(doc, res):
            console.print(f"  [green]+[/green] {doc.title}")

        try:
            res = sync_connector(conn, gh, embedder, on_progress=_progress)
        finally:
            gh.close()
        console.print(
            f"[green]완료[/green]: fetched={res.fetched} "
            f"changed={res.changed} skipped={res.skipped}"
        )
    conn.close()


# ---------------------------------------------------------------- search
@app.command()
def search(
    query: str,
    top: int = typer.Option(10, help="결과 개수"),
    source: str = typer.Option(None, help="소스 필터 (예: github)"),
    since: str = typer.Option(None, help="이 날짜 이후만 (예: 2024 / 2024-01-01)"),
):
    """하이브리드 검색 (BM25 + 벡터)."""
    cfg, conn = _open_db()
    from .index.embed import get_embedder
    from .search.hybrid import search as hybrid_search

    embedder = get_embedder(cfg.embed_backend)
    hits = hybrid_search(conn, query, embedder, top=top, source=source, since=since)
    conn.close()

    if not hits:
        console.print("[dim]결과 없음[/dim]")
        return

    table = Table("score", "source", "title", "url")
    for h in hits:
        table.add_row(
            f"{h.score:.3f}",
            h.row["source"],
            h.row["title"],
            h.row["url"],
        )
    console.print(table)


# ---------------------------------------------------------------- status
@app.command()
def status():
    """색인 통계."""
    cfg, conn = _open_db()
    from .store.repo import stats as get_stats

    s = get_stats(conn)
    conn.close()
    console.print(f"문서 총 {s['total']}개, 청크 {s['chunks']}개")
    for src, n in s["by_source"].items():
        console.print(f"  - {src}: {n}")


if __name__ == "__main__":
    app()
