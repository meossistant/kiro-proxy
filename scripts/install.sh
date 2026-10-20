#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Installing kiro-proxy ==="
echo "Repository path: $REPO_DIR"

# 1. Check or install uv
if ! command -v uv &> /dev/null; then
    echo ">> 'uv' not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

echo ">> Using uv: $(uv --version)"

# 2. Check kiro-cli
if ! command -v kiro-cli &> /dev/null; then
    echo ">> [WARNING] 'kiro-cli' not found in PATH."
    echo "   Please install it: curl -fsSL https://cli.kiro.dev/install | bash"
else
    echo ">> kiro-cli found: $(kiro-cli --version 2>&1 | head -n 1)"
    if kiro-cli whoami 2>&1 | grep -q "Logged in"; then
        echo ">> kiro-cli authentication: OK"
    else
        echo ">> [NOTICE] kiro-cli is not logged in. Run 'kiro-cli login --use-device-flow' to authenticate."
    fi
fi

# 3. Sync dependencies with uv
echo ">> Syncing dependencies..."
cd "$REPO_DIR"
uv sync

# 4. Create global launcher in ~/.local/bin
INSTALL_BIN="$HOME/.local/bin"
mkdir -p "$INSTALL_BIN"
LAUNCHER="$INSTALL_BIN/kiro-proxy"

cat << EOF > "$LAUNCHER"
#!/usr/bin/env bash
cd "$REPO_DIR" && exec uv run kiro-proxy "\$@"
EOF

chmod +x "$LAUNCHER"
echo ">> Created global launcher at: $LAUNCHER"

# 5. Ensure PATH includes ~/.local/bin
SHELL_CONFIG=""
if [ -n "$BASH_VERSION" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
elif [ -n "$ZSH_VERSION" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
fi

if [[ ":$PATH:" != *":$INSTALL_BIN:"* ]]; then
    if [ -n "$SHELL_CONFIG" ] && [ -f "$SHELL_CONFIG" ]; then
        if ! grep -q 'export PATH=.*\.local/bin' "$SHELL_CONFIG"; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_CONFIG"
            echo ">> Added $INSTALL_BIN to $SHELL_CONFIG"
        fi
    fi
    export PATH="$INSTALL_BIN:$PATH"
fi

echo ""
echo "=== Installation complete! ==="
echo "You can now run 'kiro-proxy' from anywhere in your terminal."
echo "Start the proxy: kiro-proxy"
echo "Health check:    curl http://localhost:8000/health"
