import pytest
from fastapi.testclient import TestClient
from kiro_proxy.main import app
from kiro_proxy.sessions import SessionManager
from kiro_proxy.formatters import format_anthropic_messages, format_openai_messages
from kiro_proxy.models import AnthropicMessage, ChatMessage

client = TestClient(app)

def test_extract_client_key():
    mgr = SessionManager()
    
    # 1. From Claude Code session header
    key1 = mgr.extract_client_key(headers={"x-claude-code-session-id": "test-uuid-1234"})
    assert key1 == "hdr:test-uuid-1234"

    # 2. From custom session header
    key2 = mgr.extract_client_key(headers={"x-session-id": "custom-sess-5678"})
    assert key2 == "hdr:custom-sess-5678"

    # 3. From user field
    key3 = mgr.extract_client_key(headers={}, body_user="user_alice")
    assert key3 == "user:user_alice"

    # 4. From message prefix hash fallback
    msgs = [AnthropicMessage(role="user", content="Initial prompt")]
    key4 = mgr.extract_client_key(headers={}, messages=msgs, system="system prompt")
    assert key4.startswith("hash:")

def test_session_lifecycle_and_delta():
    mgr = SessionManager(ttl_seconds=100)
    client_key = "test-client-1"

    msgs_turn1 = [
        AnthropicMessage(role="user", content="Turn 1 message")
    ]

    # Turn 1: brand new
    resume_id, delta, is_cont = mgr.prepare_turn(client_key, msgs_turn1, "claude-sonnet-4.5")
    assert resume_id is None
    assert len(delta) == 1
    assert is_cont is False

    # Simulate turn 1 completion
    mgr.record_session(client_key, "kiro-sess-abc", len(msgs_turn1), "claude-sonnet-4.5")

    # Turn 2: user sends history + assistant + new message (3 messages total)
    msgs_turn2 = [
        AnthropicMessage(role="user", content="Turn 1 message"),
        AnthropicMessage(role="assistant", content="Turn 1 reply"),
        AnthropicMessage(role="user", content="Turn 2 question")
    ]

    resume_id, delta, is_cont = mgr.prepare_turn(client_key, msgs_turn2, "claude-sonnet-4.5")
    assert resume_id == "kiro-sess-abc"
    assert is_cont is True
    # Delta should contain only the 2 new messages (assistant reply + user question)
    assert len(delta) == 2
    assert delta[-1].content == "Turn 2 question"

    # Turn 3: user branches/resets history to 1 message
    msgs_reset = [AnthropicMessage(role="user", content="Brand new branch")]
    resume_id, delta, is_cont = mgr.prepare_turn(client_key, msgs_reset, "claude-sonnet-4.5")
    assert resume_id is None
    assert is_cont is False
    assert len(delta) == 1

def test_differential_prompt_formatting():
    delta = [
        AnthropicMessage(role="user", content="What is the answer?")
    ]
    prompt = format_anthropic_messages(delta, system="Long system instructions", is_continuation=True)
    # When is_continuation=True, system instructions must NOT be repeated
    assert "[System Instructions]" not in prompt
    assert "Long system instructions" not in prompt
    assert "What is the answer?" in prompt

    openai_delta = [
        ChatMessage(role="user", content="New query")
    ]
    openai_prompt = format_openai_messages(openai_delta, is_continuation=True)
    assert "[System Instructions]" not in openai_prompt
    assert "New query" in openai_prompt

def test_sessions_endpoint():
    res = client.get("/v1/sessions")
    assert res.status_code == 200
    data = res.json()
    assert "active_sessions_count" in data
    assert "sessions" in data
