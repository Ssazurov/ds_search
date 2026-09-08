"""LLM-модуль черновика новости из источника (issue #46, ADR-003).

Провайдер/модель/эндпоинт/промпт вынесены в config/news_llm.yaml, не в код.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
import yaml

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


def load_llm_config(path: Path = CONFIG_PATH) -> LlmConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return LlmConfig(
        provider=data["provider"],
        model=data["model"],
        endpoint=data["endpoint"],
        temperature=float(data.get("temperature", 0.3)),
        max_tokens=int(data.get("max_tokens", 1500)),
        prompt_template=data["prompt_template"],
        timeout_s=float(data.get("timeout_s", 60.0)),
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
    api_key = os.environ.get("OPENAI_API_KEY", "")
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


_CALLERS = {
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


def generate_draft(source: dict, config: LlmConfig | None = None) -> dict:
    """source: {source_url, source_name, source_published_at, title, text}.
    Возвращает dict для db.insert_news_item (status=draft,
    requires_review=True, channels=[] — до ручного approve, issue #48)."""
    cfg = config or load_llm_config()
    prompt = build_prompt(cfg, source)
    raw = call_llm(prompt, cfg)
    parsed = parse_llm_json(raw)
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
