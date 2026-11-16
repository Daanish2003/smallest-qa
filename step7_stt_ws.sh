#!/usr/bin/env bash
# Step 7 — STT WebSocket (wss://api.smallest.ai/waves/v1/stt/live). Evidence for W8, F6, F7.
# Takes ~1.5 min. Timeout and bad-param tests run twice for reproducibility.
cd "$(dirname "$0")"
PY=.venv/bin/python
$PY ws_probe.py stt_happy            # stream 5.6 s sample in real time, close_stream -> is_last (W8)
$PY ws_probe.py stt_keepalive        # ping / keepalive / keep_alive / keep-alive -> pong (W8)
for run in 1 2; do
  $PY ws_probe.py stt_timeout 10     # documented timeout message + close code (W8, F6)
  $PY ws_probe.py stt_bad_params     # bad encoding / model / language (F6, F7)
done
