# Connecting Claude Code CLI to Kiro Proxy

This guide explains how to connect Anthropic's official **Claude Code CLI** (`claude`) to **kiro-proxy**, allowing you to use AWS Kiro AI's Claude Sonnet models directly inside your terminal with full streaming and agentic capabilities.

---

## 🎯 Architecture Overview

```text
┌────────────────┐      ANTHROPIC_BASE_URL="http://localhost:8000"      ┌──────────────┐      stream-json      ┌──────────────┐
│  Claude Code   │ ───────────────────────────────────────────────────> │  kiro-proxy  │ ────────────────────> │   kiro-cli   │
│     (CLI)      │ <─────────────────────────────────────────────────── │ (FastAPI)    │ <──────────────────── │ (AWS Kiro AI)│
└────────────────┘         SSE Stream /v1/messages                      └──────────────┘                       └──────────────┘
```

1. **Claude Code CLI** sends standard Anthropic `/v1/messages` requests, including the `x-claude-code-session-id` header.
2. **kiro-proxy** intercepts the session ID. On turn 1, it passes the agent prompt and receives a Kiro session ID. On subsequent turns (`--resume` or interactive mode), it sends **only the new delta messages** using `kiro-cli chat --resume-id <SESSION_ID>`.
3. **AWS Kiro AI** automatically reuses the cached prompt tokens, cutting payload transmission by over 99% and accelerating response latency by up to 7x.
4. Response tokens are converted to Anthropic Server-Sent Events (SSE) and streamed back in real-time.

---

## ⚡ Quick Start

### 1. Ensure `kiro-proxy` is Running

Start the proxy server in a terminal window or in the background:

```bash
# Using uv directly inside repo:
uv run kiro-proxy

# Or globally if installed to PATH:
kiro-proxy
```

Verify it is running:
```bash
curl http://localhost:8000/health
# Returns: {"status": "healthy", "kiro_auth": true, ...}
```

---

### 2. Launch Claude Code

Run Claude Code with the custom Anthropic environment variables:

#### On Linux / macOS (Bash / Zsh):
```bash
export ANTHROPIC_BASE_URL="http://localhost:8000"
export ANTHROPIC_API_KEY="none"

claude --model claude-sonnet-5.5
```

#### On Windows (PowerShell):
```powershell
$env:ANTHROPIC_BASE_URL = "http://localhost:8000"
$env:ANTHROPIC_API_KEY = "none"

claude --model claude-sonnet-5.5
```

#### On Windows (Command Prompt):
```cmd
set ANTHROPIC_BASE_URL=http://localhost:8000
set ANTHROPIC_API_KEY=none

claude --model claude-sonnet-5.5
```

---

## ⚠️ Important Rules & Gotchas

### 1. Base URL Path Format
> [!IMPORTANT]
> **Do NOT include `/v1` or `/v1/messages` in `ANTHROPIC_BASE_URL`!**
> 
> Set:
> ```bash
> ANTHROPIC_BASE_URL="http://localhost:8000"
> ```
> The Anthropic SDK automatically appends `/v1/messages`. Setting `http://localhost:8000/v1` will result in `http://localhost:8000/v1/v1/messages` which causes a `404 Not Found` error.

---

### 2. Log Out of Claude.ai First
If you previously used Claude Code with your personal Anthropic account (web browser login):
1. Run `claude logout` or type `/logout` inside an active Claude Code session.
2. Ensure `ANTHROPIC_API_KEY` is set to any dummy string (e.g., `none` or `sk-ant-dummy`) so Claude Code enters API key mode instead of opening a web browser OAuth flow.

---

### 3. Model Resolution & Fallback
`kiro-proxy` automatically inspects your AWS Kiro tier and resolves Claude model names dynamically:

- **Free Tier**: Automatically routes requests to `claude-sonnet-4.5`.
- **Pro / Paid Tier**: Automatically routes requests to `claude-sonnet-5.5` (or `claude-sonnet-5`).
- You can pass any of the following model names to Claude Code:
  - `claude-sonnet-5.5`
  - `claude-sonnet-5`
  - `claude-sonnet-4.5`
  - `claude-3-7-sonnet-20250219`
  - `default`

---

## 💡 Convenient Aliases & Shortcuts

To avoid typing environment variables every time, define a custom alias or wrapper script.

### Linux / macOS (`~/.bashrc` or `~/.zshrc`):
Add the following line to your shell configuration file:
```bash
alias kiro-claude='ANTHROPIC_BASE_URL="http://localhost:8000" ANTHROPIC_API_KEY="none" claude --model claude-sonnet-5.5'
```
Then reload your shell:
```bash
source ~/.bashrc  # or source ~/.zshrc
kiro-claude
```

---

### Windows PowerShell (`$PROFILE`):
Add the following function to your PowerShell profile (run `notepad $PROFILE` to edit):
```powershell
function kiro-claude {
    $env:ANTHROPIC_BASE_URL = "http://localhost:8000"
    $env:ANTHROPIC_API_KEY = "none"
    claude --model claude-sonnet-5.5 $args
}
```
Then run:
```powershell
kiro-claude
```

---

### Windows Command Script (`kiro-claude.cmd`):
Save the following as `%USERPROFILE%\.local\bin\kiro-claude.cmd`:
```cmd
@echo off
setlocal
set ANTHROPIC_BASE_URL=http://localhost:8000
set ANTHROPIC_API_KEY=none
claude --model claude-sonnet-5.5 %*
endlocal
```

---

## 🛠️ Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Connection Refused (`ECONNREFUSED 127.0.0.1:8000`)** | `kiro-proxy` is not running. | Start `kiro-proxy` in another terminal or run `curl http://localhost:8000/health` to verify. |
| **HTTP 401 Session Expired** | AWS Kiro authentication token expired or logged out. | Run `kiro-cli whoami`. If signed out, run `kiro-cli login --use-device-flow` to refresh credentials. |
| **HTTP 404 Not Found** | Incorrect `ANTHROPIC_BASE_URL`. | Make sure `ANTHROPIC_BASE_URL` is exactly `http://localhost:8000` without `/v1` or `/messages`. |
| **Browser OAuth Keeps Opening** | Claude Code is still in OAuth login mode. | Run `claude logout` and ensure `export ANTHROPIC_API_KEY="none"` is set in your current shell. |
| **Model Not Found** | Model requested is not available in Kiro. | Pass `--model claude-sonnet-5.5` or check available models at `http://localhost:8000/v1/models`. |
