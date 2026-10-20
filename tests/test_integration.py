import pytest
from fastapi.testclient import TestClient
from kiro_proxy.main import app

client = TestClient(app)

def test_openai_chat_completions_non_stream():
    payload = {
        "model": "claude-haiku-4.5",
        "messages": [
            {"role": "user", "content": "What is 10 + 15? Answer only the number."}
        ],
        "stream": False
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert len(data["choices"]) > 0
    content = data["choices"][0]["message"]["content"]
    assert "25" in content

def test_openai_chat_completions_stream():
    payload = {
        "model": "claude-haiku-4.5",
        "messages": [
            {"role": "user", "content": "Say 'hello'"}
        ],
        "stream": True
    }
    with client.stream("POST", "/v1/chat/completions", json=payload) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        chunks = list(response.iter_lines())
        assert any("data: " in line for line in chunks)
        assert any("[DONE]" in line for line in chunks)

def test_anthropic_messages_non_stream():
    payload = {
        "model": "claude-haiku-4.5",
        "messages": [
            {"role": "user", "content": "What is 20 + 22? Answer only the number."}
        ],
        "stream": False
    }
    response = client.post("/v1/messages", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "message"
    assert data["role"] == "assistant"
    assert len(data["content"]) > 0
    assert "42" in data["content"][0]["text"]

def test_anthropic_messages_stream():
    payload = {
        "model": "claude-haiku-4.5",
        "messages": [
            {"role": "user", "content": "Say 'kiro'"}
        ],
        "stream": True
    }
    with client.stream("POST", "/v1/messages", json=payload) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        lines = list(response.iter_lines())
        assert any("event: message_start" in line for line in lines)
        assert any("event: content_block_delta" in line for line in lines)
        assert any("event: message_stop" in line for line in lines)
