#!/usr/bin/env bash
# One-time setup: Python venv with websockets, check tools and API key.
set -e
cd "$(dirname "$0")"
for t in curl jq python3 file; do command -v $t >/dev/null || { echo "missing: $t"; exit 1; }; done
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
chmod +x *.sh
if [ -z "${SMALLEST_API_KEY:-}" ] && [ ! -f .env ]; then
  echo "No API key yet. Run:  read -s -p 'key: ' K && echo \"SMALLEST_API_KEY=\$K\" > .env && chmod 600 .env"
else
  echo "setup ok"
fi
