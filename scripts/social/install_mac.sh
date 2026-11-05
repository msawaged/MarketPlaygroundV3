#!/bin/bash
# Installs the MarketPlayground social bot on a Mac: dependencies, a config template, and a launchd job
# that posts at 9:40 am and 5:10 pm local time (if the Mac was asleep, it runs when it wakes).
#   bash scripts/social/install_mac.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
HOME_DIR="$HOME/.mp_social"
PLIST="$HOME/Library/LaunchAgents/com.mulabs.mp-social.plist"
NODE="$(command -v node || true)"

[ -n "$NODE" ] || { echo "Install Node first: brew install node"; exit 1; }
command -v ffmpeg >/dev/null || { echo "Installing ffmpeg..."; brew install ffmpeg; }
cd "$REPO" && [ -d node_modules/playwright ] || npm install --no-save playwright
npx playwright install chromium

mkdir -p "$HOME_DIR"
if [ ! -f "$HOME_DIR/config.json" ]; then
  cp "$REPO/scripts/social/config.example.json" "$HOME_DIR/config.json"
  chmod 600 "$HOME_DIR/config.json"
  echo "Created $HOME_DIR/config.json: add your tokens, then set \"live\": true."
fi

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.mulabs.mp-social</string>
  <key>ProgramArguments</key><array><string>$NODE</string><string>$REPO/scripts/social/post.js</string></array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>StartCalendarInterval</key><array>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>40</integer></dict>
    <dict><key>Hour</key><integer>17</integer><key>Minute</key><integer>10</integer></dict>
  </array>
  <key>StandardOutPath</key><string>$HOME_DIR/bot.log</string>
  <key>StandardErrorPath</key><string>$HOME_DIR/bot.log</string>
</dict></plist>
EOF
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Installed. Try a dry run now:  node $REPO/scripts/social/post.js --dry-run"
echo "Logs: $HOME_DIR/bot.log   Stop it:  launchctl unload $PLIST"
