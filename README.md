# Kiro Proxy Server

> **OpenAI & Anthropic Compatible FastAPI Proxy for AWS Kiro AI CLI**

`kiro-proxy` is a lightweight, high-performance proxy server built with **FastAPI** and managed via **uv**. It exposes the underlying AWS **Kiro AI CLI** (`kiro-cli`) as standard **OpenAI-compatible** (`/v1/chat/completions`, `/v1/models`) and **Anthropic-compatible** (`/v1/messages`) HTTP endpoints, supporting both full JSON responses and real-time Server-Sent Events (SSE) streaming.

It comes with an automatic **custom generic agent** to ensure clean, versatile assistant completions without assuming specific terminal or IDE constraints.

---

## 🌟 Key Features

- **OpenAI Compatible**: Drop-in replacement for `/v1/chat/completions` and `/v1/models`. Works seamlessly with the official OpenAI Python/Node SDKs, LangChain, LiteLLM, LibreChat, Open WebUI, and Cursor.
- **Anthropic Compatible**: Supports `/v1/messages` with native event types (`message_start`, `content_block_delta`, `message_delta`, etc.). Works directly with Anthropic SDKs and clients.
- **True Real-Time Streaming**: Parses Kiro CLI's ACP stream-json events in real time and streams SSE chunks instantly.
- **Custom Generic Agent**: Automatically sets up a dedicated generic profile in `~/.kiro/agents/generic.json` with a general-purpose prompt, disabling unnecessary terminal tool calls for clean LLM outputs.
- **Dynamic Model Mapping**: Maps standard model identifiers (`gpt-4o`, `claude-3-7-sonnet`, `claude-3-5-haiku`, etc.) to Kiro's supported backend models (`claude-sonnet-4.5`, `claude-haiku-4.5`, `deepseek-3.2`, etc.).
- **Modern Python Tooling**: Uses [`uv`](https://docs.astral.sh/uv/) for blazing fast virtual environments and dependency management.
- **Optional API Key Security**: Protect your proxy with `API_KEY` or `KIRO_PROXY_API_KEY` via standard Bearer tokens or `x-api-key` headers.

---

## 🤖 Supported Models

| Requested Model | Routed Kiro Model | Description |
| :--- | :--- | :--- |
| `auto` | `auto` | Kiro automatically picks the optimal model |
| `claude-sonnet-4.5` / `gpt-4o` | `claude-sonnet-4.5` | Top-tier deep reasoning & coding |
| `claude-haiku-4.5` / `gpt-4o-mini` | `claude-haiku-4.5` | Fast & lightweight model |
| `deepseek-3.2` | `deepseek-3.2` | DeepSeek V3.2 preview |
| `qwen3-coder-next` | `qwen3-coder-next` | Dedicated coding model |
| `minimax-m2.5` | `minimax-m2.5` | MiniMax M2.5 model |
| `glm-5` | `glm-5` | GLM-5 model |

---

## 🚀 Quick Start

### 1. Prerequisites

- Linux or macOS with `python >= 3.12`
- [`uv`](https://github.com/astral-sh/uv) installed
- `kiro-cli` installed and authenticated (`kiro-cli login`)

### 2. Installation

Clone this repository and sync dependencies:

```bash
git clone https://github.com/meossistant/kiro-proxy.git
cd kiro-proxy
uv sync
```

### 3. Run the Proxy Server

```bash
# Start server on 0.0.0.0:8000
uv run kiro-proxy

# Or using uvicorn directly
uv run uvicorn kiro_proxy.main:app --host 0.0.0.0 --port 8000
```

---

## ⚙️ Configuration

You can configure `kiro-proxy` using environment variables or a `.env` file:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `HOST` | `0.0.0.0` | Host interface to bind |
| `PORT` | `8000` | Port to listen on |
| `KIRO_CLI_PATH` | `~/.local/bin/kiro-cli` | Path to `kiro-cli` binary |
| `KIRO_AGENT` | `generic` | Name of custom agent configuration |
| `API_KEY` | *(None)* | Optional API key to authenticate requests |
| `DEFAULT_MODEL`| `auto` | Fallback model if not specified |

---

## 📖 Usage Examples

### 1. Using OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="none"  # or your KIRO_PROXY_API_KEY
)

# Streaming
response = client.chat.completions.create(
    model="claude-sonnet-4.5",
    messages=[
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": "Write a quicksort implementation in Python."}
    ],
    stream=True
)

for chunk in response:
    content = chunk.choices[0].delta.content or ""
    print(content, end="", flush=True)
```

### 2. Using Anthropic Python SDK

```python
from anthropic import Anthropic

client = Anthropic(
    base_url="http://localhost:8000",
    api_key="none"
)

message = client.messages.create(
    model="claude-haiku-4.5",
    max_tokens=1024,
    system="Answer concisely.",
    messages=[
        {"role": "user", "content": "What is WebAssembly?"}
    ]
)

print(message.content[0].text)
```

### 3. Using cURL (OpenAI Chat)

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

### 4. Using cURL (Anthropic Messages Streaming)

```bash
curl -N -X POST http://localhost:8000/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-haiku-4.5",
    "messages": [{"role": "user", "content": "Count from 1 to 5"}],
    "stream": true
  }'
```

---

## 🧪 Testing

Run unit and integration tests with `pytest`:

```bash
# Unit tests
uv run pytest tests/test_proxy.py

# Full integration tests (invokes kiro-cli)
uv run pytest tests/test_integration.py
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
