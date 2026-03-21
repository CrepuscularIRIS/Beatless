#!/usr/bin/env bash
set -euo pipefail

# install_cron_example.sh
# Install a minimal cron entry for Beatless automation tick (every 30 minutes).

BEATLESS="${HOME}/.openclaw/beatless"
SCRIPT="$BEATLESS/scripts/rawcli_cron_tick.sh"
LINE="*/30 * * * * BEATLESS_ROOT=$BEATLESS bash $SCRIPT >/dev/null 2>&1"

if [[ ! -x "$SCRIPT" ]]; then
  echo "script not found or not executable: $SCRIPT" >&2
  exit 1
fi

( crontab -l 2>/dev/null | rg -v 'rawcli_cron_tick\.sh' || true; echo "$LINE" ) | crontab -

echo "installed: $LINE"
