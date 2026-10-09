#!/bin/zsh
# Regenerate the synthetic example report and the README screenshots (needs Google Chrome).
set -euo pipefail
cd "$(dirname "$0")"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
TMP="$(mktemp -d)"
python3 demo.py
mkdir -p docs/img
shoot() { "$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size=1200,1500 \
  --virtual-time-budget=3000 --screenshot="$PWD/docs/img/$1" "file://$2" >/dev/null 2>&1; }
shoot portal.png "$PWD/examples/report.html"
sed 's/<html /<html data-theme="dark" /' examples/report.html > "$TMP/dark.html"
shoot portal-dark.png "$TMP/dark.html"
echo "Wrote docs/img/portal.png and portal-dark.png"
