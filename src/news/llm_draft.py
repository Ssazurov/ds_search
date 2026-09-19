"""LLM-модуль черновика новости из источника (issue #46, ADR-003).

Провайдер/модель/эндпоинт/промпт вынесены в config/news_llm.yaml, не в код.
Эндпоинт/модель можно переопределить env NEWS_LLM_ENDPOINT / NEWS_LLM_MODEL
(в docker Ollama на хосте: http://host.docker.internal:11434/api/chat, issue #208).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
import yaml

from .text_clean import clean_article_text

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "news_llm.yaml"


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    model: str
    endpoint: str
    temperature: float
    max_tokens: int
    prompt_template: str
    timeout_s: float = 60.0
    api_key: str = ""
    num_ctx: int = 8192  # только provider=ollama


def load_llm_config(path: Path = CONFIG_PATH) -> LlmConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return LlmConfig(
        provider=data["provider"],
        model=os.environ.get("NEWS_LLM_MODEL") or data["model"],
        endpoint=os.environ.get("NEWS_LLM_ENDPOINT") or data["endpoint"],
        temperature=float(data.get("temperature", 0.3)),
        max_tokens=int(data.get("max_tokens", 1500)),
        prompt_template=data.get("prompt_template", ""),
        timeout_s=float(data.get("timeout_s", 60.0)),
        api_key=str(data.get("api_key", "")),
        num_ctx=int(data.get("num_ctx", 8192)),
    )


def build_prompt(config: LlmConfig, source: dict) -> str:
    return config.prompt_template.format(
        source_name=source.get("source_name", ""),
        source_url=source.get("source_url", ""),
        source_title=source.get("title", ""),
        source_text=source.get("text", ""),
    )


def _call_anthropic(prompt: str, config: LlmConfig) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY не задан")
    resp = httpx.post(
        config.endpoint,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=config.timeout_s,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(b["text"] for b in data["content"] if b.get("type") == "text")


def _call_openai_compatible(prompt: str, config: LlmConfig) -> str:
    api_key = config.api_key or os.environ.get("OPENAI_API_KEY", "")
    headers = {"content-type": "application/json"}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    resp = httpx.post(
        config.endpoint,
        headers=headers,
        json={
            "model": config.model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=config.timeout_s,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _call_ollama(prompt: str, config: LlmConfig) -> str:
    """Нативный /api/chat: в отличие от /v1/chat/completions принимает
    options.num_ctx (по умолчанию Ollama режет вход до 4096 токенов, issue #208)."""
    resp = httpx.post(
        config.endpoint,
        json={
            "model": config.model,
            "stream": False,
            "format": "json",
            "messages": [{"role": "user", "content": prompt}],
            "options": {
                "temperature": config.temperature,
                "num_predict": config.max_tokens,
                "num_ctx": config.num_ctx,
            },
        },
        timeout=config.timeout_s,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


_CALLERS = {
    "ollama": _call_ollama,
    "anthropic": _call_anthropic,
    "openai_compatible": _call_openai_compatible,
}


def call_llm(prompt: str, config: LlmConfig) -> str:
    caller = _CALLERS.get(config.provider)
    if caller is None:
        raise ValueError(f"неизвестный provider: {config.provider}")
    return caller(prompt, config)


def parse_llm_json(raw: str) -> dict:
    """Снять markdown-обрамление ```json ... ``` (если есть) и распарсить JSON."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


class NotRelevantError(Exception):
    """LLM оценил источник как не относящийся к теме СД/РАС (issue #180)."""


def generate_draft(source: dict, config: LlmConfig | None = None) -> dict:
    """source: {source_url, source_name, source_published_at, title, text}.
    Возвращает dict для db.insert_news_item (status=draft,
    requires_review=True, channels=[] — до ручного approve, issue #48).
    Бросает NotRelevantError, если LLM пометил источник как нерелевантный
    (issue #180: фильтр после SearchChain — например pravmir.ru отдаёт
    RSS без тематического фильтра)."""
    cfg = config or load_llm_config()
    # шапка/подвал страницы не нужны модели и съедают контекст (issue #208)
    source = {**source, "text": clean_article_text(source.get("text", ""))}
    prompt = build_prompt(cfg, source)
    raw = call_llm(prompt, cfg)
    parsed = parse_llm_json(raw)
    if parsed.get("relevant") is False:
        raise NotRelevantError(parsed.get("relevance_reason", "нерелевантно"))
    return {
        "source_url": source["source_url"],
        "source_name": source.get("source_name"),
        "source_published_at": source.get("source_published_at"),
        "title": parsed["title"],
        "summary": parsed.get("summary"),
        "body_md": parsed.get("body_md"),
        "direction": "news",
        "tags": parsed.get("tags", []),
        "requires_review": True,
        "status": "draft",
        "channels": [],
    }
