#!/usr/bin/env bash
# ACM one-command install + start (Linux/macOS). Mirror of install.ps1.
set -e
here="$(cd "$(dirname "$0")" && pwd)"

echo "ACM install"

# 1) uv (the only bootstrap dependency)
if ! command -v uv >/dev/null 2>&1; then
    echo "  installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 2) environment from the committed lockfile
cd "$here"
uv sync

# 3) self-test (non-fatal)
if ! uv run pytest tests -m "not statistical" -q --tb=no > /dev/null 2>&1; then
    echo "  ! self-test reported failures (non-fatal) - run 'uv run pytest tests' to investigate"
fi

echo ""
echo "ACM ready. Start the service:"
echo "  cd $here"
echo "  uv run python -m acm.service --root acm_data --port 8899"
echo "  -> http://127.0.0.1:8899"
