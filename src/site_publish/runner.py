"""Пересборка внешнего сайта из админки (ds_search#225, ADR-0018).

Запускает `node scripts/publish-pages.mjs` из ds_site (выгрузка из GAR -> фильтр по
publish_permission -> next build -> force-push gh-pages) отдельным процессом; лог и код
возврата пишутся в data/site_publish/. Работает только там, где есть ds_site, node, gh
(локально в WSL; в docker-контейнере ds_search — нет).
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / "data" / "site_publish"
_COUNT_RE = re.compile(r"^(\w+): (\d+) выгружено, отброшено (\{.*\})\s*$", re.M)
_URL_RE = re.compile(r"^опубликовано: (\S+)", re.M)


def _log() -> Path:
    return STATE_DIR / "last.log"


def _state() -> Path:
    return STATE_DIR / "state.json"


def _exit() -> Path:
    return STATE_DIR / "exit_code"


def ds_site_dir() -> Path:
    return Path(os.environ.get("DS_SITE_DIR") or ROOT.parent / "ds_site")


def find_node() -> str | None:
    """node из PATH или из nvm (Streamlit из `bash -lc` nvm может не видеть)."""
    found = shutil.which("node")
    if found:
        return found
    cands = sorted(Path.home().glob(".nvm/versions/node/*/bin/node"))
    v22 = [c for c in cands if "/v22." in str(c)]  # версия, на которой собирается ds_site
    pick = (v22 or cands or [None])[-1]
    return str(pick) if pick else None


def check_env(dry_run: bool = False) -> str | None:
    """Текст проблемы или None, если запуск возможен."""
    site = ds_site_dir()
    if not (site / "scripts" / "publish-pages.mjs").is_file():
        return (f"Не найден ds_site ({site}). Задайте DS_SITE_DIR; в docker "
                "ds_site монтируется томом (gar-deploy, ADR-0019).")
    if not (site / ".env.local").is_file():
        return f"Нет {site}/.env.local (GAR_URL, GAR_PUBLIC_API_KEY)."
    if not find_node():
        return "Не найден node (PATH или ~/.nvm)."
    if not dry_run and not shutil.which("gh"):
        return "Не найден gh (GitHub CLI) — нужен для публикации."
    return None


@dataclass
class Status:
    running: bool = False
    started_at: float | None = None
    dry_run: bool = False
    exit_code: int | None = None  # None — не запускалось / ещё идёт; -1 — процесс оборван
    log: str = ""
    counts: list[dict] = field(default_factory=list)
    url: str | None = None


def parse_counts(log: str) -> list[dict]:
    rows = []
    for name, n, skipped in _COUNT_RE.findall(log):
        try:
            sk = json.loads(skipped)
        except ValueError:
            sk = {}
        rows.append({"name": name, "published": int(n), "skipped": sk})
    return rows


def parse_url(log: str) -> str | None:
    m = _URL_RE.search(log)
    return m.group(1) if m else None


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def status(tail_lines: int = 300) -> Status:
    if not _state().is_file():
        return Status()
    try:
        st = json.loads(_state().read_text(encoding="utf-8"))
    except ValueError:
        return Status()
    log = _log().read_text(encoding="utf-8", errors="replace") if _log().is_file() else ""
    code: int | None = None
    if _exit().is_file():
        try:
            code = int(_exit().read_text().strip())
        except ValueError:
            code = -1
    running = code is None and _alive(int(st.get("pid", 0)))
    if code is None and not running:
        code = -1
    return Status(
        running=running, started_at=st.get("started_at"), dry_run=bool(st.get("dry_run")),
        exit_code=code, log="\n".join(log.splitlines()[-tail_lines:]),
        counts=parse_counts(log), url=parse_url(log),
    )


def start(dry_run: bool = False) -> None:
    """Запустить публикацию отдельным процессом. RuntimeError, если уже идёт или окружение не готово."""
    if status().running:
        raise RuntimeError("Пересборка уже выполняется")
    err = check_env(dry_run)
    if err:
        raise RuntimeError(err)
    node = find_node()
    site = ds_site_dir()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _exit().unlink(missing_ok=True)
    _log().write_text("", encoding="utf-8")
    argv = [node, "scripts/publish-pages.mjs"] + (["--dry-run"] if dry_run else [])
    cmd = " ".join(shlex.quote(a) for a in argv)
    sh = f"{cmd} > {shlex.quote(str(_log()))} 2>&1; echo $? > {shlex.quote(str(_exit()))}"
    env = os.environ.copy()
    env["PATH"] = str(Path(node).parent) + os.pathsep + env.get("PATH", "")
    if os.environ.get("DS_SITE_GAR_URL"):  # в docker GAR — по имени сервиса, а не localhost из .env.local
        env["GAR_URL"] = os.environ["DS_SITE_GAR_URL"]
    proc = subprocess.Popen(  # noqa: S603
        ["sh", "-c", sh], cwd=site, env=env, start_new_session=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _state().write_text(
        json.dumps({"pid": proc.pid, "started_at": time.time(), "dry_run": dry_run}),
        encoding="utf-8",
    )
