#!/usr/bin/env bash
# jr-commit.sh — append+commit for the PyCJr living repo.
#
# Default allowlist: facts.md, sessions/, docs/.
# --setup: one-time wide allowlist for the two baseline commits.
#
# Usage:
#   jr-commit.sh "<commit message>" facts.md sessions/...
#   jr-commit.sh --setup "<commit message>" bds/... bin/... README.md
set -euo pipefail

SETUP=0
[ "${1:-}" = "--setup" ] && { SETUP=1; shift; }

if [ "$#" -lt 2 ]; then
  echo "Usage: jr-commit.sh [--setup] \"<commit message>\" <file> [<file> ...]" >&2
  exit 1
fi

msg="$1"; shift

for f in "$@"; do
  case "$f" in
    /*) echo "Reject absolute path: $f" >&2; exit 1 ;;
    *..*) echo "Reject '..': $f" >&2; exit 1 ;;
  esac
  if [ "$SETUP" -eq 1 ]; then
    case "$f" in
      bds/*|bin/*|mcp/*|refs/pcjr_repo_grep.py|README.md|MANIFEST.md|pyproject.toml|facts.md|sessions/*|docs/*) ;;
      *) echo "Reject (even in --setup): $f" >&2; exit 1 ;;
    esac
  else
    case "$f" in
      facts.md|sessions/*|docs/*) ;;
      *) echo "Reject outside facts.md/sessions/docs (use --setup for baseline): $f" >&2; exit 1 ;;
    esac
  fi
done

git add -- "$@"
git commit -m "$msg"
