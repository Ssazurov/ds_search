# CURRENT_STATUS archive: 2026-09-30 (part 2)

Вынесено при подготовке записи по issue #432.

## 2026-09-30 — ds_search#420: пересказ (digest), модель/промпт/overlap
- `news_items`: колонки `format`, `quotes`, `overlap_max_run`, `overlap_ratio` (миграция в `db.init_db`).
- `llm_draft.generate_draft(..., fmt="digest", autoclassify=...)`, `prompt_template_digest` + `max_tokens_digest`/`num_ctx_digest` в `news_llm.yaml`.
- `src/news/overlap.py`: серия ≥8 слов / доля 5-грамм >15% (цитаты исключены), лимиты цитат (≤2, ≤25 слов).
- `publish`: `doc_type=digest`, блок «Полный текст — на сайте источника», без http(s)-URL публикация запрещена.
- ADR-0024 (ds/docs/adr). Требуется активная опция `doc_type=digest` в GAR (вручную).
- Container ds-search rebuilt, UI без изменений (UI — #421). PR #424, Closes #420.

## 2026-09-30: GAR resolver integration for news/digest generation (#423)

**Implemented**: GAR (Generic AI Router) resolver/generate endpoint integration into news/digest LLM pipeline.

### Changes

**ADR-015** (`docs/adr/ADR-015-gar-resolver-news-digest.md`):
- GAR resolver selects provider/model based on `purpose` (news|digest) and `input_chars` (content size)
- Local `news_llm.yaml` config becomes fallback only when GAR unavailable

**Code**:
- `src/gar_ingest/client.py`: Added `generate(purpose, input_chars, prompt)` method calling `POST /v1/generate`
- `src/news/llm_draft.py`: 
  - `call_llm()` tries GAR first via `client.generate()`, falls back to local provider on error/unavailability
  - `generate_draft()` passes `purpose="news"` + `input_chars` to `call_llm()`
  - `_generate_digest()` passes `purpose="digest"` + `input_chars`
- `config/news_llm.yaml`: Updated comment explaining fallback behavior

**Tests**:
- `tests/test_llm_draft_gar.py`: 5 new tests (GAR integration + fallback scenarios)
- `tests/test_llm_draft.py`: Updated mocks for new `call_llm` signature
- All 12 tests pass

### Verification

- Commit: 7f2d5bd
- Tests: `pytest tests/test_llm_draft.py tests/test_llm_draft_gar.py -v` → 12 passed
- Container: `ds-search` rebuilt, new code verified in image
- Issue: https://github.com/Ssazurov/ds_search/issues/423 closed

### Impact

News/digest generation now routes through GAR for centralized model selection. Local provider/model in `news_llm.yaml` used only when GAR unavailable (network error, not configured, etc).
