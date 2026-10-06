"""Пакетная перекачка статей из источника с заменой в GAR (ds_search#457).

Повторяет кнопку «Перезагрузить из источника» (documents_tab) без Streamlit:
download_single -> валидация -> бэкап старого контента -> замена файла рядом
с sidecar -> POST /reload_by_gar_id (ds_ingestion). Идемпотентно: state-файл.
Старый контент не трогается, пока новый не скачан и не прошёл валидацию.

CLI: python -m src.recrawl.batch --limit 3 [--domain downsideup.org] [--retry-failed]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

import httpx

from src.tz import now_msk
from src.discovery.download import DEFAULT_DATA_ROOT, download_single

RAW_ROOT = Path(DEFAULT_DATA_ROOT)
STATE_PATH = RAW_ROOT.parent / "recrawl_state.json"
BACKUP_ROOT = RAW_ROOT.parent / "recrawl_backup"
REPORT_PATH = RAW_ROOT.parent / "recrawl_report.md"

DS_INGESTION_URL = os.environ.get("DS_INGESTION_URL", "http://127.0.0.1:8200")
DOWNLOAD_TIMEOUT_S = 60
PAUSE_S = 4.0        # /reload: 20/мин глобально, 1/60с на документ (ADR-0008)
MIN_NEW_CHARS = 300  # валидация: короче — считаем неудачной скачкой


def load_state() -> dict:
    if STATE_PATH.is_file():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    tmp = STATE_PATH.with_name(STATE_PATH.name + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, STATE_PATH)


def scan_candidates(domain: str) -> list[dict]:
    """Документы из GAR (есть gar_document_id) с source_domain, содержащим domain."""
    rows = []
    for jp in sorted(RAW_ROOT.glob("*/*.json")):
        try:
            meta = json.loads(jp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        gid = meta.get("gar_document_id")
        url = meta.get("source_url") or meta.get("canonical_url")
        if not gid or not url or domain not in (meta.get("source_domain") or url):
            continue
        rows.append({"doc_id": jp.stem, "jp": jp, "gar_id": gid, "url": url,
                     "title": meta.get("title") or jp.stem})
    return rows


def _content_file(jp: Path) -> Path | None:
    for p in sorted(jp.parent.glob(jp.stem + ".*")):
        if p.suffix != ".json" and not p.name.endswith(".tmp"):
            return p
    return None


def _read_text(p: Path | None) -> str:
    if not p or not p.is_file():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _download(url: str) -> dict:
    async def _dl(tmp_root: Path):
        return await asyncio.wait_for(
            download_single({"url": url}, data_root=tmp_root, dest_dir="r", filename="r"),
            timeout=DOWNLOAD_TIMEOUT_S,
        )
    tmp = tempfile.mkdtemp()
    try:
        new = asyncio.run(_dl(Path(tmp)))
        path = Path(new["content_path"])
        return {"tmp": tmp, "path": path, "text": _read_text(path)}
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


DOC_TYPE = "article"


def _reload(gar_id: str) -> dict:
    headers = {}
    if os.environ.get("DS_INGESTION_API_KEY"):
        headers["X-Ingestion-Key"] = os.environ["DS_INGESTION_API_KEY"]
    resp = httpx.post(f"{DS_INGESTION_URL}/reload_by_gar_id",
                      json={"gar_document_id": gar_id, "recrawl": False},
                      headers=headers, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"reload {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def ensure_doc_type(jp: Path) -> bool:
    """Пустой doc_type в sidecar -> article (иначе статья не видна на сайте).
    Reload подтягивает метаданные из sidecar в GAR. True, если изменили."""
    meta = json.loads(jp.read_text(encoding="utf-8"))
    if meta.get("doc_type"):
        return False
    meta["doc_type"] = DOC_TYPE
    jp.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def fix_doc_types(domain: str = "downsideup.org") -> list[dict]:
    """Проставить doc_type=article уже перекачанным (done) документам без типа."""
    state, out = load_state(), []
    for row in scan_candidates(domain):
        if state.get(row["doc_id"], {}).get("status") != "done" or not ensure_doc_type(row["jp"]):
            continue
        try:
            rep = _reload(row["gar_id"])
            out.append({"title": row["title"], "ok": True, "changed": rep.get("changed_fields")})
        except Exception as exc:  # noqa: BLE001
            out.append({"title": row["title"], "ok": False, "error": str(exc)})
        time.sleep(PAUSE_S)
    return out


def process_one(row: dict) -> dict:
    """Возвращает запись для state/отчёта. Исключения -> status=failed, старое цело."""
    jp: Path = row["jp"]
    old_file = _content_file(jp)
    old_text = _read_text(old_file)
    rec = {"gar_id": row["gar_id"], "url": row["url"], "title": row["title"],
           "old_len": len(old_text), "old_preview": old_text[:300],
           "ts": datetime.now().isoformat(timespec="seconds")}
    dl = None
    try:
        dl = _download(row["url"])
        new_text = dl["text"]
        rec["new_len"] = len(new_text)
        rec["new_preview"] = new_text[:300]
        if len(new_text.strip()) < MIN_NEW_CHARS:
            raise ValueError(f"новый текст слишком короткий ({len(new_text.strip())} симв.)")
        if old_file is None or old_file.suffix != dl["path"].suffix:
            raise ValueError(f"тип контента: было {old_file.suffix if old_file else None}, стало {dl['path'].suffix}")
        BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
        backup = BACKUP_ROOT / f"{row['doc_id']}{old_file.suffix}"
        shutil.copyfile(old_file, backup)
        tmp_dst = old_file.with_name(old_file.name + ".tmp")
        shutil.copyfile(dl["path"], tmp_dst)
        os.replace(tmp_dst, old_file)
        ensure_doc_type(jp)
        try:
            rep = _reload(row["gar_id"])
        except Exception:
            shutil.copyfile(backup, old_file)  # файл и GAR не расходятся
            raise
        rec.update(status="done", content_replaced=rep.get("content_replaced"),
                   changed_fields=rep.get("changed_fields"))
    except Exception as exc:  # noqa: BLE001 — батч не должен падать на одной статье
        rec.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        if dl:
            shutil.rmtree(dl["tmp"], ignore_errors=True)
    return rec


def write_report(recs: list[dict]) -> None:
    lines = [f"# Перекачка {now_msk():%d.%m.%Y %H:%M}", ""]
    for r in recs:
        lines += [f"## {r['title']}", f"- {r['url']}", f"- gar_id: {r['gar_id']}",
                  f"- статус: **{r['status']}**" + (f" — {r['error']}" if r.get("error") else ""),
                  f"- длина до/после: {r.get('old_len')} → {r.get('new_len')}",
                  f"- было: `{(r.get('old_preview') or '')[:200]!r}`",
                  f"- стало: `{(r.get('new_preview') or '')[:200]!r}`", ""]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def run_batch(limit: int, domain: str = "downsideup.org", retry_failed: bool = False,
              progress=None) -> dict:
    """Обрабатывает до `limit` ещё не done документов. Возвращает сводку."""
    state = load_state()
    cands = scan_candidates(domain)
    todo = [r for r in cands
            if state.get(r["doc_id"], {}).get("status") != "done"
            and (retry_failed or state.get(r["doc_id"], {}).get("status") != "failed")]
    batch = todo[:limit]
    recs = []
    for i, row in enumerate(batch):
        if progress:
            progress(i, len(batch), row["title"])
        rec = process_one(row)
        state[row["doc_id"]] = rec
        save_state(state)
        recs.append(rec)
        if i < len(batch) - 1:
            time.sleep(PAUSE_S)
    if recs:
        write_report(recs)
    done = sum(1 for r in cands if state.get(r["doc_id"], {}).get("status") == "done")
    return {"processed": recs, "done_total": done, "total": len(cands),
            "failed": sum(1 for r in recs if r["status"] == "failed"), "report": str(REPORT_PATH)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--domain", default="downsideup.org")
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--fix-doc-type", action="store_true")
    a = ap.parse_args()
    if a.fix_doc_type:
        for r in fix_doc_types(a.domain):
            print(r)
        return
    out = run_batch(a.limit, a.domain, a.retry_failed,
                    progress=lambda i, n, t: print(f"[{i+1}/{n}] {t}", flush=True))
    for r in out["processed"]:
        print(r["status"], r.get("old_len"), "->", r.get("new_len"), r["url"], r.get("error", ""))
    print(f"done {out['done_total']}/{out['total']}, failed in batch: {out['failed']}, report: {out['report']}")


if __name__ == "__main__":
    main()
