#!/usr/bin/env bash
# Snapshot the doc pages every 'Expected' in the report quotes (docs change; this records what we tested against).
cd "$(dirname "$0")"; mkdir -p docs
for p in models/text-to-speech/quickstart models/text-to-speech/overview models/text-to-speech/choosing-a-transport \
  models/text-to-speech/sync-async models/text-to-speech/streaming models/text-to-speech/continuations \
  models/speech-to-text/pre-recorded/quickstart models/speech-to-text/pre-recorded/audio-formats \
  models/speech-to-text/pre-recorded/troubleshooting models/speech-to-text/realtime-web-socket/quickstart \
  models/speech-to-text/realtime-web-socket/response-format models/speech-to-text/realtime-web-socket/audio-formats \
  models/speech-to-text/realtime-web-socket/troubleshooting models/speech-to-text/features/keep-alive \
  api-reference/authentication models/getting-started models/troubleshooting/error-reference \
  api-reference/concurrency-and-limits overview/administration/subscription-plans; do
  curl -s -o "docs/$(echo $p | tr / _).md" -w "%{http_code} $p\n" "https://docs.smallest.ai/$p.md"
done
