import pytest
from fastapi.testclient import TestClient
from kiro_proxy.main import app
from kiro_proxy.formatters import map_model_name, format_openai_messages, format_anthropic_messages
from kiro_proxy.models import ChatMessage, AnthropicMessage

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "kiro-proxy"

def test_list_models():
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) > 0
    model_ids = [m["id"] for m in data["data"]]
    assert "claude-sonnet-4.5" in model_ids
    assert "auto" in model_ids

def test_map_model_name():
    assert map_model_name("claude-3-7-sonnet") == "claude-sonnet-4.5"
    assert map_model_name("gpt-4o") == "claude-sonnet-4.5"
    assert map_model_name("gpt-4o-mini") == "claude-haiku-4.5"
    assert map_model_name("deepseek-chat") == "deepseek-3.2"
    assert map_model_name("qwen-max") == "qwen3-coder-next"
    assert map_model_name("auto") == "auto"

def test_format_openai_messages():
    messages = [
        ChatMessage(role="system", content="You are a poet."),
        ChatMessage(role="user", content="Write a haiku about rain.")
    ]
    prompt = format_openai_messages(messages)
    assert "[System Instructions]" in prompt
    assert "You are a poet." in prompt
    assert "Write a haiku about rain." in prompt

def test_format_anthropic_messages():
    messages = [
        AnthropicMessage(role="user", content="Hello Kiro!")
    ]
    prompt = format_anthropic_messages(messages, system="Be brief.")
    assert "[System Instructions]" in prompt
    assert "Be brief." in prompt
    assert "Hello Kiro!" in prompt
