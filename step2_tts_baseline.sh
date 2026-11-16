#!/usr/bin/env bash
# Step 2: 3 sequential TTS REST calls (one at a time, so no concurrency effects)
cd "$(dirname "$0")"
[ -f .env ] && { set -a; . ./.env; set +a; }; : "${SMALLEST_API_KEY:?set SMALLEST_API_KEY or create .env}"
for i in 1 2 3; do
  ./probe.sh tts_ok_$i -X POST https://api.smallest.ai/waves/v1/tts \
    -H "Authorization: Bearer $SMALLEST_API_KEY" -H "Content-Type: application/json" -H "Accept: audio/wav" \
    -d @tts.json
  sleep 2
done
for i in 1 2 3; do file evidence/tts_ok_$i.body; done
