#!/bin/zsh
# Refresh usage data. Optionally commit and push it to a private data repo.
#
#   ./update.sh                      collect only (default)
#   CLAUDE_USAGE_PUSH=1 ./update.sh  also commit and push the data directory
#
# Pushing requires the data directory (CLAUDE_USAGE_DATA_DIR, default ./data) to be
# its own git repo with a remote. This tool repo never contains your data.
set -euo pipefail
cd "$(dirname "$0")"
/usr/bin/env python3 collect.py
[[ "${CLAUDE_USAGE_PUSH:-}" == "1" ]] || exit 0

DATA_DIR="${CLAUDE_USAGE_DATA_DIR:-$PWD/data}"
if [[ "$(git -C "$DATA_DIR" rev-parse --show-toplevel 2>/dev/null)" != "$(cd "$DATA_DIR" && pwd -P)" ]]; then
  echo "CLAUDE_USAGE_PUSH=1 but $DATA_DIR is not its own git repo; skipping push." >&2
  exit 1
fi
git -C "$DATA_DIR" add -A
# Reports carry a "generated at" timestamp that changes every run; only commit when the usage itself changed.
if git -C "$DATA_DIR" diff --cached --quiet -- daily.csv; then
  git -C "$DATA_DIR" reset -q
  echo "No usage changes."
  exit 0
fi
git -C "$DATA_DIR" commit -q -m "Usage snapshot $(date +%Y-%m-%d)"
REMOTE="$(git -C "$DATA_DIR" remote | head -1)"
if [[ -n "$REMOTE" ]]; then
  # -u so the first push from a freshly `git init`ed data repo works without extra setup
  git -C "$DATA_DIR" push -q -u "$REMOTE" HEAD
fi
echo "Committed usage snapshot."
