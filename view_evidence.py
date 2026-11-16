#!/usr/bin/env python3
"""Turn evidence/log.tsv (REST) and evidence/ws.log (WebSocket) into a readable EVIDENCE.md.

Usage:  python3 view_evidence.py            -> writes EVIDENCE.md
        python3 view_evidence.py --stdout   -> prints it instead
Standard library only. Safe to re-run any time; it only reads the logs.
"""
import json, os, re, sys
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "evidence", "log.tsv")
WSLOG = os.path.join(HERE, "evidence", "ws.log")
OUT = os.path.join(HERE, "EVIDENCE.md")


def cell(s, n=None):
    s = str(s).replace("|", "\\|").replace("\n", " ")
    return s if n is None or len(s) <= n else s[: n - 1] + "…"


def ms(x):
    try:
        return f"{float(x) * 1000:.0f}"
    except ValueError:
        return x


def body_summary(b, label=""):
    """Short human-readable version of a response body."""
    if b.startswith("event:"):  # SSE stream: summarise from the saved body file
        try:
            txt = open(os.path.join(HERE, "evidence", label + ".body"), encoding="utf-8").read()
            n = txt.count("event: audio")
            end = "ends with `{\"status\":\"200\",\"done\":true}`" if '"done":true' in txt else "**no done:true terminator**"
            return f"*SSE stream: {n} audio events, {end}*"
        except OSError:
            return "*SSE stream*"
    if b.startswith("<") and b.endswith(">"):
        return f"*{b[1:-1]} body*"
    if b.lstrip().startswith("<!DOCTYPE"):
        return "**HTML page**: `<pre>Bad Request</pre>`"
    try:
        d = json.loads(b)
    except ValueError:
        return f"`{cell(b, 110)}` *(truncated)*"
    if isinstance(d.get("error"), list):
        parts = [f"{'.'.join(map(str, e.get('path', [])))}: {e.get('message', '')}" for e in d["error"]]
        return "`{\"error\":[…]}` → " + cell("; ".join(parts), 110)
    return f"`{cell(json.dumps(d, separators=(',', ':')), 110)}`"


# ---------- REST ----------
def full_body(label, logged):
    """log.tsv keeps only 200 chars of the body; use the saved .body file when it is text."""
    if logged.startswith("<") and logged.endswith(">"):
        return logged  # binary (audio) — keep the <content-type> marker
    path = os.path.join(HERE, "evidence", label + ".body")
    try:
        txt = open(path, encoding="utf-8").read()
        return txt if len(txt) < 5000 else logged
    except (OSError, UnicodeDecodeError):
        return logged

def read_rest():
    rows = []
    if not os.path.exists(LOG):
        return rows
    for line in open(LOG, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if len(f) < 9:
            continue
        rows.append(dict(time=f[0].replace(" IST", ""), label=f[1], status=f[2], ttfb=ms(f[3]), total=ms(f[4]),
                         size=f[5], rid=f[6].replace("rid=", ""), retry=f[7].replace("retry-after=", ""),
                         body=full_body(f[1], f[8] if len(f) > 8 else "")))
    return rows


STEP3_EXPECT = OrderedDict([
    ("auth_none", ("no Authorization header", "401", "W4, F1")),
    ("auth_bad", ("invalid key `sk_invalid0000`", "401", "W4, F1")),
    ("auth_nobearer", ("key without `Bearer `", "401", "W4, F1")),
    ("json_broken", ("malformed JSON `{\"text\":`", "400", "F1 (HTML)")),
    ("text_missing", ("no `text` field", "400", "W4, F1")),
    ("text_empty", ("`text: \"\"`", "400", "W4, F1")),
    ("text_wrongtype", ("`text: 12345`", "400", "W4, F1")),
    ("voice_bad", ("unknown `voice_id`", "400", "W4, F1")),
    ("model_bad", ("unknown `model`", "400", "W4, F1")),
    ("rate_bad", ("`sample_rate: 12345`", "400", "W4, F1")),
    ("format_bad", ("`output_format: mp9`", "400", "W4, F1")),
    ("ctype_text", ("valid JSON sent as `text/plain`", "400/415", "F2")),
])


def rest_simple_table(rows, note=""):
    out = ["| Time (IST) | Test | HTTP | TTFB ms | Total ms | Bytes | Request ID | Response |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['time'][11:]} | `{r['label']}` | **{r['status']}** | {r['ttfb']} | {r['total']} | {r['size']} "
                   f"| `{r['rid']}` | {body_summary(r['body'], r['label'])} |")
    return out + ([note] if note else [])


def rest_section(rows):
    out = ["## Part A — REST (`evidence/log.tsv`)", ""]
    by = lambda pred: [r for r in rows if pred(r["label"])]

    s0 = by(lambda l: l == "smoke_noauth")
    if s0:
        out += ["### Step 0 — No API key → 401  ·  *evidence for W2*", "",
                "`POST /waves/v1/tts` with no `Authorization` header. Expect a fast 401 with a clear message.", ""]
        out += rest_simple_table(s0) + [""]

    s1 = by(lambda l: l.startswith("step1_"))
    if s1:
        out += ["### Step 1 — Docs quickstart examples, copied verbatim  ·  *W1 (TTS), W3 (STT)*", ""]
        out += rest_simple_table(s1) + [""]

    s2 = by(lambda l: l.startswith("tts_ok_"))
    if s2:
        tot = [float(r["total"]) for r in s2]
        out += ["### Step 2 — Baseline: 3 sequential TTS calls  ·  *latency reference for step 4*", ""]
        out += rest_simple_table(s2)
        out += ["", f"> Total latency {min(tot):.0f}–{max(tot):.0f} ms. A single uncontended call takes ~0.6 s — "
                    "step 4 compares against this.", ""]

    s3 = by(lambda l: l.startswith("e_"))
    if s3:
        runs = defaultdict(dict)
        for r in s3:
            m = re.match(r"e_(.+)_r(\d+)$", r["label"])
            if m:
                runs[m.group(1)][m.group(2)] = r
        out += ["### Step 3 — TTS REST error semantics (12 cases × 2 runs)  ·  *W4, F1, F2*", "",
                "Each bad request sent twice, 1 s apart. Look at: is the status right, is it the same both runs, "
                "and does the **shape** of the body stay the same across cases (it doesn't → F1).", "",
                "| Case | What was sent | Expected | Run 1 | Run 2 | Same? | Response body (run 1) | Evidence for |",
                "|---|---|---|---|---|---|---|---|"]
        for case, (desc, exp, tag) in STEP3_EXPECT.items():
            if case not in runs:
                continue
            r1, r2 = runs[case].get("1"), runs[case].get("2")
            s1_, s2_ = (r1 or {}).get("status", "–"), (r2 or {}).get("status", "–")
            same = "✅" if r1 and r2 and r1["status"] == r2["status"] and r1["body"] == r2["body"] else "⚠️"
            out.append(f"| {case} | {desc} | {exp} | **{s1_}** | **{s2_}** | {same} | {body_summary((r1 or r2)['body'])} | {tag} |")
        out += ["", "<details><summary>Request IDs and timings for every step-3 request</summary>", ""]
        out += rest_simple_table(s3) + ["", "</details>", ""]

    for prefix, title in (("c_", "### Step 4 — 3 TTS requests at once (docs: only 1 allowed, the rest → 429)  ·  *F3*"),
                          ("c5_", "### Step 4b — 5 TTS requests at once (the brief's maximum)  ·  *F3*")):
        s4 = by(lambda l, p=prefix: l.startswith(p) and not (p == "c_" and l.startswith("c5_")))
        if not s4:
            continue
        rounds = OrderedDict()
        for r in s4:
            m = re.match(r"(c5?_(?:sync_|sse_)?r\d+)_\d+$", r["label"])
            rounds.setdefault(m.group(1) if m else r["label"], []).append(r)
        out += [title, "",
                "All requests in a round are fired together. If the server ran only one at a time, the last one in a "
                "round would take ~N × 0.6 s. Equal totals = truly parallel.", "",
                "| Round | Endpoint | Started (IST) | Statuses | Total ms (each) | 429s |", "|---|---|---|---|---|---|"]
        n200 = n429 = 0
        for name, rs in rounds.items():
            ep = "SSE `/tts/live`" if "sse" in name else "sync `/tts`"
            sts = [r["status"] for r in rs]
            n200 += sts.count("200"); n429 += sts.count("429")
            out.append(f"| `{name}` | {ep} | {rs[0]['time'][11:]} | {' '.join(sts)} | "
                       f"{', '.join(r['total'] for r in rs)} | {sts.count('429')} |")
        out += ["", f"> **{n200} × 200, {n429} × 429.** Docs say a 2nd concurrent request gets 429.", "",
                "<details><summary>Request IDs</summary>", ""] + rest_simple_table(s4) + ["", "</details>", ""]
    return out


# ---------- WebSocket ----------
WS_RE = re.compile(r"^(\S+ \S+) IST \+\s*(\d+)ms \[([^\]]+)\] (.*)$")

WS_GROUPS = [  # (tag regex, title, explanation)
    (r"^tts_happy\d", "Step 5 — TTS WebSocket happy path  ·  *W6, F4, F5*",
     "One sentence per connection. Docs: chunks, then `complete`, then *“the server closes the WebSocket”*. "
     "Watch **LAST chunk → complete gap** (F5) and what happens after `complete` (F4)."),
    (r"^tts_fv:", "Step 5 — F5 root cause: does `flush` / `max_buffer_flush_ms` remove the ~4 s gap?  ·  *F5*",
     "Same sentence with no option, `flush:true`, and `max_buffer_flush_ms:100` (from the SDK example)."),
    (r"^tts_auth:", "Step 5 — TTS WebSocket with no key / bad key  ·  *W7*", "Expect rejection at the handshake."),
    (r"^tts_bad:", "Step 5 — TTS WebSocket bad inputs  ·  *W7, F1, F2*",
     "Expect a clear error frame, not a hang or silent close. Compare the shape with REST step 3 (F1)."),
    (r"^stt_happy|^stt$", "Step 7 — STT WebSocket happy path  ·  *W8*",
     "5.6 s sample streamed in real time, then `close_stream`. Docs: final message has `is_last: true`."),
    (r"^stt_ka", "Step 7 — STT keep-alive aliases  ·  *W8*",
     "Docs: `ping`, `keepalive`, `keep_alive`, `keep-alive` all behave identically (→ `pong`)."),
    (r"^stt_timeout", "Step 7 — STT inactivity timeout (`timeout=10`)  ·  *W8, F6*",
     "Docs: error message *“Connection timed out after N seconds of inactivity”*, then socket terminated. Watch the **close code**."),
    (r"^stt:", "Step 7 — STT bad connection parameters  ·  *F6, F7*",
     "Bad `encoding`, `model`, `language`. Watch **where** it fails (handshake vs after) and the **error shape**."),
]


def ws_event(msg):
    """Make one WS log message readable."""
    m = re.match(r"recv (?:@(\d+)ms )?(\{.*)$", msg)
    if m:
        try:
            d = json.loads(m.group(2))
        except ValueError:  # ws.log truncates long frames at 300 chars
            return f"`{cell(m.group(2), 170)}`"
        st = d.get("status") or d.get("type")
        if st == "chunk":
            return f"audio chunk ({d.get('data', {}).get('audio', '')})"
        if d.get("type") == "transcription":
            flags = f"is_final={str(d.get('is_final')).lower()}, is_last={str(d.get('is_last')).lower()}"
            return f"transcript “{d.get('transcript', '').strip()}” ({flags})"
        keep = {k: v for k, v in d.items() if k not in ("session_id",)}
        if isinstance(keep.get("errors"), list):
            keep["errors"] = [e.get("message") for e in keep["errors"]]
        return f"`{cell(json.dumps(keep, ensure_ascii=False), 170)}`"
    msg = re.sub(r"handshake headers=\{.*\}", "", msg)
    msg = re.sub(r"resp headers=\{.*\}", "connected", msg)
    msg = msg.replace("bytearray(b'", "").replace("')", "")
    for k, v in (("LAST chunk", "**LAST chunk"), ("gap last-chunk->complete", "gap last-chunk→complete"),
                 ("CLOSED code=", "**CLOSED code="), ("did NOT close", "**did NOT close"),
                 ("UNEXPECTED frame after complete", "**frame after complete**")):
        msg = msg.replace(k, v)
    if msg.count("**") % 2:
        msg += "**"
    return cell(msg, 200)


def ws_section():
    out = ["## Part B — WebSocket (`evidence/ws.log`)", "",
           "`+ms` = milliseconds since that test's start (monotonic clock on the client).", ""]
    if not os.path.exists(WSLOG):
        return out + ["*(no ws.log yet)*"]
    events = []
    for line in open(WSLOG, encoding="utf-8"):
        m = WS_RE.match(line.rstrip("\n"))
        if m:
            events.append(dict(time=m.group(1)[11:], plus=int(m.group(2)), tag=m.group(3), msg=m.group(4)))
    for rx, title, expl in WS_GROUPS:
        ev = [e for e in events if re.search(rx, e["tag"])]
        if not ev:
            continue
        out += [f"### {title}", "", expl, ""]
        if rx.startswith(r"^tts_happy") or rx.startswith(r"^tts_fv"):
            out += ws_summary(ev) + [""]
        out += ["<details><summary>Full event log</summary>", "" ] if rx.startswith((r"^tts_happy", r"^tts_fv")) else []
        out += ["| Time (IST) | +ms | Test | Event |", "|---|---|---|---|"]
        for e in ev:
            out.append(f"| {e['time']} | {e['plus']} | `{e['tag']}` | {ws_event(e['msg'])} |")
        out += ["", "</details>", ""] if rx.startswith((r"^tts_happy", r"^tts_fv")) else [""]
    return out


def ws_summary(ev):
    """One row per TTS session: TTFB, last chunk, complete, gap, what happened after."""
    rows, cur = [], None
    for e in ev:
        t = e["tag"]
        if cur is None or cur["tag"] != t or (cur.get("done") and "connected" in e["msg"]):
            cur = dict(tag=t, start=e["time"], ttfb="", last="", complete="", gap="", after="", rid=""); rows.append(cur)
        m = re.search(r"TTFB (\d+)ms", e["msg"]);                       cur["ttfb"] = m.group(1) if m else cur["ttfb"]
        m = re.search(r"first chunk (\d+)ms, LAST chunk (\d+)ms, end (\d+)ms, gap (\d+)ms", e["msg"])
        if m: cur.update(ttfb=m.group(1), last=m.group(2), complete=m.group(3), gap=m.group(4))
        m = re.search(r"LAST chunk at (\d+)ms; complete at (\d+)ms; gap last-chunk->complete = (\d+)ms", e["msg"])
        if m: cur.update(last=m.group(1), complete=m.group(2), gap=m.group(3))
        m = re.search(r"complete after (\d+)ms", e["msg"]);              cur["complete"] = cur["complete"] or (m.group(1) if m else "")
        m = re.search(r'"request_id": "([^"]+)"', e["msg"]);             cur["rid"] = cur["rid"] or (m.group(1) if m else "")
        if "did NOT close" in e["msg"]: cur["after"] = "still OPEN (" + re.search(r"within (\d+s)", e["msg"]).group(1) + ")"; cur["done"] = True
        if "UNEXPECTED frame" in e["msg"]: cur["after"] = "error frame: *timed out after 60 s*"; cur["done"] = True
        if "server closed" in e["msg"]: cur["after"] = cell(e["msg"], 60); cur["done"] = True
    out = ["| Session | Started (IST) | TTFB ms | Last chunk ms | `complete` ms | **Gap ms** | After `complete` | request_id |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| `{r['tag']}` | {r['start']} | {r['ttfb']} | {r['last'] or '–'} | {r['complete']} | **{r['gap'] or '–'}** "
                   f"| {r['after'] or '–'} | `{r['rid']}` |")
    gaps = [int(r["gap"]) for r in rows if r["gap"]]
    if gaps:
        out += ["", f"> Gap from last audio to `complete`: **{min(gaps)}–{max(gaps)} ms over {len(gaps)} sessions** (F5)."]
    if any(not r["gap"] and r["complete"] for r in rows):
        out += ["> Sessions with “–” are the first batch (15:12–15:13), run before the last-chunk timestamp was added and with "
                "a 15 s wait after `complete`; their `complete` still lands at ~4.45 s with TTFB ~155 ms."]
    return out


def main():
    rest = read_rest()
    doc = ["# Evidence — Smallest AI API QA", "",
           "Generated by `python3 view_evidence.py` from `evidence/log.tsv` and `evidence/ws.log`. "
           "Times are IST (Asia/Kolkata). IDs: W = done well, F = finding (see `REPRODUCE.md` for what each one is "
           "and the command that reproduces it).", "",
           "**How to read it:** each section is one test step. The heading says what it is evidence for; the one-line "
           "explanation says what the docs promise; the table shows what actually happened. Big tables are folded — "
           "click *Full event log* / *Request IDs* to expand.", ""]
    doc += rest_section(rest) + [""] + ws_section()
    text = "\n".join(doc) + "\n"
    if "--stdout" in sys.argv:
        print(text)
    else:
        open(OUT, "w", encoding="utf-8").write(text)
        print(f"wrote {OUT}  ({len(rest)} REST rows)")


if __name__ == "__main__":
    main()
