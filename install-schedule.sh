#!/bin/zsh
# Install a launchd agent that runs update.sh every Thursday at 15:05, just after the allowance reset.
# Uninstall: launchctl bootout gui/$(id -u)/com.claude-usage.weekly && rm ~/Library/LaunchAgents/com.claude-usage.weekly.plist
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL=com.claude-usage.weekly
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$DIR/logs"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/zsh</string><string>-l</string><string>$DIR/update.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>15</integer><key>Minute</key><integer>5</integer></dict>
  <key>StandardOutPath</key><string>$DIR/logs/update.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/update.log</string>
</dict>
</plist>
PLIST
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed $PLIST (runs Thursdays 15:05; missed runs fire on next wake)."
