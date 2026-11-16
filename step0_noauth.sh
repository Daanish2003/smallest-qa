#!/usr/bin/env bash
# Step 0 — TTS REST with no Authorization header (free; no key needed). Evidence for W2.
cd "$(dirname "$0")"
./probe.sh smoke_noauth -X POST https://api.smallest.ai/waves/v1/tts \
  -H 'Content-Type: application/json' -d '{"text":"hi","voice_id":"meher","model":"lightning_v3.1_pro"}'
