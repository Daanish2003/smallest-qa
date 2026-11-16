#!/usr/bin/env bash
# Step 3: TTS REST error semantics. Each case run twice, sequentially, 1 s apart.
cd "$(dirname "$0")"
[ -f .env ] && { set -a; . ./.env; set +a; }; : "${SMALLEST_API_KEY:?set SMALLEST_API_KEY or create .env}"
U=https://api.smallest.ai/waves/v1/tts
CT="Content-Type: application/json"
for run in 1 2; do
  # --- auth cases (valid payload) ---
  ./probe.sh e_auth_none_r$run      -X POST $U -H "$CT" -d @tts.json; sleep 1
  ./probe.sh e_auth_bad_r$run       -X POST $U -H "$CT" -H "Authorization: Bearer sk_invalid0000" -d @tts.json; sleep 1
  ./probe.sh e_auth_nobearer_r$run  -X POST $U -H "$CT" -H "Authorization: $SMALLEST_API_KEY" -d @tts.json; sleep 1
  # --- payload cases (valid key) ---
  for p in payloads/*.json; do
    n=$(basename $p .json)
    ./probe.sh e_${n}_r$run -X POST $U -H "$CT" -H "Authorization: Bearer $SMALLEST_API_KEY" -d @$p; sleep 1
  done
  # --- wrong content type ---
  ./probe.sh e_ctype_text_r$run -X POST $U -H "Content-Type: text/plain" -H "Authorization: Bearer $SMALLEST_API_KEY" -d @tts.json; sleep 1
done
echo; echo "== summary (label, status, total s, request id) =="
grep -P '\te_' evidence/log.tsv | awk -F'\t' '{printf "%-26s %s %6s  %s\n",$2,$3,$5,$7}'
