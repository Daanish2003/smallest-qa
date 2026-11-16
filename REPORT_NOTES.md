# Smallest QA — report notes (running log)

Area: **APIs** — TTS (Lightning v3.1 Pro) and STT (Pulse), REST + WebSocket, against docs.smallest.ai.
Tester location: India (IST, UTC+5:30). Tools: curl 8.x via `probe.sh`, Python 3.14 + websockets 17.4 via `ws_probe.py`, jq.
Session start: 2026-11-16 ~13:50 IST (docs reading + tooling).

---

## What is done well

### W1 — Docs quickstart TTS curl works verbatim, returns exactly the requested format
- **Source:** docs `api-reference/authentication` → "Generate speech (Lightning TTS)", copied unchanged.
- **When:** 2026-11-16 14:56:18 IST
- **Result:** HTTP 200, `content-type: audio/wav`, RIFF WAVE PCM 16-bit mono **24000 Hz** (as requested via `sample_rate: 24000`), 84,524 bytes = 1.76 s of audio for "Hello from Smallest AI."
- **Latency:** TTFB 802 ms, total 824 ms (from India, single run).
- **Request ID:** `x-request-id: a7fe4282-0354-44d1-89d0-6fd609a6c4ba` present, and exposed to browsers via `access-control-expose-headers` (`X-Request-Id`) — supports the error-reference advice to quote `x-request-id` in tickets.
- **Evidence files:** `evidence/step1_docs_tts.{hdr,body}`, `evidence/log.tsv`.

### W2 — 401 on missing key is fast and carries a request ID
- **When:** 2026-11-16 13:53:04 IST
- `POST /waves/v1/tts` with no `Authorization` header → **401** in 107 ms, body `{"message":"Unauthorized: No tokens provided"}`, `x-request-id: e145dd63-6e0f-444b-9bf4-697d254d4292`. Matches docs (error-reference: 401 = missing/invalid Authorization).

### W3 — Docs quickstart STT curl works verbatim; response matches the documented example exactly
- **Source:** docs `api-reference/authentication` → "Transcribe audio (Pulse STT)", copied unchanged (run via `step1_stt.sh`).
- **When:** 2026-11-16 15:02:40 IST
- **Result:** HTTP 200, body identical to the documented example: `status: "success"`, transcription "This is a sample audio file for testing speech-to-text transcription with the pulse api.", `words: []`, `utterances: []`, `metadata: {duration: 5.6, fileSize: 268844}`.
- **Latency:** 1.18 s total for 5.6 s of audio fetched by URL (~4.8× faster than real time; includes server-side download from GitHub). Single run.
- **Request ID:** `6533181d-70cd-4342-8e3d-f1e616d98aa6`.
- **Time to first working call (TTS + STT):** _fill in: minutes from opening docs to first 200_.

### Baseline — TTS REST latency, sequential (step 2)
- **When:** 2026-11-16 15:03:34–15:03:40 IST, 3 calls, 2 s apart, payload `tts.json` ("Hello from the QA test.", meher, lightning_v3.1_pro, 24 kHz wav).
- **All 3:** HTTP 200, valid WAV PCM 16-bit mono 24000 Hz, request ID present.

| Run | TTFB | Total | Audio | Request ID |
|---|---|---|---|---|
| 1 | 561 ms | 583 ms | 1.52 s | b5d92d2c-8115-4c0b-a631-df9d90cc58c4 |
| 2 | 585 ms | 607 ms | 1.92 s | 74fdbe74-c700-4001-a356-f65ceb49f4a4 |
| 3 | 602 ms | 624 ms | 1.67 s | 3f07e1bd-3d54-4427-86db-dcf4eaa6eab0 |

- Total latency tight: 583–624 ms (spread 41 ms). Use this as the reference for concurrency/error timing in later steps.

### W4 — TTS REST input validation: correct status codes, field-precise messages, deterministic
- **When:** 2026-11-16 15:04:56–15:05:24 IST, 12 cases × 2 runs = 24 requests (`step3_tts_errors.sh`).
- 24/24 returned the correct class (401 auth, 400 validation); same status on both runs; request ID on every response; all answered in 89–158 ms.
- Validation errors name the field, the received value and the allowed values, e.g. `{"received":"mp9","code":"invalid_enum_value","options":["wav","ulaw","alaw","pcm","mp3"],"path":["output_format"]}`, and `"Voice 'no_such_voice' is not available on the lightning_v3.1_pro model"`. A developer can fix the request from the error alone.

### W5 — SSE streaming halves time-to-first-audio and terminates cleanly
- **When:** 2026-11-16 15:07:18 and 15:07:23 IST, `POST /waves/v1/tts/live` (Accept: text/event-stream), 6 requests (3 at once × 2).
- TTFB 224–286 ms vs 483–582 ms for sync `/tts` with the same text — first audio ~2× sooner. Each stream: 12 `event: audio` chunks, then a terminal `data: {"status":"200","done":true}`, so a client knows unambiguously when the stream is complete.
- Request IDs e.g. fec1f2e6-ed00-491c-835e-c8805a6fb029, 44f25a49-0c80-44d6-9a11-e639b03d4cec.

### W6 — TTS WebSocket: ~155 ms time-to-first-audio, frames match documented envelope
- **When:** 2026-11-16 15:12:29, 15:12:50, 15:13:12 IST (`ws_probe.py tts_happy`, 3 runs, new connection each).
- Connect 123–129 ms; TTFB **153 / 165 / 153 ms** (vs ~500 ms sync REST, ~225 ms SSE — consistent with docs' "~200 ms in-region"). Frames match the documented envelope exactly: `{"session_id","request_id","status":"chunk","data":{"audio":…}}` then `{"status":"complete"}`; `request_id` in every frame (e.g. 0c7ecad0-8eef-4a85-b378-800663cf5256, 7ce4be52-083f-4198-9bd5-fba9891e3d27, b7b953bf-fb18-4a1d-a4c4-094da25e1357).

### W7 — TTS WebSocket fails fast and clearly on bad auth and bad input
- **When:** 2026-11-16 15:14:41–15:15:01 IST (`ws_probe.py tts_no_auth`, `tts_bad_inputs`).
- No key / invalid key → handshake rejected with **HTTP 401** in 97 ms / 272 ms (no half-open socket to clean up).
- 5 bad payloads (non-JSON, empty text, unknown voice, bad sample rate, missing text) → each answered with an error frame in ~160 ms carrying a `request_id` and a field-level reason, e.g. `{"request_id":"a827d786-6fd6-48bf-a95f-b215b4ab1eb8","status":"error","message":"Invalid input data","errors":[{"path":["voice_id"],"message":"Voice 'no_such_voice' is not available on the lightning_v3.1_pro model"}]}`. No hangs, no silent closes.

### W8 — STT WebSocket session lifecycle, keep-alive and timeout behave exactly as documented
- **When:** 2026-11-16 15:26:09–15:27:06 IST (`ws_probe.py stt_happy`, `stt_keepalive`, `stt_timeout 10`).
- **Streaming:** 5.6 s sample streamed in real time (100 ms linear16 chunks, 24 kHz) → partials roughly every 1 s (`is_final:false`), a final segment at 5.3 s, and **68 ms** after `{"type":"close_stream"}` the closing segment with `is_final:true, is_last:true` — as docs `realtime-web-socket/quickstart` describe. Session fae70444-d493-4b03-8d67-0de1391918d5.
- **Keep-alive:** `ping`, `keepalive`, `keep_alive`, `keep-alive` each answered `{"type":"pong"}` in ~30 ms — matches docs `features/keep-alive` ("Three aliases behave identically to `ping`").
- **Timeout:** `timeout=10` → error frame at **10.07 s**, text exactly as documented: `{"status":"error","message":"Connection timed out after 10 seconds of inactivity"}`.

---

## Observations to follow up (not findings yet)

- **O1 — No rate-limit headers on success.** 200 responses have no `X-RateLimit-*` / quota headers. Step 4 produced no 429 to compare against → folded into F3 as supporting detail (customer has no signal of the real limit), not a separate finding.
- **O2 — Same input, different audio length each call.** Identical payload gave 1.52 s / 1.92 s / 1.67 s (±12%). This is model output variance, which the brief says not to judge — **do not report as a finding**. Only relevant if a customer caches by input hash or bills by audio length; mention at most as a note.
- **O4 — Model list in errors ≠ docs.** 400 for a bad model lists `lightning_v3.1`, `lightning_v3.1_pro`, `lightning_v3.1_pro_07_26`, `lightning_v3.1_pro_10_26`; docs (TTS quickstart) mention `_10_26` as preview but never `_07_26`. Also the default `model` differs by page: sync-async table says default `lightning_v3.1`, streaming page says "Picked from `voice_id`". Possible doc-accuracy finding if a request without `model` behaves differently from what a page says — test later if budget allows.

---

## Findings

### F1 — TTS REST error bodies use four different shapes (one is HTML), and no error schema is documented
- **Area:** APIs · **Severity (proposed):** minor
- **Expected:** One documented, machine-readable error envelope for a JSON API, so a client can write one error handler. docs `models/troubleshooting/error-reference` says "Every Waves REST and WebSocket endpoint returns standard HTTP status codes" and lists 401/403/429/500 — but documents **no error body format and no 400 at all**.
- **Observed:** Status codes were right, but on the same endpoint (`POST /waves/v1/tts`) bodies came in 4 shapes, identical on both runs:

| Case | Status | Content-Type | Body |
|---|---|---|---|
| no Authorization header | 401 | application/json | `{"message":"Unauthorized: No tokens provided"}` |
| invalid key `sk_invalid0000` | 401 | application/json | `{"error":"unauthorized"}` |
| key without `Bearer ` | 401 | application/json | `{"error":"No token provided"}` |
| any validation error (8 cases) | 400 | application/json | `{"error":[{"code":…,"path":[…],"message":…}]}` (array) |
| malformed JSON `{"text":` | 400 | **text/html** | `<!DOCTYPE html>…<pre>Bad Request</pre>…` |

  Three 401s for the same class of problem give three different bodies (`message` string vs `error` string, different wording).
  **Across transports** the same validation error has a 5th shape: TTS WebSocket returns `{"request_id":…,"status":"error","message":"Invalid input data","errors":[{path,message}]}` (2026-11-16 15:14:59 IST, rid a827d786-6fd6-48bf-a95f-b215b4ab1eb8) vs REST `{"error":[{path,message}]}` for the identical bad `voice_id` (rid d0bd10e0-4216-405f-acdf-fd41df9649cd). A shared client library needs two parsers.
- **Evidence:** `./step3_tts_errors.sh` (each case 2×, sequential, 1 s apart), 2026-11-16 15:04:56–15:05:24 IST. Request IDs: no-key 512eac1d-db98-4c2a-bff3-80b2f3229af5 / 33786f4b-8031-4eeb-9059-774e2059521e; bad key 0810434a-3c90-4eb6-804e-2e7c8d1b3465 / 88aeef76-97ec-4b49-99ee-5cc054293c80; no-Bearer 94ecfd6e-4350-4940-8915-bbc2da85867d / 1eaa3beb-081a-4a03-a7b8-67b19d8713e4; HTML 400 f1abae03-9abd-45b9-b314-a30c96f3358a / 7f101858-9eb8-431a-a7a0-03582b5d203d; validation e.g. d0bd10e0-4216-405f-acdf-fd41df9649cd.
- **Customer impact:** A client that parses `body.error.message` (or `body.message`) gets `undefined` on most paths; a client that calls `response.json()` on every non-2xx throws a parse exception on the HTML 400, so the real cause (bad JSON from the customer's own serializer) is masked by a second error in their logs. Doesn't break the success-rate SLO directly, but raises time-to-diagnose for every integration error and makes automated alerting on error codes unreliable.

### F2 — Wrong Content-Type is reported as missing fields
- **Area:** APIs · **Severity (proposed):** minor
- **Expected:** A request with an unsupported `Content-Type` gets 415 (or a 400 that says the content type is wrong).
- **Observed:** Valid JSON body (`tts.json`, which contains `text` and `voice_id`) sent with `Content-Type: text/plain` → 400 `{"error":[{"path":["text"],"message":"Text required"},{"path":["voice_id"],"message":"Required"}]}` — tells the developer fields are missing when they are present. 2/2 runs.
- **Evidence:** 2026-11-16 15:05:08 and 15:05:23 IST, request IDs 5ecf6811-8a6d-43be-a823-2ff8d047dc14, 098d2c9a-02ad-4ce0-8f66-70f7c8a14e63.
- **Customer impact:** Common with HTTP clients that default to `text/plain` or form encoding (e.g. some low-code tools, `fetch` with a string body and no header). Developer debugs their payload instead of the header; slows time-to-first-call. Low severity — easy workaround once understood.
- **Same pattern on WebSocket:** `{"text":"","voice_id":"meher",…}` → `"text and voice_id are required unless cancel_request, flush or context_close is true…"` although `voice_id` was present (2026-11-16 15:14:58 IST, rid d4015bdb-a51d-40de-8f85-9111df3de923). REST names only `text` ("Text cannot be empty") for the same input.

### F3 — Documented TTS concurrency limit (1, else 429) is not what the API does (≥5 accepted), and the docs contradict themselves
- **Area:** APIs · **Severity (proposed):** minor (doc accuracy / capacity planning) — see impact
- **Expected:** docs `api-reference/concurrency-and-limits`: "**1 TTS request concurrency**: Only 1 Text-to-Speech request can be actively processed at a time per account … This applies to every Lightning v3.1 TTS endpoint (sync, SSE, WebSocket)" and "If you attempt to make a second HTTP request while one is already being processed, you'll receive a `429 Too Many Requests` error".
- **Observed:** 3 simultaneous requests, 5 rounds (3 × sync `/tts`, 2 × SSE `/tts/live`): **15/15 returned 200, 0 × 429**. The requests genuinely overlapped: each round's 3 requests started in the same second and each finished in 0.51–0.60 s (sync) / 0.48–0.56 s (SSE) — the same as a single uncontended call (0.58–0.62 s in step 2). Serialised processing would have pushed the 3rd to ~1.5 s. No rate-limit/concurrency headers on any response.
- **Docs contradict each other:** `models/text-to-speech/sync-async` → "Asynchronous Text to Speech" shows an official example firing **3 concurrent requests** via `asyncio.gather`, with no `resp.status` check, writing the response bytes straight to `.wav`. Under the limit stated on the limits page, 2 of 3 files would silently be 429 JSON bodies saved as `.wav`.
- **Evidence:** `./step4_concurrency.sh`, 2026-11-16 15:07:01–15:07:23 IST. Request IDs (round 1 sync): 58b93f71-2456-4a95-a7cf-c81c565b80a3, 385af95b-14e6-4cea-a0ec-aeb13ead9d3a, b07edf25-6864-41cc-adac-cdc3f8ba6aeb; (round 1 SSE): bbcfe10d-2c8a-4cf4-abf7-71ca7602d17b, 2d388dd9-98a4-4760-80e6-59d9ce3f0c01, fec1f2e6-ed00-491c-835e-c8805a6fb029. Full set in `evidence/log.tsv` (labels `c_*`).
- **Customer impact:** A customer cannot plan capacity from the docs. Either (a) they trust the limits page and build a single-slot queue in front of TTS, adding ~0.5 s of queueing per extra concurrent utterance — e.g. a voice bot whose 3rd simultaneous reply waits ~1.2 s, blowing a typical 800 ms p95 time-to-first-audio SLO for no reason; or (b) they observe what we observed, ship parallel calls, and get unannounced 429s in production when the real (undocumented) limit is reached or the documented one starts being enforced — the sync-async example would then write error bodies into audio files without any error raised.
- **Bound on real limit (step 4b):** 5 simultaneous sync requests × 2 rounds (2026-11-16 15:09:44 and 15:09:55 IST, `./step4b_concurrency5.sh`): **10/10 returned 200**, totals 0.49–0.68 s (single uncontended call: 0.58–0.62 s) — no queueing, no 429. Real limit is **≥5, i.e. ≥5× the documented 1**; not tested higher because the assessment caps us at ~5 concurrent. Request IDs: 8ae9e3c3-9497-4597-800d-ec8574c0c4b6, 20369cbf-a16f-475c-a0c7-d4cedcd1f569, 00deb696-a471-40af-b694-2b5cccd986f2, 16d9e63e-4b35-4a20-874d-f7d7a9156152, e27b9459-a95f-4288-98b0-ba34257e3ecb (round 1); d0df8267-7831-47bf-b2bd-c1e0f0332ce3 … 714d20c1-a2e6-4b82-86c8-a903284acad2 (round 2).
- **Totals across steps 4 + 4b:** 25 overlapping requests in 7 rounds (3- and 5-wide; sync and SSE), 25/25 × 200, 0 × 429.
- **Side effect:** because no 429 could be produced within the brief's limits, the 429 path (body shape, `Retry-After`, request ID) is **untestable for a customer on a small account** — the docs' backoff guidance can't be verified before production.

---

### F4 — TTS WebSocket: `complete` is not terminal; a successful session ends 60 s later with an error frame (undocumented timeout)
- **Area:** APIs · **Severity (proposed):** minor
- **Expected:** docs `models/text-to-speech/streaming` → Response Format: `// stream complete (terminal frame; the server closes the WebSocket after this)`; `models/text-to-speech/continuations` repeats that for "a plain non-continuation request … `complete` is terminal". No TTS WebSocket idle timeout is documented anywhere (the only documented one is STT's 20 min).
- **Observed:** 6/6 plain requests (one sentence, no `context_id`/`continue`/`flush`): socket still OPEN after `complete` (run 1: checked for 15 s, 3/3). Run 2 waited 60 s: in 3/3 the server sent, exactly 60 s after `complete`, `{"status":"error","message":"Connection timed out after 60 seconds of inactivity"}` — i.e. every successful synthesis ends with an **error-status** frame.
- **Evidence:** `.venv/bin/python ws_probe.py tts_happy` (runs: 2026-11-16 15:12:29–15:13:31 IST and 15:15:53–15:18:57 IST). Request IDs (run 2): from frames — see `evidence/ws.log` lines `[tts_happy1..3]`; `complete` at 15:15:57.787 → timeout error 15:16:53.333; 15:16:59.870 → 15:17:55.487; 15:18:02.116 → 15:18:57.636 (all ≈ 55.5 s after our log line, 60 s after the last server frame). Session IDs (run 1): fe3dcba5-89de-473a-85a9-a9641defeac4, 2561fcc2-7eff-4abf-b7f5-a63c0a1348ed, 8f4954bf-51ab-4ede-bc89-e3956bf788a2.
- **Caveat to own:** docs `streaming` comparison table also says WebSocket is for "Multiple messages: Reuse same connection", so keeping the socket open may be intended and the "server closes" line may be the error. Either way: docs contradict each other, the 60 s idle timeout is undocumented, and a normal idle end is reported as `status:"error"`. Not tested: a 2nd request on the same socket.
- **Customer impact:** A client written to the docs (`async for msg in ws` until the server closes, or `await ws.wait_closed()`) blocks for 60 s after every utterance, then sees `status:"error"` and — if it alerts or retries on error frames — logs a false failure for every successful request (100% false-error rate against an error-rate SLO). Lingering sockets also hold the documented 5-connection budget for a minute each, so a bot doing one utterance every ~12 s or faster can exhaust it.

### F5 — TTS WebSocket: `complete` arrives a fixed ~4.03 s after the last audio chunk
- **Area:** APIs · **Severity (proposed):** major
- **Expected:** For a plain (non-continuation) request `complete` is the terminal frame (docs streaming → Response Format; continuations → "Unlike a plain non-continuation request … where `complete` is terminal"). Docs do not mention any wait before `complete`; the timer-based buffer knobs (`flush`, `max_buffer_flush_ms`) are not in the streaming parameter table — `max_buffer_flush_ms` only appears inside an SDK example.
- **Observed:** All audio arrives within ~0.5 s, then nothing for ~4 s, then `complete`. The gap is constant regardless of audio length:

| Run (2026-11-16 IST) | TTFB | Last chunk | `complete` | Gap | Audio |
|---|---|---|---|---|---|
| 15:15:53 | 169 ms | 454 ms | 4486 ms | **4032 ms** | 1.71 s |
| 15:16:55 | 155 ms | 389 ms | 4414 ms | **4025 ms** | 1.60 s |
| 15:17:57 | 153 ms | 481 ms | 4511 ms | **4030 ms** | 1.61 s |

  Earlier batch (15:12:29, 15:12:50, 15:13:12): `complete` at 4433 / 4470 / 4466 ms with TTFB 153–165 ms — same pattern (6/6). Spread of the gap 4025–4032 ms (±4 ms) → looks like a fixed server-side timer, not synthesis time.
- **Evidence:** `.venv/bin/python ws_probe.py tts_happy` — `evidence/ws.log` lines "LAST chunk at … gap last-chunk->complete". Payload `{"text":"Hello from the QA test.","voice_id":"meher","model":"lightning_v3.1_pro","sample_rate":24000}`.
- **Customer impact:** `complete` is the only end-of-stream signal on the WebSocket (docs: "Detect completion with `msg["status"] == "complete"`"). A client that plays audio as it streams finishes playback at ≈ TTFB + audio length ≈ 0.15 + 1.6 = **~1.8 s**, but `complete` arrives at **~4.45 s** — so a voice agent that waits for `complete` before ending the bot's turn (switching to listen mode, enabling barge-in, sending the next utterance) adds **~2.6–2.9 s of dead air per turn** on a one-sentence reply. Against a typical voice-agent SLO of < 1 s response latency, 12/12 turns miss. It undercuts the headline ~155 ms TTFB: fast to start, slow to finish. (Only one-sentence inputs were tested; the constant 4.02–4.03 s gap suggests a fixed timer, so the extra wait relative to audio is largest on short replies — the common case in conversation.)
- **No client-side workaround (root-cause probe):** `.venv/bin/python ws_probe.py tts_flush_variants`, 2026-11-16 15:20:29–15:21:02 IST, same payload with the legacy buffer knobs (the SDK example in docs streaming uses `max_buffer_flush_ms=100`). Both knobs are **accepted silently (no validation error) and have no effect**:

| Variant | Gap run 1 | Gap run 2 | request_id (run 1 / run 2) |
|---|---|---|---|
| none | 4026 ms | 4024 ms | 0bdfd558-d190-46f3-8a05-848078e2f72a / 4db7a5ea-a5bc-43ad-b9b0-39920ea76e9c |
| `"flush": true` | 4022 ms | 4020 ms | 4862d158-1e99-4fdf-9c57-2d9cf593687c / e6b5eaee-afb7-4183-9b0c-4db1009858d1 |
| `"max_buffer_flush_ms": 100` | 4029 ms | 4018 ms | 639bc24d-89d2-4711-b210-5877cf80eaea / 87073590-a24d-4f13-bfef-c55f87330d4d |

- **Totals:** 12/12 plain WebSocket requests across 3 sessions (15:12, 15:15, 15:20 IST) show the gap; range **4018–4032 ms**. A customer cannot shorten it with any documented or SDK-exampled option; the only workaround is to ignore `complete` and guess end-of-audio from silence/chunk timing, which the docs explicitly steer away from.

### F6 — STT WebSocket closes without a proper close code: 1006 after the documented timeout, 1005 after a validation error
- **Area:** APIs · **Severity (proposed):** minor
- **Expected:** docs `features/keep-alive`: on inactivity timeout "the server sends `{"status":"error",…}` and terminates the socket". RFC 6455 clients distinguish a deliberate server close (close frame with a code, e.g. 1000/1008/1011 or 4xxx) from a network failure (1006). A customer expects a policy/timeout close to arrive as a close frame with a meaningful code.
- **Observed:** 6/6 runs, identical — 2026-11-16 15:27 and 15:29 IST, repeated 16:19:42, 16:19:53, 16:39:42 and 16:39:52 IST:
  - `timeout=10`, no audio → error frame at 10.07 s, then **close 1006** (abnormal closure: no close frame, TCP dropped). 2026-11-16 15:27:06 and 15:29:39 IST.
  - `encoding=mp9` or `language=xx` → error frame, then **close 1005** (close frame with no status code). 15:27:30 and 15:29:58 IST.
- **Evidence:** `.venv/bin/python ws_probe.py stt_timeout 10` and `.venv/bin/python ws_probe.py stt_bad_params`, run twice; `evidence/ws.log` lines `[stt_timeout10] CLOSED code=1006`, `[stt:bad_encoding] CLOSED code=1005`, `[stt:bad_language] CLOSED code=1005`. URL: `wss://api.smallest.ai/waves/v1/stt/live?model=pulse&language=en&encoding=linear16&sample_rate=16000&timeout=10`.
- **Customer impact:** Most client libraries (browser `WebSocket`, Python `websockets`, `ws` in Node) surface 1006 as a connection failure. Reconnect-with-backoff logic — which the STT troubleshooting page itself recommends — will treat every documented idle timeout as an outage and reconnect into another idle session, and monitoring will count it against a connection-success SLO. 1005 on a config error means a client cannot tell "your parameters are wrong, don't retry" from a clean close by code alone; it must parse the preceding text frame, whose shape differs by case (see F7).

### F7 — STT WebSocket: invalid query parameters fail three different ways, and error frames carry no session or request ID
- **Area:** APIs · **Severity (proposed):** minor
- **Expected:** Invalid connection parameters rejected consistently (ideally at the handshake, as `model` is), in one error shape, with an identifier — docs `troubleshooting/error-reference` asks customers to quote `x-request-id` in every ticket.
- **Observed:** 6/6 runs, identical (2026-11-16 15:27:30, 15:29:58, 16:19:43, 16:19:54, 16:39:42 and 16:39:53 IST):

| Bad parameter | Handshake | What the client gets | Close |
|---|---|---|---|
| `model=nope` | **HTTP 400** | `{"status":"error","error_code":"INVALID_MODEL","message":"Invalid model query parameter: nope. Supported: pulse, pulse-2."}` | — |
| `encoding=mp9` | **101 accepted** | `{"type":"error","message":"Invalid input data","error":"Invalid enum value. Expected 'linear16' \| 'linear32' \| 'alaw' \| 'mulaw' \| 'opus' \| 'ogg_opus', received 'mp9'"}` | 1005 |
| `language=xx` | **101 accepted** | same shape as encoding, listing valid languages | 1005 |
| (idle timeout) | 101 | `{"status":"error","message":"Connection timed out after 10 seconds of inactivity"}` | 1006 |

  Three shapes (`status/error_code/message`, `type/message/error`, `status/message`); discriminator is `status` in one and `type` in another. **No `session_id` or request ID** in any STT error frame (success frames do carry `session_id`, e.g. fae70444-d493-4b03-8d67-0de1391918d5), and the WebSocket handshake response has no `x-request-id` header.
- **Customer impact:** A client must handle three error formats and two failure points (handshake vs first frame) for what is one class of mistake. The validation messages themselves are good (they list valid values), but when an STT session fails in production the customer has nothing to quote in a support ticket, so a failed transcription can't be traced server-side — directly lengthening time-to-resolution for any STT incident.

## Time log
| Start (IST) | End (IST) | What |
|---|---|---|
| 13:50 | 15:03 | Docs reading, tooling setup, step 0, step 1 (TTS + STT docs examples) |
| 15:03 | 15:04 | Step 2 TTS baseline (3 runs) |
| 15:04 | 15:15 | Step 3 TTS REST error semantics (24 requests) + analysis |
| 15:07 | 15:25 | Step 4 TTS concurrency (15 requests) + docs cross-check |
| 15:09 | 15:30 | Step 4b 5-concurrent (10 requests), finalise F3 |
| 15:12 | 15:40 | Step 5 TTS WebSocket (happy ×6, auth, bad inputs) + F4/F5 |
| 15:20 | 15:45 | F5 root-cause probe (flush variants ×6) |
| 15:26 | 15:50 | Step 7 STT WebSocket (happy, keep-alive, timeout, bad params) |
| 15:29 | 15:55 | Step 7 repeat runs, finalise F6/F7 |
