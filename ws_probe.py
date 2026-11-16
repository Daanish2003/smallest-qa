"""WebSocket probes for Smallest TTS (/tts/live) and STT (/stt/live).
Run: .venv/bin/python ws_probe.py <test>   (tests listed at bottom)
Every event is printed with IST timestamp + ms since connect, and appended to evidence/ws.log
"""
import asyncio, inspect, json, os, sys, time, datetime, urllib.request
import websockets

def load_key():
    """SMALLEST_API_KEY from the environment, else from .env next to this script (quotes stripped)."""
    if os.environ.get("SMALLEST_API_KEY"):
        return os.environ["SMALLEST_API_KEY"].strip().strip('"').strip("'")
    env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env):
        for line in open(env):
            if line.startswith("SMALLEST_API_KEY="):
                return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("Set SMALLEST_API_KEY or create .env (see .env.example)")
KEY = load_key()
HDR = {"Authorization": f"Bearer {KEY}"}
TTS = "wss://api.smallest.ai/waves/v1/tts/live"
STT = "wss://api.smallest.ai/waves/v1/stt/live"
SAMPLE = "https://github.com/smallest-inc/cookbook/raw/main/speech-to-text/getting-started/samples/audio.wav"
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.makedirs("evidence", exist_ok=True)
T0 = time.monotonic()

def log(test, msg):
    ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
    line = f"{ist:%Y-%m-%d %H:%M:%S.%f}"[:-3] + f" IST +{(time.monotonic()-T0)*1000:7.0f}ms [{test}] {msg}"
    print(line); open("evidence/ws.log", "a").write(line + "\n")

def hdrs(ws):
    """Handshake response headers, minus noisy ones; tolerant of repeated headers like Set-Cookie."""
    return {k: v for k, v in ws.response.headers.raw_items()
            if k.lower() not in ("set-cookie", "content-security-policy")}

def short(m):
    if isinstance(m, bytes): return f"<{len(m)} bytes binary>"
    try:
        d = json.loads(m)
        if isinstance(d.get("data"), dict) and "audio" in d["data"]:
            d["data"]["audio"] = f"<{len(d['data']['audio'])} b64 chars>"
        return json.dumps(d)[:300]
    except Exception: return m[:300]

async def drain(ws, test, until=None, timeout=30):
    """Print every message until `until(msg)` is true, the socket closes, or timeout."""
    try:
        while True:
            m = await asyncio.wait_for(ws.recv(), timeout)
            log(test, "recv " + short(m))
            if until and until(m): return m
    except asyncio.TimeoutError:
        log(test, f"no message for {timeout}s")
    except websockets.ConnectionClosed as e:
        log(test, f"CLOSED code={e.code} reason={e.reason!r}")

def tts_req(text="Hello from the QA test.", **kw):
    return json.dumps({"text": text, "voice_id": "meher", "model": "lightning_v3.1_pro",
                       "sample_rate": 24000, **kw})

def done(m):
    return isinstance(m, str) and '"complete"' in m

# ---------- TTS ----------
async def tts_happy(runs="3", close_wait="60"):
    """3 runs. Docs: chunks {status:'chunk',data.audio}, then terminal {status:'complete'};
    'the server closes the WebSocket after this'. Measures TTFB, chunk count, and whether/when the server closes."""
    for r in range(1, int(runs) + 1):
        tag = f"tts_happy{r}"; t = time.monotonic()
        async with websockets.connect(TTS, additional_headers=HDR) as ws:
            log(tag, f"connected in {(time.monotonic()-t)*1000:.0f}ms; handshake headers={hdrs(ws)}")
            t = time.monotonic(); await ws.send(tts_req()); first = None; chunks = 0; nbytes = 0; last = None
            while True:
                m = await asyncio.wait_for(ws.recv(), 30)
                if first is None: first = (time.monotonic()-t)*1000; log(tag, f"TTFB {first:.0f}ms")
                d = json.loads(m) if isinstance(m, str) else {}
                if d.get("status") == "chunk":
                    chunks += 1; nbytes += len(d.get("data", {}).get("audio", "")) * 3 // 4; last = (time.monotonic()-t)*1000
                    if chunks <= 2: log(tag, "recv " + short(m))
                else: log(tag, "recv " + short(m))
                if done(m): break
            tdone = (time.monotonic()-t)*1000
            log(tag, f"LAST chunk at {last:.0f}ms; complete at {tdone:.0f}ms; gap last-chunk->complete = {tdone-last:.0f}ms")
            log(tag, f"complete after {tdone:.0f}ms; {chunks} chunks, ~{nbytes} PCM bytes "
                     f"(~{nbytes/2/24000:.2f}s at 24kHz 16-bit)")
            tc = time.monotonic()
            try:
                extra = await asyncio.wait_for(ws.recv(), int(close_wait))
                log(tag, f"UNEXPECTED frame after complete: {short(extra)}")
            except asyncio.TimeoutError:
                log(tag, f"server did NOT close within {close_wait}s after complete (state={ws.state.name})")
            except websockets.ConnectionClosed as e:
                log(tag, f"server closed {(time.monotonic()-tc)*1000:.0f}ms after complete: code={e.code} reason={e.reason!r}")
        await asyncio.sleep(2)

async def tts_flush_variants():
    """Is the ~4 s last-chunk -> complete gap a default buffer timer? Try the legacy knobs seen in the SDK example.
    2 runs each: baseline (no knob), flush=true, max_buffer_flush_ms=100."""
    variants = {"baseline": {}, "flush_true": {"flush": True}, "maxflush100": {"max_buffer_flush_ms": 100}}
    for r in (1, 2):
        for name, extra in variants.items():
            tag = f"tts_fv:{name}:{r}"
            async with websockets.connect(TTS, additional_headers=HDR) as ws:
                t = time.monotonic(); await ws.send(tts_req(**extra)); first = last = None; chunks = 0
                try:
                    while True:
                        m = await asyncio.wait_for(ws.recv(), 15)
                        now = (time.monotonic()-t)*1000
                        d = json.loads(m) if isinstance(m, str) else {}
                        if d.get("status") == "chunk":
                            chunks += 1; last = now; first = first or now
                        else:
                            log(tag, f"recv @{now:.0f}ms " + short(m))
                        if d.get("status") in ("complete", "error"): break
                    if last is not None:
                        log(tag, f"first chunk {first:.0f}ms, LAST chunk {last:.0f}ms, end {now:.0f}ms, gap {now-last:.0f}ms, {chunks} chunks")
                except asyncio.TimeoutError:
                    log(tag, f"no frame for 15s (chunks so far {chunks}, last chunk {last}ms)")
            await asyncio.sleep(1)

async def tts_bad_inputs():
    cases = {"not_json": "hello", "empty_text": tts_req(""), "bad_voice": tts_req(voice_id="no_such_voice"),
             "bad_rate": tts_req(sample_rate=12345), "missing_text": json.dumps({"voice_id": "meher"})}
    for name, payload in cases.items():
        try:
            async with websockets.connect(TTS, additional_headers=HDR) as ws:
                await ws.send(payload); await drain(ws, f"tts_bad:{name}", until=lambda m: True, timeout=10)
        except Exception as e: log(f"tts_bad:{name}", f"EXC {type(e).__name__}: {e}")
        await asyncio.sleep(1)

async def tts_no_auth():
    for name, h in {"no_header": {}, "bad_key": {"Authorization": "Bearer sk_invalid"}}.items():
        try:
            async with websockets.connect(TTS, additional_headers=h) as ws:
                await ws.send(tts_req()); await drain(ws, f"tts_auth:{name}", timeout=10)
        except websockets.InvalidStatus as e:
            log(f"tts_auth:{name}", f"handshake rejected HTTP {e.response.status_code} body={e.response.body[:200]!r}")
        except Exception as e: log(f"tts_auth:{name}", f"EXC {type(e).__name__}: {e}")

async def tts_two_sockets():
    """Docs: up to 5 sockets, only 1 request in flight; extras 'rejected with an error'."""
    async def one(i):
        async with websockets.connect(TTS, additional_headers=HDR) as ws:
            await ws.send(tts_req("This sentence is long enough to keep the first request busy for a moment or two."))
            await drain(ws, f"tts_par{i}", until=lambda m: done(m) or '"error"' in str(m), timeout=30)
    await asyncio.gather(*(one(i) for i in range(3)))

async def tts_idle():
    """How long does an idle TTS socket stay open, and how is the close reported?"""
    async with websockets.connect(TTS, additional_headers=HDR) as ws:
        log("tts_idle", "connected, sending nothing")
        await drain(ws, "tts_idle", timeout=900)

# ---------- STT ----------
def sample_pcm():
    path = "evidence/sample.wav"
    if not os.path.exists(path): urllib.request.urlretrieve(SAMPLE, path)
    import wave
    w = wave.open(path); log("stt", f"sample: {w.getframerate()}Hz ch={w.getnchannels()} width={w.getsampwidth()} dur={w.getnframes()/w.getframerate():.2f}s")
    return w.readframes(w.getnframes()), w.getframerate()

def stt_url(**p):
    q = {"model": "pulse", "language": "en", "encoding": "linear16", **p}
    return STT + "?" + "&".join(f"{k}={v}" for k, v in q.items())

async def stream(ws, pcm, rate, chunk_ms=100, realtime=True):
    n = rate * 2 * chunk_ms // 1000
    for i in range(0, len(pcm), n):
        await ws.send(pcm[i:i+n])
        if realtime: await asyncio.sleep(chunk_ms / 1000)

async def stt_happy():
    pcm, rate = sample_pcm()
    async with websockets.connect(stt_url(sample_rate=rate), additional_headers=HDR) as ws:
        log("stt_happy", f"resp headers={hdrs(ws)}")
        rx = asyncio.create_task(drain(ws, "stt_happy", until=lambda m: '"is_last": true' in m or '"is_last":true' in m, timeout=20))
        await stream(ws, pcm, rate); log("stt_happy", "sent all audio, sending close_stream")
        await ws.send(json.dumps({"type": "close_stream"})); await rx

async def stt_wrong_rate():
    pcm, rate = sample_pcm()   # declare 8000 while sending 16k audio; also an invalid rate
    for r in (8000, 12345):
        try:
            async with websockets.connect(stt_url(sample_rate=r), additional_headers=HDR) as ws:
                rx = asyncio.create_task(drain(ws, f"stt_rate{r}", until=lambda m: "is_last" in m and "true" in m, timeout=15))
                await stream(ws, pcm, rate, realtime=False); await ws.send(json.dumps({"type": "close_stream"})); await rx
        except websockets.InvalidStatus as e:
            log(f"stt_rate{r}", f"handshake rejected HTTP {e.response.status_code} body={e.response.body[:200]!r}")

async def stt_bad_params():
    for name, url in {"bad_encoding": stt_url(sample_rate=16000, encoding="mp9"),
                      "bad_model": stt_url(sample_rate=16000, model="nope"),
                      "bad_language": stt_url(sample_rate=16000, language="xx")}.items():
        try:
            async with websockets.connect(url, additional_headers=HDR) as ws:
                await ws.send(b"\x00" * 3200); await drain(ws, f"stt:{name}", timeout=10)
        except websockets.InvalidStatus as e:
            log(f"stt:{name}", f"handshake rejected HTTP {e.response.status_code} body={e.response.body[:200]!r}")

async def stt_keepalive():
    """Docs: {'type':'ping'} returns a pong; aliases keepalive/keep_alive/keep-alive behave the same."""
    async with websockets.connect(stt_url(sample_rate=16000), additional_headers=HDR) as ws:
        for t in ("ping", "keepalive", "keep_alive", "keep-alive"):
            await ws.send(json.dumps({"type": t})); log("stt_ka", f"sent {t}")
            await drain(ws, f"stt_ka:{t}", until=lambda m: True, timeout=5)

async def stt_timeout(seconds="10"):
    """Docs: timeout=<s> sets inactivity limit; server sends
    {"status":"error","message":"Connection timed out after N seconds of inactivity"} then closes."""
    async with websockets.connect(stt_url(sample_rate=16000, timeout=seconds), additional_headers=HDR) as ws:
        log("stt_timeout", f"connected with timeout={seconds}, sending nothing")
        await drain(ws, f"stt_timeout{seconds}", timeout=int(seconds) * 3 + 30)

async def stt_abrupt():
    """Drop the socket mid-stream without close_stream, then reconnect straight away."""
    pcm, rate = sample_pcm()
    ws = await websockets.connect(stt_url(sample_rate=rate), additional_headers=HDR)
    await stream(ws, pcm[: len(pcm)//2], rate); ws.transport.abort(); log("stt_abrupt", "aborted TCP mid-stream")
    t = time.monotonic(); await stt_happy(); log("stt_abrupt", f"reconnect + full transcript took {(time.monotonic()-t)*1000:.0f}ms")

TESTS = {k: v for k, v in globals().items() if k.startswith(("tts_", "stt_")) and inspect.iscoroutinefunction(v)}
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in TESTS: sys.exit("tests: " + " ".join(TESTS))
    asyncio.run(TESTS[sys.argv[1]](*sys.argv[2:]))
