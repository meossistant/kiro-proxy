#!/usr/bin/env python3
"""
Example usage of kiro-proxy using standard HTTP requests.
Demonstrates:
  1. OpenAI-compatible /v1/chat/completions (streaming & non-streaming)
  2. Anthropic-compatible /v1/messages (streaming & non-streaming)
"""

import json
import httpx

BASE_URL = "http://localhost:8000"

def test_openai_non_stream():
    print("\n--- 1. OpenAI Compatible Non-Streaming ---")
    payload = {
        "model": "claude-haiku-4.5",
        "messages": [
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "What is the capital of Vietnam?"}
        ],
        "stream": False
    }
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        res = client.post("/v1/chat/completions", json=payload)
        print("Status:", res.status_code)
        data = res.json()
        print("Response:", data["choices"][0]["message"]["content"])

def test_openai_stream():
    print("\n--- 2. OpenAI Compatible Streaming (SSE) ---")
    payload = {
        "model": "claude-haiku-4.5",
        "messages": [
            {"role": "user", "content": "Count from 1 to 5."}
        ],
        "stream": True
    }
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        with client.stream("POST", "/v1/chat/completions", json=payload) as response:
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        print("\n[DONE]")
                        break
                    chunk = json.loads(data_str)
                    content = chunk["choices"][0]["delta"].get("content", "")
                    print(content, end="", flush=True)

def test_anthropic_non_stream():
    print("\n\n--- 3. Anthropic Compatible Non-Streaming ---")
    payload = {
        "model": "claude-haiku-4.5",
        "system": "Answer in one sentence.",
        "messages": [
            {"role": "user", "content": "Explain what an API is."}
        ],
        "stream": False
    }
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        res = client.post("/v1/messages", json=payload)
        print("Status:", res.status_code)
        data = res.json()
        print("Response:", data["content"][0]["text"])

def test_anthropic_stream():
    print("\n--- 4. Anthropic Compatible Streaming (SSE) ---")
    payload = {
        "model": "claude-haiku-4.5",
        "messages": [
            {"role": "user", "content": "Write a 2-line greeting."}
        ],
        "stream": True
    }
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        with client.stream("POST", "/v1/messages", json=payload) as response:
            for line in response.iter_lines():
                if line.startswith("data: "):
                    event_data = json.loads(line[6:].strip())
                    if event_data.get("type") == "content_block_delta":
                        print(event_data["delta"].get("text", ""), end="", flush=True)
    print("\n")

if __name__ == "__main__":
    test_openai_non_stream()
    test_openai_stream()
    test_anthropic_non_stream()
    test_anthropic_stream()
