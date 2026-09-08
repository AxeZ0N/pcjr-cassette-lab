#!/bin/bash
# session_handoff.sh — copy the newest session handoff plus repo stats
# to the clipboard for pasting into the assistant at session start.
#
# Recency signal: the commit that ADDED the handoff, via --diff-filter=A.
# Never inode (filesystem allocation order), mtime (reset rewrites it),
# or filename sort (same-date ties break alphabetically, not by time).
set -euo pipefail

export DISPLAY=:0

BASE_DIR="/home/k/Code/Helpful/PyCJr"

# Newest handoff = the session file first added in the most recent
# commit that created one. Date-shape filter excludes sessions/README.md.
newest_rel=$(cd "$BASE_DIR" && git log -1 --diff-filter=A \
    --name-only --format= -- 'sessions/*.md' \
  | grep -m1 -E '^sessions/[0-9]{4}-[0-9]{2}-[0-9]{2}_.*\.md$') || true

if [[ -z "${newest_rel:-}" ]]; then
    echo "ERROR: no committed session handoff found" >&2
    exit 1
fi

filename=$(basename "$newest_rel")

LOG_OUTPUT=$(cd "$BASE_DIR" && git log --oneline -5)
STATUS_OUTPUT=$(cd "$BASE_DIR" && git status --short)
FILES_OUTPUT=$(cd "$BASE_DIR" && git ls-files)

{
    echo "LOG:"
    echo "$LOG_OUTPUT"
    echo ""
    echo "STATUS:"
    echo "${STATUS_OUTPUT:-<clean>}"
    echo ""
    echo "FILES:"
    echo "$FILES_OUTPUT"
    echo ""
    echo "--- $filename ---"
    cat "$BASE_DIR/$newest_rel"
} | xclip -selection clipboard

echo "Copied: $filename"
