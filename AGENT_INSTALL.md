# AI Coding Agent Installation Guide (Playbook)

> **Instructions for AI Agents** (Cursor Agent, Claude Code, Cline, Roo Code, Windsurf, Aider, GitHub Copilot Workspace, etc.)  
> When the user asks you to **"Install and set up kiro-proxy"**, follow the autonomous instructions below step-by-step according to the host operating system.

---

## 🎯 Goal
Set up and run `kiro-proxy` on the user's system so that local tools, IDEs, and CLI assistants (such as Claude Code, Cursor, Open WebUI, LibreChat) can access AWS Kiro AI through standard OpenAI (`/v1/chat/completions`) and Anthropic (`/v1/messages`) endpoints.

---

## 📋 Step 0: Detect Operating System & Shell

Determine the host OS and user shell:
- **Windows**: PowerShell or Command Prompt.
- **Linux / macOS**: Bash, Zsh, or Fish.

---

## 📦 Step 1: Verify & Install Prerequisites

### 1.1 Verify Python (>= 3.12)
Run:
```bash
# Windows / Linux / macOS
python --version || python3 --version
```
If Python >= 3.12 is missing, install it or let `uv` download it automatically.

### 1.2 Verify or Install `uv` (Fast Package Manager)
Check if `uv` exists:
```bash
uv --version
```
If `uv` is not found, install it automatically:
- **Windows (PowerShell)**:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" + [System.Environment]::GetEnvironmentVariable("Path","Machine")
  ```
- **Linux / macOS (Bash/Zsh)**:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  source $HOME/.cargo/env 2>/dev/null || source $HOME/.local/bin/env 2>/dev/null || export PATH="$HOME/.local/bin:$PATH"
  ```

### 1.3 Verify or Install `kiro-cli`
Check if `kiro-cli` exists:
```bash
kiro-cli --version
```
If `kiro-cli` is not installed:
- **Linux / macOS**:
  ```bash
  curl -fsSL https://cli.kiro.dev/install | bash
  export PATH="$HOME/.local/bin:$PATH"
  ```
- **Windows**:
  Download and install the official Windows installer from [https://kiro.dev/downloads/](https://kiro.dev/downloads/) or run:
  ```powershell
  # Check if installed in standard paths:
  $kiroPaths = @(
      "$env:LOCALAPPDATA\Programs\kiro\bin\kiro-cli.exe",
      "$env:USERPROFILE\.local\bin\kiro-cli.exe",
      "$env:ProgramFiles\kiro\kiro-cli.exe"
  )
  foreach ($p in $kiroPaths) { if (Test-Path $p) { $env:Path += ";$(Split-Path $p)"; break } }
  ```

### 1.4 Check Kiro CLI Authentication
Run:
```bash
kiro-cli whoami
```
- If it outputs `Logged in with ... Email: ...`, authentication is active. Proceed to Step 2.
- If it outputs `Not logged in`:
  - Run `kiro-cli login --use-device-flow`
  - Print the verification URL and code for the user, and prompt the user to authorize it in their web browser.

---

## 🛠️ Step 2: Set Up `kiro-proxy`

### 2.1 Clone or Navigate to Repository
If not already inside the repository directory:
```bash
git clone https://github.com/meossistant/kiro-proxy.git
cd kiro-proxy
```

### 2.2 Install Dependencies via `uv`
```bash
uv sync
```

### 2.3 Verify Installation with Unit Tests
```bash
uv run pytest tests/test_proxy.py
```
Ensure all tests pass.

---

## 🌐 Step 3: Add `kiro-proxy` to System PATH

Make `kiro-proxy` runnable globally from any terminal.

### On Windows (PowerShell):
1. Create a global command wrapper `kiro-proxy.cmd` inside the user's bin directory:
```powershell
$binDir = "$env:USERPROFILE\.local\bin"
if (!(Test-Path $binDir)) { New-Item -ItemType Directory -Path $binDir -Force }

$repoPath = (Get-Location).Path
$cmdContent = "@echo off`r`ncd /d `"$repoPath`"`r`nuv run kiro-proxy %*"
Set-Content -Path "$binDir\kiro-proxy.cmd" -Value $cmdContent

# Add to User PATH if not present
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$binDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$binDir", "User")
    $env:Path += ";$binDir"
}
```

### On Linux / macOS (Bash/Zsh):
1. Create a global launcher script in `~/.local/bin/kiro-proxy`:
```bash
mkdir -p "$HOME/.local/bin"
REPO_PATH="$(pwd)"

cat << 'EOF' > "$HOME/.local/bin/kiro-proxy"
#!/usr/bin/env bash
REPO_DIR="REPLACE_REPO_PATH"
cd "$REPO_DIR" && exec uv run kiro-proxy "$@"
EOF

sed -i.bak "s|REPLACE_REPO_PATH|$REPO_PATH|g" "$HOME/.local/bin/kiro-proxy" && rm -f "$HOME/.local/bin/kiro-proxy.bak"
chmod +x "$HOME/.local/bin/kiro-proxy"

# Ensure ~/.local/bin is in PATH in ~/.bashrc or ~/.zshrc
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    [[ -f "$HOME/.zshrc" ]] && echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
    export PATH="$HOME/.local/bin:$PATH"
fi
```

---

## 🚀 Step 4: Start the Service & Verify Health

Start the server in background:
```bash
# Windows (PowerShell - Background Process)
Start-Process powershell -ArgumentList "-NoProfile -Command cd '$repoPath'; uv run kiro-proxy" -WindowStyle Hidden

# Linux / macOS (Detached background)
nohup uv run kiro-proxy > kiro-proxy.log 2>&1 &
```

Wait 3 seconds, then test the health endpoint:
```bash
curl http://localhost:8000/health
```
Verify the JSON response returns `"status": "healthy"`.

---

## 📝 Step 5: Inform the User

Provide the user with a concise summary:
1. `kiro-proxy` is installed and running at `http://localhost:8000`.
2. Both OpenAI endpoints (`/v1/chat/completions`, `/v1/models`) and Anthropic endpoint (`/v1/messages`) are active.
3. Show how they can connect tools like **Claude Code** (point to [CLAUDE_CODE_SETUP.md](CLAUDE_CODE_SETUP.md)) or **Cursor**.
