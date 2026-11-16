# Smallest AI API QA — how to reproduce

Every finding in the report comes from a script in this folder. Run them against your own account and you get the same log lines: time (IST), status, latency, request ID.

- **Area tested:** APIs. Lightning v3.1 Pro text-to-speech and Pulse speech-to-text, over REST, SSE and WebSocket, checked against docs.smallest.ai.
- **Original run:** 2026-11-16, 13:50–15:30 IST, from India, on curl 8.23.0, Python 3.14.8 and websockets 17.4.
- **Re-runs:** full suite again 16:14–16:20 IST (`./run_all.sh`), and step 7 again at 16:39 IST. Every finding reproduced; both runs are in the logs. Per-request `.hdr` files hold the latest run (same labels are overwritten); `log.tsv` and `ws.log` keep every run.
- **Snapshot of the docs we tested against:** `docs/` (re-fetch with `./fetch_docs.sh`).

## 1. Setup (2 min)

Needs `curl`, `jq`, `python3` and `file`.

```bash
./setup.sh                                   # creates .venv, installs websockets
read -s -p 'key: ' K && echo "SMALLEST_API_KEY=$K" > .env && chmod 600 .env
# or: export SMALLEST_API_KEY=sk_...        (every script reads either one)
```

## 2. Run

```bash
./run_all.sh          # every step, ~8 min, ~85 API calls, a few cents of credit
./run_all.sh 4 5      # only some steps
```

**Safety:**
- No more than 5 requests are ever in flight at once (the assessment's limit).
- No load testing, and no security tooling.
- Error responses are free. Only successful synthesis or transcription is billed.

## 3. Where results go

**Start with `EVIDENCE.md`.** It's the readable version: one section per step, tables with plain-English headings, the two runs side by side, and each row tagged with the W or F item it supports. Regenerate it any time with `python3 view_evidence.py` (`run_all.sh` does this automatically). The raw files below are the source.

| File | What's in it |
|---|---|
| `evidence/log.tsv` | One line per REST call: `time IST · label · HTTP status · TTFB s · total s · bytes · request-id · Retry-After · start of body` |
| `evidence/<label>.hdr` / `.body` | Full response headers and body for that REST call |
| `evidence/ws.log` | Every WebSocket event: `time IST · +ms since connect · [test] · frame / close code` |

Pull out one step: `grep -P '\tc5_' evidence/log.tsv` or `grep 'tts_fv' evidence/ws.log`.

## 4. Steps: what each tests and what it found

| Step | Script | Docs claim tested | Result |
|---|---|---|---|
| 0 | `step0_noauth.sh` | 401 for a missing key (error-reference) | ✅ W2 |
| 1 | `step1_tts.sh`, `step1_stt.sh` | The quickstart curls in api-reference/authentication work as written | ✅ W1, W3 |
| 2 | `step2_tts_baseline.sh` | Baseline: 3 sequential REST TTS calls | latency reference |
| 3 | `step3_tts_errors.sh` (+ `payloads/`) | Error semantics: 12 bad requests × 2 runs | ✅ W4 · ❌ F1, F2 |
| 4 | `step4_concurrency.sh`, `step4b_concurrency5.sh` | "Only 1 TTS request at a time… second request → 429" (concurrency-and-limits) | ❌ F3 |
| 5 | `step5_tts_ws.sh` → `ws_probe.py tts_*` | WS frame format; "server closes the WebSocket after `complete`" (streaming) | ✅ W6, W7 · ❌ F4, F5 |
| 7 | `step7_stt_ws.sh` → `ws_probe.py stt_*` | `close_stream` → `is_last`; keep-alive aliases → `pong`; `timeout=` message (keep-alive) | ✅ W8 · ❌ F6, F7 |

Step 6 (speech-to-text REST error cases) was planned but not run. `ws_probe.py` also contains `tts_two_sockets`, `tts_idle`, `stt_wrong_rate` and `stt_abrupt`, which are written but were **not run** for the report.

## 5. Findings: reproduce each one

| # | Finding | Severity | Reproduce | What to look for | Original evidence (2026-11-16 IST) |
|---|---|---|---|---|---|
| **F5** | TTS WS `complete` arrives a fixed ~4.03 s after the last audio chunk; `flush` / `max_buffer_flush_ms` don't change it | major | `.venv/bin/python ws_probe.py tts_happy` then `… tts_flush_variants` | `gap last-chunk->complete = ~4020–4032ms` on every run | 12/12 runs, 15:12–15:21; e.g. request_id 0bdfd558-d190-46f3-8a05-848078e2f72a |
| **F4** | TTS WS stays open after `complete`, then sends `{"status":"error","message":"Connection timed out after 60 seconds of inactivity"}` | minor | `.venv/bin/python ws_probe.py tts_happy` | `UNEXPECTED frame after complete: … timed out after 60 seconds` | 6/6, 15:12–15:18; session fe3dcba5-89de-473a-85a9-a9641defeac4 |
| **F3** | 3 or 5 simultaneous TTS requests all return 200 (docs: 1, else 429); the async docs example sends 3 at once with no status check | minor | `./step4_concurrency.sh`, `./step4b_concurrency5.sh` | `grep -P '\tc5?_' evidence/log.tsv`: all 200, totals ≈ a single call | 25/25 × 200, 15:07–15:09; e.g. 8ae9e3c3-9497-4597-800d-ec8574c0c4b6 |
| **F1** | Error bodies come in 5 shapes (3 different 401 bodies, an array for validation, HTML for broken JSON, another shape on WS); no error format documented | minor | `./step3_tts_errors.sh`, `ws_probe.py tts_bad_inputs` | the body column in `log.tsv`; `e_json_broken` is `text/html` | 15:04–15:05; e.g. f1abae03-9abd-45b9-b314-a30c96f3358a (HTML) |
| **F2** | `Content-Type: text/plain` with valid JSON → 400 "Text required" | minor | `./step3_tts_errors.sh` | `e_ctype_text_r*` | 5ecf6811-8a6d-43be-a823-2ff8d047dc14 |
| **F6** | STT WS closes with 1006 after its documented timeout, and 1005 after a validation error | minor | `.venv/bin/python ws_probe.py stt_timeout 10`, `… stt_bad_params` | `CLOSED code=1006` / `code=1005` | 6/6, 15:27, 15:29, 16:19 (×2), 16:39 (×2) |
| **F7** | Bad STT params: `model` → HTTP 400 at handshake, `encoding`/`language` → accepted then an error frame; 3 error shapes; no ID in error frames | minor | `.venv/bin/python ws_probe.py stt_bad_params` | `handshake rejected HTTP 400` vs `recv {"type":"error"…}` | 6/6, 15:27, 15:29, 16:19 (×2), 16:39 (×2) |

## 6. Notes for anyone re-running

- **Timing is location-dependent.** We ran from India, routed to the Mumbai region. Expect different TTFB from elsewhere. The F5 gap (~4 s) is server-side and shouldn't depend on where you run from.
- **F3 depends on how the account's limit is configured.** If Smallest starts enforcing the documented limit, step 4 will show 429s. Then check whether those carry `Retry-After` (step 4's script prints every 429 header).
- **TTS audio length varies by ±12% for the same text.** That's model output, not an engineering issue, and isn't reported.
- **The key never appears in logs.** `probe.sh` records only response headers. Redact the key (`sk_...`) if you paste commands.

## 7. Files

```
run_all.sh                 run every step or chosen ones
view_evidence.py → EVIDENCE.md   readable evidence report built from the raw logs
setup.sh / requirements.txt   one-time venv setup
probe.sh                   curl wrapper → evidence/log.tsv
ws_probe.py                WebSocket tests → evidence/ws.log   (.venv/bin/python ws_probe.py with no args lists them)
step0…step7 *.sh           one script per step (as run for the report)
tts.json, tts_sse.json, payloads/   request bodies (no paste/line-wrap issues)
fetch_docs.sh, docs/       doc snapshot the "Expected" quotes come from
REPORT_NOTES.md            full notes: every finding with all evidence
PLAYBOOK.md                original test plan
```
