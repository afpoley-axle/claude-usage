#!/bin/zsh
# Install a launchd agent that runs update.sh 5 minutes before the weekly allowance reset
# (default Thursday 15:00, so Thursday 14:55). Honors CLAUDE_USAGE_RESET_DAY / _RESET_HOUR,
# plus CLAUDE_USAGE_PUSH and CLAUDE_USAGE_DATA_DIR if set when you run this installer.
# Uninstall: launchctl bootout gui/$(id -u)/com.claude-usage.weekly && rm ~/Library/LaunchAgents/com.claude-usage.weekly.plist
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL=com.claude-usage.weekly
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

# launchd weekdays: 1=Mon ... 7=Sun. Fire at HH-1:55; if the reset hour is 0, fire 23:55 the day before.
DAYS=(mon tue wed thu fri sat sun)
RESET_DAY="${CLAUDE_USAGE_RESET_DAY:-thu}"
RESET_HOUR="${CLAUDE_USAGE_RESET_HOUR:-15}"
WD=${DAYS[(Ie)${${RESET_DAY:l}[1,3]}]}
[[ $WD -ge 1 && $RESET_HOUR == <0-23> ]] || { echo "Bad CLAUDE_USAGE_RESET_DAY/HOUR" >&2; exit 1; }
if (( RESET_HOUR == 0 )); then HOUR=23; WD=$(( (WD + 5) % 7 + 1 )); else HOUR=$(( RESET_HOUR - 1 )); fi

ENV_XML=""
for v in CLAUDE_USAGE_RESET_DAY CLAUDE_USAGE_RESET_HOUR CLAUDE_USAGE_PUSH CLAUDE_USAGE_DATA_DIR; do
  [[ -n "${(P)v:-}" ]] && ENV_XML+="<key>$v</key><string>${(P)v}</string>"
done

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
  <dict><key>Weekday</key><integer>$WD</integer><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>55</integer></dict>
  <key>EnvironmentVariables</key><dict>$ENV_XML</dict>
  <key>StandardOutPath</key><string>$DIR/logs/update.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/update.log</string>
</dict>
</plist>
PLIST
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed $PLIST (runs ${DAYS[$WD]} $HOUR:55; missed runs fire on next wake)."
