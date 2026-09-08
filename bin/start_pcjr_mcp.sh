#!/usr/bin/env bash
# Start the pcjr-tools MCP server.
# Resolves the repo root from this script's location; no hardcoded paths.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

export PCJR_REF_DIR="${PCJR_REF_DIR:-$REPO_ROOT/refs}"
export PCJR_HOST="${PCJR_HOST:-127.0.0.1}"
export PCJR_PORT_REF="${PCJR_PORT_REF:-8765}"

exec uv run "$REPO_ROOT/mcp/pcjr_tools_server.py"
