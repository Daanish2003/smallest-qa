#!/usr/bin/env bash
# Step 1a — Docs quickstart TTS example, copied verbatim from docs api-reference/authentication
# ("Generate speech (Lightning TTS)"). Evidence for W1.
cd "$(dirname "$0")"
[ -f .env ] && { set -a; . ./.env; set +a; }; : "${SMALLEST_API_KEY:?set SMALLEST_API_KEY or create .env}"
./probe.sh step1_docs_tts -X POST "https://api.smallest.ai/waves/v1/tts" \
  -H "Authorization: Bearer $SMALLEST_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: audio/wav" \
  -d '{"text": "Hello from Smallest AI.", "voice_id": "meher", "model": "lightning_v3.1_pro", "sample_rate": 24000, "output_format": "wav"}'
file evidence/step1_docs_tts.body
