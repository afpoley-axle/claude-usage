#!/bin/zsh
# Refresh usage data and commit a snapshot (pushes if a remote is configured).
set -euo pipefail
cd "$(dirname "$0")"
/usr/bin/env python3 collect.py
git add data WEEKLY.md report.html
if git diff --cached --quiet; then
  echo "No usage changes."
  exit 0
fi
git commit -q -m "Usage snapshot $(date +%Y-%m-%d)"
if git remote | grep -q .; then
  git push -q
fi
echo "Committed usage snapshot."
