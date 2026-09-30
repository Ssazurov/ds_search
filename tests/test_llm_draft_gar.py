"""Тесты GAR resolver integration в llm_draft.py (ADR-015, issue #423)."""
import json
import pytest
from unittest.mock import Mock, patch

from src.news.llm_draft import LlmConfig, call_llm, generate_draft
from src.gar_ingest.client import GarPublishError


def _cfg(**overrides) -> LlmConfig:
    base = dict(
        provider="ollama",
        model="qwen2.5-coder:14b",
        endpoint="http://127.0.0.1:11434/api/chat",
        temperature=0.3,
        max_tokens=800,
        num_ctx=8192,
        prompt_template="{source_name}|{source_url}|{source_title}|{source_text}",
    )
    base.update(overrides)
    return LlmConfig(**base)


def test_call_llm_uses_gar_when_available():
    """GAR resolver доступен — call_llm использует client.generate()."""
    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client.generate.return_value = '{"title": "From GAR", "tags": ["test"]}'
    
    with patch("src.gar_ingest.client.GarIngestClient", return_value=mock_client):
        with patch("src.gar_ingest.client.load_settings"):
            result = call_llm("test prompt", _cfg(), purpose="news", input_chars=1000)
    
    assert result == '{"title": "From GAR", "tags": ["test"]}'
    mock_client.generate.assert_called_once_with("news", 1000, "test prompt")
    mock_client.__enter__.assert_called_once()
    mock_client.__exit__.assert_called_once()


def test_call_llm_fallback_on_gar_error():
    """GAR недоступен (GarPublishError) — fallback на локальный provider."""
    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client.generate.side_effect = GarPublishError("503 Service Unavailable")
    
    mock_ollama_response = {"message": {"content": '{"title": "Fallback", "tags": []}'}}
    
    with patch("src.gar_ingest.client.GarIngestClient", return_value=mock_client):
        with patch("src.gar_ingest.client.load_settings"):
            with patch("httpx.post") as mock_post:
                mock_post.return_value = Mock(status_code=200, json=lambda: mock_ollama_response)
                result = call_llm("test prompt", _cfg(), purpose="news", input_chars=1000)
    
    assert '{"title": "Fallback"' in result
    mock_client.generate.assert_called_once()
    mock_post.assert_called_once()


def test_call_llm_fallback_on_import_error():
    """GAR клиент не настроен (ImportError на load_settings) — fallback."""
    mock_ollama_response = {"message": {"content": '{"title": "No GAR", "tags": []}'}}
    
    with patch("src.gar_ingest.client.load_settings", side_effect=ImportError("no GAR")):
        with patch("httpx.post") as mock_post:
            mock_post.return_value = Mock(status_code=200, json=lambda: mock_ollama_response)
            result = call_llm("test prompt", _cfg(), purpose="news", input_chars=1000)
    
    assert '{"title": "No GAR"' in result


def test_generate_draft_passes_purpose_and_input_chars():
    """generate_draft(fmt='news') передаёт purpose='news' и input_chars."""
    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client.generate.return_value = json.dumps({
        "relevant": True,
        "title": "News draft",
        "summary": "Summary",
        "body_md": "Body",
        "tags": ["test"],
    })
    
    source = {
        "source_url": "https://example.com/news",
        "source_name": "Example",
        "title": "Source title",
        "text": "x" * 5000,  # 5000 символов
    }
    
    with patch("src.gar_ingest.client.GarIngestClient", return_value=mock_client):
        with patch("src.gar_ingest.client.load_settings"):
            item = generate_draft(source, _cfg(), fmt="news")
    
    assert item["title"] == "News draft"
    # input_chars — длина после clean_article_text (может отличаться от 5000)
    call_args = mock_client.generate.call_args
    assert call_args[0][0] == "news"  # purpose
    assert isinstance(call_args[0][1], int)  # input_chars
    assert call_args[0][1] > 0


def test_generate_digest_passes_purpose_digest():
    """generate_draft(fmt='digest') передаёт purpose='digest'."""
    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client.generate.return_value = json.dumps({
        "relevant": True,
        "title": "Digest draft",
        "summary": "Summary",
        "body_md": "Body text",
        "quotes": ["quote 1"],
        "tags": ["test"],
    })
    
    source = {
        "source_url": "https://example.com/article",
        "source_name": "Example",
        "title": "Long article",
        "text": "a" * 10000,
    }
    
    cfg = _cfg(
        prompt_template_digest="{source_name}|{source_text}",
        max_tokens_digest=1800,
        num_ctx_digest=8192,
    )
    
    with patch("src.gar_ingest.client.GarIngestClient", return_value=mock_client):
        with patch("src.gar_ingest.client.load_settings"):
            item = generate_draft(source, cfg, fmt="digest")
    
    assert item["title"] == "Digest draft"
    assert item["format"] == "digest"
    call_args = mock_client.generate.call_args
    assert call_args[0][0] == "digest"  # purpose
    assert call_args[0][1] > 5000  # input_chars после clean должен быть близок к 10000
