#!/usr/bin/env bash
# Step 5 — TTS WebSocket (wss://api.smallest.ai/waves/v1/tts/live). Evidence for W6, W7, F4, F5, F1 (WS shape), F2 (WS).
# Takes ~5 min (tts_happy waits 60 s after each of 3 'complete' frames to see if the server closes).
cd "$(dirname "$0")"
PY=.venv/bin/python
$PY ws_probe.py tts_happy            # 3 runs: TTFB, last-chunk -> complete gap (F5), close after complete? (F4)
$PY ws_probe.py tts_no_auth          # no key / bad key at handshake (W7)
$PY ws_probe.py tts_bad_inputs       # non-JSON, empty text, bad voice, bad rate, missing text (W7, F1, F2)
$PY ws_probe.py tts_flush_variants   # F5 root cause: baseline vs flush:true vs max_buffer_flush_ms:100, 2 runs each
