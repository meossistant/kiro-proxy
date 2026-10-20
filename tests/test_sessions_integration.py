import pytest
from fastapi.testclient import TestClient
from kiro_proxy.main import app

client = TestClient(app)

def test_multiturn_anthropic_session_continuation():
    session_id = "test-anthropic-e2e-99"
    headers = {"x-session-id": session_id}

    # Turn 1: State favorite fruit
    turn1_payload = {
        "model": "claude-haiku-4.5",
        "system": "You are a helpful assistant.",
        "messages": [
            {"role": "user", "content": "My favorite fruit is Dragonfruit. Please confirm you noted it."}
        ],
        "stream": False
    }
    res1 = client.post("/v1/messages", json=turn1_payload, headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    reply1 = data1["content"][0]["text"]
    assert len(reply1) > 0

    # Turn 2: Ask for favorite fruit, sending full message history as standard Anthropic clients do
    turn2_payload = {
        "model": "claude-haiku-4.5",
        "system": "You are a helpful assistant.",
        "messages": [
            {"role": "user", "content": "My favorite fruit is Dragonfruit. Please confirm you noted it."},
            {"role": "assistant", "content": reply1},
            {"role": "user", "content": "What is my favorite fruit? Reply with only the name of the fruit."}
        ],
        "stream": False
    }
    res2 = client.post("/v1/messages", json=turn2_payload, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    reply2 = data2["content"][0]["text"]
    assert "Dragonfruit" in reply2

    # Check /v1/sessions endpoint verifies active session
    sessions_res = client.get("/v1/sessions")
    assert sessions_res.status_code == 200
    sessions_data = sessions_res.json()
    assert sessions_data["active_sessions_count"] >= 1
    found = any(s["client_key"] == f"hdr:{session_id}" for s in sessions_data["sessions"])
    assert found is True

def test_multiturn_openai_session_continuation():
    session_id = "test-openai-e2e-77"
    headers = {"x-session-id": session_id}

    # Turn 1
    turn1_payload = {
        "model": "claude-haiku-4.5",
        "messages": [
            {"role": "user", "content": "Remember the word: SUNFLOWER_33."}
        ],
        "stream": False
    }
    res1 = client.post("/v1/chat/completions", json=turn1_payload, headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    reply1 = data1["choices"][0]["message"]["content"]

    # Turn 2: Query word
    turn2_payload = {
        "model": "claude-haiku-4.5",
        "messages": [
            {"role": "user", "content": "Remember the word: SUNFLOWER_33."},
            {"role": "assistant", "content": reply1},
            {"role": "user", "content": "What was the word? Answer only the word."}
        ],
        "stream": False
    }
    res2 = client.post("/v1/chat/completions", json=turn2_payload, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    reply2 = data2["choices"][0]["message"]["content"]
    assert "SUNFLOWER_33" in reply2
