#!/usr/bin/env bash
# Step 4b: 5 concurrent sync TTS requests (the brief's max), 2 runs, 10 s apart.
cd "$(dirname "$0")"
[ -f .env ] && { set -a; . ./.env; set +a; }; : "${SMALLEST_API_KEY:?set SMALLEST_API_KEY or create .env}"
AUTH="Authorization: Bearer $SMALLEST_API_KEY"; CT="Content-Type: application/json"
for run in 1 2; do
  echo "--- 5 concurrent, run $run ---"
  for i in 1 2 3 4 5; do
    ./probe.sh c5_r${run}_$i -X POST https://api.smallest.ai/waves/v1/tts -H "$AUTH" -H "$CT" -H "Accept: audio/wav" -d @tts.json &
  done; wait; sleep 10
done
