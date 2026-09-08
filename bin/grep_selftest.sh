#!/usr/bin/env bash
# grep_selftest.sh — smoke test the read-only repo grep engine.
# Resolves the repo root from this script's location; no hardcoded paths.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"
python3 refs/pcjr_repo_grep.py roots
python3 refs/pcjr_repo_grep.py stats
python3 refs/pcjr_repo_grep.py grep "carrier_high_us|gap2" --context 2
echo "grep_selftest OK"
