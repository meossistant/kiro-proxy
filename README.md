# Kiro Proxy Server

> **OpenAI & Anthropic Compatible FastAPI Proxy for AWS Kiro AI CLI**

`kiro-proxy` is a lightweight, high-performance proxy server built with **FastAPI** and managed via **uv**. It exposes the underlying AWS **Kiro AI CLI** (`kiro-cli`) as standard **OpenAI-compatible** (`/v1/chat/completions`, `/v1/models`) and **Anthropic-compatible** (`/v1/messages`) HTTP endpoints, supporting both full JSON responses and real-time Server-Sent Events (SSE) streaming.

---

## 🌟 Key Features

- **OpenAI Compatible**: Drop-in replacement for `/v1/chat/completions` and `/v1/models`. Works seamlessly with official OpenAI Python/Node SDKs, LangChain, LiteLLM, LibreChat, Open WebUI, and Cursor.
- **Anthropic Compatible**: Supports `/v1/messages` with native event types (`message_start`, `content_block_delta`, `message_delta`, `message_stop`). Works directly with Anthropic SDKs and clients.
- **Dynamic Model Discovery**: Queries `kiro-cli chat --list-models --format json` dynamically to extract all models enabled on your active Kiro subscription tier (Free or Paid/Pro).
- **Intelligent Auto-Routing & Fallbacks**:
  - **OpenAI API Default**: Defaults to `gpt-5.6-terra` (or best available general model in active tier).
  - **Anthropic API Default**: Defaults to `Sonnet` (`claude-sonnet-5.5` -> `claude-sonnet-5` -> `claude-sonnet-4.5`).
  - **Cross-Version Routing**: Automatically maps requested model versions (e.g. `gpt-4o`, `claude-3-7-sonnet`, `opus`, `haiku`) to the best matching model in your active tier.
- **True Real-Time Streaming**: Parses Kiro CLI's ACP `stream-json` events in real time and streams SSE chunks instantly.
- **Custom Generic Agent**: Automatically configures a dedicated generic profile in `~/.kiro/agents/generic.json` with a versatile system prompt and empty toolset for clean, direct completions.
- **Modern Python Tooling**: Uses [`uv`](https://docs.astral.sh/uv/) for blazing fast virtual environments and dependency management.
- **Optional API Key Security**: Protect your proxy with `API_KEY` or `KIRO_PROXY_API_KEY` via standard Bearer tokens or `x-api-key` headers.

---

## 🤖 Supported & Routed Models

The proxy dynamically adapts whether your account is on the **Free** tier or the **Paid (Pro)** tier:

| Model Family | Pro Tier (1M Context) | Free Tier | Auto-Routing Behavior |
| :--- | :--- | :--- | :--- |
| **OpenAI / General** | `gpt-5.6-terra`, `gpt-5.6-sol`, `gpt-5.6-luna` | `claude-sonnet-4.5`, `claude-haiku-4.5` | `gpt-4o`, `gpt-5*` -> `gpt-5.6-terra` (Pro) or `claude-sonnet` (Free) |
| **Reasoning / Pro** | `gpt-5.6-sol`, `claude-opus-5.5` | `claude-sonnet-4.5` | `o1`, `o3`, `sol` -> `gpt-5.6-sol` (Pro) or `claude-sonnet` (Free) |
| **Claude Sonnet** | `claude-sonnet-5.5`, `claude-sonnet-5` | `claude-sonnet-4.5` | `claude-sonnet*` -> highest available Sonnet version |
| **Claude Opus** | `claude-opus-5.5`, `claude-opus-5`, `claude-opus-4.8` | `claude-sonnet-4.5` | `claude-opus*` -> highest available Opus version |
| **Claude Haiku / Fast** | `gpt-5.6-luna`, `claude-haiku-4.5` | `claude-haiku-4.5` | `haiku`, `mini`, `flash` -> `claude-haiku-4.5` or `gpt-5.6-luna` |
| **DeepSeek** | `deepseek-3.2` | `deepseek-3.2` | `deepseek*` -> `deepseek-3.2` |
| **Qwen Coder** | `qwen3-coder-next` | `qwen3-coder-next` | `qwen*` -> `qwen3-coder-next` |
| **MiniMax** | `minimax-m2.5`, `minimax-m2.1` | `minimax-m2.5`, `minimax-m2.1` | `minimax*` -> `minimax-m2.5` |
| **GLM** | `glm-5` | `glm-5` | `glm*` -> `glm-5` |

---

## 🚀 Quick Start

> 🤖 **Automated Setup for AI Coding Agents**: See [AGENT_INSTALL.md](AGENT_INSTALL.md) for automated agent setup instructions and system PATH configuration.  
> 💻 **Claude Code CLI Setup**: See [CLAUDE_CODE_SETUP.md](CLAUDE_CODE_SETUP.md) for connecting Anthropic's Claude Code CLI.

### 1. Prerequisites

- Linux, macOS, or Windows with `python >= 3.12`
- [`uv`](https://github.com/astral-sh/uv) installed
- `kiro-cli` installed and authenticated (`kiro-cli login`)

### 2. Automated Installation

Run the one-line installer from inside the repository:

- **Linux / macOS**:
  ```bash
  ./scripts/install.sh
  ```
- **Windows (PowerShell)**:
  ```powershell
  .\scripts\install.ps1
  ```

This syncs dependencies with `uv` and installs `kiro-proxy` globally to your system PATH.

### 3. Manual Installation

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

# Automatically routes default or 'gpt-4o' to gpt-5.6-terra (or best available Sonnet)
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="none"  # or your KIRO_PROXY_API_KEY
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "Explain quantum computing in 2 sentences."}
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

# Automatically defaults to Claude Sonnet (claude-sonnet-5.5 / claude-sonnet-5 / claude-sonnet-4.5)
client = Anthropic(
    base_url="http://localhost:8000",
    api_key="none"
)

message = client.messages.create(
    model="claude-3-7-sonnet",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Hello Kiro!"}
    ]
)

print(message.content[0].text)
```

### 3. Using cURL (OpenAI Chat)

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

### 4. Using cURL (Anthropic Messages Streaming)

```bash
curl -N -X POST http://localhost:8000/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Count from 1 to 5"}],
    "stream": true
  }'
```

### 5. Using Claude Code CLI

Connect Anthropic's official `claude` command-line tool directly to `kiro-proxy`:

```bash
export ANTHROPIC_BASE_URL="http://localhost:8000"
export ANTHROPIC_API_KEY="none"

claude --model claude-sonnet-5.5
```

See the full [Claude Code Setup Guide](CLAUDE_CODE_SETUP.md) for shell aliases, Windows configuration, and troubleshooting.

---

## 🧪 Testing

Run unit and integration tests with `pytest`:

```bash
# Unit tests (including model resolution tests)
uv run pytest tests/test_proxy.py

# Full end-to-end integration tests (invokes kiro-cli)
uv run pytest tests/test_integration.py
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
