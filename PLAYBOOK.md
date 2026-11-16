# Smallest QA — do-it-yourself playbook (area: APIs)

Budget: **$1.00 credit**, ~2–3 hours. Keep TTS text short (one sentence). Max 5 requests at once.
Every result lands in `evidence/log.tsv` (REST) or `evidence/ws.log` (WebSocket) with IST time + request ID.

## 0. Setup (5 min)
```bash
cd ~/hobby/smallest-qa
read -s -p "key: " K && echo "SMALLEST_API_KEY=$K" > .env && chmod 600 .env   # never paste the key anywhere
set -a; . ./.env; set +a
B=https://api.smallest.ai/waves/v1
J='Content-Type: application/json'; A="Authorization: Bearer $SMALLEST_API_KEY"
TTS='{"text":"Hello from the QA test.","voice_id":"meher","model":"lightning_v3.1_pro","sample_rate":24000,"output_format":"wav"}'
```
Start a timer. Note the start time — you need "time spent" at the end.

## 1. Time-to-first-call (developer experience, but it is evidence for the API area too)
Copy the curl from docs `api-reference/authentication` exactly. Did it work first time? Note minutes taken and any doc mismatch.

## 2. TTS REST — happy path, 3 runs (latency baseline)
```bash
for i in 1 2 3; do ./probe.sh tts_ok_$i -X POST $B/tts -H "$A" -H "$J" -H 'Accept: audio/wav' -d "$TTS"; done
file evidence/tts_ok_1.body     # is it really a WAV at 24 kHz as requested?
```

## 3. TTS REST — error semantics (does each fail clearly, with the documented code?)
| label | what to send | docs expect |
|---|---|---|
| auth_none | drop `-H "$A"` | 401 |
| auth_bad | `-H 'Authorization: Bearer sk_invalid'` | 401 |
| auth_noBearer | `-H "Authorization: $SMALLEST_API_KEY"` | 401 |
| json_broken | `-d '{"text":'` | 400 with a useful message |
| text_missing | `-d '{"voice_id":"meher","model":"lightning_v3.1_pro"}'` | 400/422 naming `text` |
| text_empty | `"text":""` | 400 |
| voice_bad | `"voice_id":"nope"` | 400/404 naming voice |
| model_bad | `"model":"nope"` | 400 naming model |
| rate_bad | `"sample_rate":12345` | 400 or documented clamp |
| format_bad | `"output_format":"mp9"` | 400 |
| long_text | 1000 chars (docs: "max ~250 recommended") | what happens? truncated? error? *costs credit — do once* |

```bash
./probe.sh tts_voice_bad -X POST $B/tts -H "$A" -H "$J" -d '{"text":"hi","voice_id":"nope","model":"lightning_v3.1_pro"}'
```
For each: status, body, does it carry a request ID, is the error **shape** consistent across cases (`message` vs `error` vs `detail`)?
Check the doc table vs reality — any 200 with an error body, or a 500 for a bad input, is a finding.

## 4. TTS concurrency (the strongest test — docs make a precise claim)
Docs (`api-reference/concurrency-and-limits`): 1 TTS request at a time per account; a 2nd concurrent HTTP request → **429**; error-reference says honour `Retry-After` "if present".
```bash
for run in 1 2 3; do
  for i in 1 2 3; do ./probe.sh conc_r${run}_$i -X POST $B/tts -H "$A" -H "$J" -d "$TTS" & done; wait; sleep 5
done
grep conc_ evidence/log.tsv
```
Record per run: how many 200 vs 429, Retry-After present?, request IDs, body of the 429. Also try the SSE endpoint (`POST $B/tts/live`) the same way — docs say the limit applies to it too.

## 5. TTS WebSocket
```bash
.venv/bin/python ws_probe.py tts_happy        # TTFB, frame format, does server close after "complete"?
.venv/bin/python ws_probe.py tts_no_auth      # 401 at handshake, or accepted then error?
.venv/bin/python ws_probe.py tts_bad_inputs   # error frame vs silent hang vs close code
.venv/bin/python ws_probe.py tts_two_sockets  # 3 sockets, 1 request each: docs say extras get "an error"
.venv/bin/python ws_probe.py tts_idle         # leave it; how long until closed? which close code? (docs silent = finding candidate)
```
Run the concurrency one 3 times.

## 6. STT REST (pre-recorded)
```bash
./probe.sh stt_url_ok -X POST "$B/stt/?model=pulse&language=en" -H "$A" -H "$J" \
  -d '{"url":"https://github.com/smallest-inc/cookbook/raw/main/speech-to-text/getting-started/samples/audio.wav"}'
```
Compare body to the documented example (`status`, `transcription`, `words`, `utterances`, `metadata`).
Then: URL that 404s, URL to a non-audio file (e.g. an HTML page), no body, raw bytes upload with wrong Content-Type, bad `language=xx`, bad `model=nope`. Expect clear 4xx each time.

## 7. STT WebSocket (docs make very specific claims here — great for findings)
```bash
.venv/bin/python ws_probe.py stt_happy         # partials, is_final, is_last after close_stream?
.venv/bin/python ws_probe.py stt_keepalive     # each of ping/keepalive/keep_alive/keep-alive → pong?
.venv/bin/python ws_probe.py stt_timeout 10    # closed at ~10s with the exact documented message?
.venv/bin/python ws_probe.py stt_timeout 99999 # docs: clamped, not rejected (Ctrl-C after it connects OK)
.venv/bin/python ws_probe.py stt_bad_params    # bad encoding/model/language: rejected at handshake or silent?
.venv/bin/python ws_probe.py stt_wrong_rate    # mismatched sample_rate: error or garbage transcript?
.venv/bin/python ws_probe.py stt_abrupt        # drop mid-stream, reconnect at once: does it recover?
```
Run `stt_timeout 10` three times and record the actual close time each run (the `+ms` column).

## 8. Check the console
After testing, open app.smallest.ai usage page: do the counts/charges match what you sent? (e.g. 429'd requests billed? failed requests counted?) Screenshot it.

## 9. Turning results into findings
Only write up a mismatch you reproduced ≥2 times. Each finding needs:
- **Expected**: quote the doc sentence + page.
- **Observed**: numbers ("3 of 3 runs…").
- **Evidence**: the exact command + the log lines (time IST, request IDs). Redact key as `sk_...`.
- **Customer impact vs SLO**: e.g. "client retrying on 429 without Retry-After hammers; 2 of 3 concurrent requests fail → a 3-agent call centre misses a 99.9% TTS success SLO".
- **Severity**: critical (data loss / wrong success) · major (documented behaviour broken, retries break) · minor (doc mismatch with workaround) · trivial.

Good candidates to watch for: missing `Retry-After` on 429; no request ID on some error paths; inconsistent error body shapes; 500 for bad input; WS errors as silent close (code 1000/1006) without a message; `timeout` not honoured / message differs from docs; keep-alive aliases not all answered; billed for failed requests; doc examples that don't run as written.

**Anything security-related (e.g. key accepted in places it shouldn't be, data from other accounts) → only the private security field.**

## 10. "What is done well", top 3 fixes, time
Note good things as you go (fast 401 with request ID, clear messages, etc.). Top fixes = your 3 highest-severity findings, each with why it ranks there (customer blast radius).
