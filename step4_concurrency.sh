#!/usr/bin/env bash
# Step 4: TTS concurrency. Docs: 1 concurrent TTS request per account; a 2nd concurrent HTTP request -> 429.
# 3 requests fired at once, 3 runs (sync REST) + 2 runs (SSE). Max 3 in flight (rule: <=5).
cd "$(dirname "$0")"
[ -f .env ] && { set -a; . ./.env; set +a; }; : "${SMALLEST_API_KEY:?set SMALLEST_API_KEY or create .env}"
AUTH="Authorization: Bearer $SMALLEST_API_KEY"; CT="Content-Type: application/json"
for run in 1 2 3; do
  echo "--- sync /tts run $run ---"
  for i in 1 2 3; do
    ./probe.sh c_sync_r${run}_$i -X POST https://api.smallest.ai/waves/v1/tts -H "$AUTH" -H "$CT" -H "Accept: audio/wav" -d @tts.json &
  done; wait; sleep 5
done
for run in 1 2; do
  echo "--- SSE /tts/live run $run ---"
  for i in 1 2 3; do
    ./probe.sh c_sse_r${run}_$i -N -X POST https://api.smallest.ai/waves/v1/tts/live -H "$AUTH" -H "$CT" -H "Accept: text/event-stream" -d @tts_sse.json &
  done; wait; sleep 5
done
echo; echo "== 429 headers (full) =="
for f in evidence/c_*.hdr; do
  if head -1 "$f" | grep -q ' 429'; then echo "## $f"; tr -d '\r' < "$f" | grep -viE '^(set-cookie|content-security-policy)'; echo "body: $(head -c 300 ${f%.hdr}.body)"; fi
done
