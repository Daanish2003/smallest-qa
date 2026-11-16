#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -f .env ] && { set -a; . ./.env; set +a; }; : "${SMALLEST_API_KEY:?set SMALLEST_API_KEY or create .env}"
./probe.sh step1_docs_stt -X POST "https://api.smallest.ai/waves/v1/stt/?model=pulse&language=en" \
  -H "Authorization: Bearer $SMALLEST_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/smallest-inc/cookbook/raw/main/speech-to-text/getting-started/samples/audio.wav"}'
jq . evidence/step1_docs_stt.body
