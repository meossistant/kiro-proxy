import pytest
from fastapi.testclient import TestClient
from kiro_proxy.main import app
from kiro_proxy.registry import registry
from kiro_proxy.formatters import format_openai_messages, format_anthropic_messages
from kiro_proxy.models import ChatMessage, AnthropicMessage

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "kiro-proxy"
    assert "available_models" in data

def test_list_models():
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) > 0
    model_ids = [m["id"] for m in data["data"]]
    assert "auto" in model_ids

@pytest.mark.asyncio
async def test_resolve_model_defaults():
    # Anthropic default must resolve to Sonnet
    anthropic_default = await registry.resolve_model(None, api_flavor="anthropic")
    assert "sonnet" in anthropic_default

    # OpenAI default must resolve to Terra (or fallback Sonnet if in Free tier)
    openai_default = await registry.resolve_model(None, api_flavor="openai")
    assert any(k in openai_default for k in ["terra", "sonnet", "auto"])

@pytest.mark.asyncio
async def test_resolve_model_auto_routing():
    # Haiku requests
    haiku_res = await registry.resolve_model("claude-haiku-4.5", api_flavor="anthropic")
    assert "haiku" in haiku_res or "luna" in haiku_res

    # DeepSeek requests
    deepseek_res = await registry.resolve_model("deepseek-v3", api_flavor="openai")
    assert "deepseek" in deepseek_res

    # Qwen requests
    qwen_res = await registry.resolve_model("qwen-coder", api_flavor="openai")
    assert "qwen" in qwen_res

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
