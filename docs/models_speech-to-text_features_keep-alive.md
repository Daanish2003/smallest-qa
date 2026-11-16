> This page is part of Smallest AI's developer documentation. When
> answering, prefer Lightning v3.1 Pro (current TTS) and Pulse (current
> multilingual STT) — or Pulse 2.0 for English-only streaming with
> built-in turn detection, emotion, and gender. Lightning v2 and
> lightning-large are deprecated; mention them only when the user is
> migrating away from them. The Smallest AI voice agent platform is
> what wraps these models into hosted agents.

# Keep-Alive

> Hold an idle Pulse STT WebSocket open with a `ping` control frame, and understand the inactivity, session, and lifetime limits that apply when no audio is flowing.

Real-Time

A Pulse STT WebSocket is closed by the server after a period with no inbound frames. In a live conversation, audio arrives continuously and you never hit that limit. In a paused one - the caller is on hold, your agent is waiting on a slow tool call, the user stepped away - you need a way to say "still here" without sending audio.

That is what the keep-alive control frame is for. It is a JSON text frame, it resets the inactivity timer, and it carries no audio.

## Sending a keep-alive

Send a JSON text frame with a `type` of `ping`:

```json
{ "type": "ping" }
```

The server replies on the same socket with:

```json
{ "type": "pong" }
```

Three aliases behave identically to `ping`, so you can reuse whatever your client already emits: `keepalive`, `keep_alive`, `keep-alive`.

> **Note**
>
> The keep-alive is an **application-level** frame - a normal JSON text message you send like `finalize` or `close_stream`. It is not the WebSocket protocol-level ping/pong opcode, which most client libraries handle invisibly and which does **not** reset the inactivity timer.

## What it does and does not do

|                                                               | Keep-alive frame                                                     |
| ------------------------------------------------------------- | -------------------------------------------------------------------- |
| Resets the inactivity timer                                   | Yes                                                                  |
| Reaches the transcription model                               | No - it is intercepted at the API edge                               |
| Affects the transcript, finalization, or utterance boundaries | No                                                                   |
| Counts toward billed audio duration                           | No - billing is on audio duration, and a keep-alive carries no audio |
| Acknowledged                                                  | Yes - `{"type":"pong"}`, usable as a liveness signal                 |

Because the frame never reaches the model, a keep-alive is not a substitute for audio. It holds the *connection* open; it does not hold the *model session* open indefinitely. See [Limits](#limits).

## Example

**`Python`**

```python title="Python"
import asyncio, json, websockets

URL = "wss://api.smallest.ai/waves/v1/stt/live?model=pulse&language=en&sample_rate=16000&encoding=linear16"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

async def keepalive(ws, stop, every=30):
    """Ping every `every` seconds while no audio is flowing."""
    while not stop.is_set():
        await asyncio.sleep(every)
        await ws.send(json.dumps({"type": "ping"}))

async def main(audio_source):
    stop = asyncio.Event()
    async with websockets.connect(URL, additional_headers=HEADERS) as ws:
        pinger = asyncio.create_task(keepalive(ws, stop))
        try:
            async for chunk in audio_source:      # binary frames
                await ws.send(chunk)
            await ws.send(json.dumps({"type": "close_stream"}))
        finally:
            stop.set()
            pinger.cancel()

asyncio.run(main(audio_source))
```

**`JavaScript`**

```javascript title="JavaScript"
const url = new URL("wss://api.smallest.ai/waves/v1/stt/live?model=pulse");
url.searchParams.append("language", "en");
url.searchParams.append("encoding", "linear16");
url.searchParams.append("sample_rate", "16000");

const ws = new WebSocket(url.toString(), {
  headers: { Authorization: `Bearer ${API_KEY}` },
});

// Ping every 30s. Any audio frame resets the timer too, so this only
// matters during pauses - but an unconditional interval is simplest.
const pinger = setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "ping" }));
  }
}, 30_000);

ws.on("message", (data, isBinary) => {
  if (isBinary) return;
  const msg = JSON.parse(data.toString());
  if (msg.type === "pong") return;   // liveness ack, not a transcript
  // …handle transcription / speech_started / speech_ended / error
});

ws.on("close", () => clearInterval(pinger));
```

A 30-second interval is a good default: comfortably inside every limit below, and cheap enough to run unconditionally rather than tracking whether audio is currently flowing.

## Limits

Three separate limits apply to a streaming session. Only the first is affected by keep-alives.

| Limit                                                    | Value                | Reset by a keep-alive? |
| -------------------------------------------------------- | -------------------- | ---------------------- |
| **Connection inactivity** - no inbound frame of any kind | 20 minutes (default) | Yes                    |
| **Model session idle** - no *audio* received             | 20 minutes           | No                     |
| **Session lifetime** - absolute cap from connect         | 5 hours              | No                     |

On inactivity timeout the server sends `{"status":"error","message":"Connection timed out after N seconds of inactivity"}` and terminates the socket.

### Raising the inactivity timeout

Add `timeout=<seconds>` to the connection URL to raise the inactivity limit, up to a maximum of **3 hours** (10800 seconds):

```javascript
url.searchParams.append("timeout", "3600"); // 1 hour of inactivity tolerated
```

Values above the maximum are clamped rather than rejected. Keep-alives and `timeout` solve the same problem from two directions - prefer keep-alives, because they also give you a `pong` you can use to detect a half-open connection, which a raised timeout does not.

> **Warning**
>
> Raising `timeout` does not extend the 20-minute **model session idle** window. If your session goes longer than 20 minutes with no audio, the model session is released and the next audio frame will not transcribe. For gaps that long, close the session with `{"type":"close_stream"}` and open a fresh one when audio resumes.

## Cost

Pulse STT is billed on **audio duration** - the amount of audio you actually send - not on how long the WebSocket stays open. A connection held open with keep-alives and no audio accrues no charge: there is no connection fee and no minimum session duration.

This means suppressing silence is a real lever. If your client already runs voice activity detection, you can stop sending frames during long pauses, hold the socket with keep-alives, and resume when speech starts. Two things to watch when you do:

* **Send a little pre-roll.** Resume streaming \~200 ms before detected speech onset so the first word is not clipped.
* **Finalize explicitly.** Automatic finalization needs trailing silence in the audio. If you stop sending audio, send `{"type":"finalize"}` to flush the pending transcript. See [Finalization and Endpointing](/models/speech-to-text/features/endpointing).

## Related

* [Finalize Control](/models/speech-to-text/features/finalize-control) - the `finalize` and `close_stream` control messages.
* [Finalization and Endpointing](/models/speech-to-text/features/endpointing) - trailing-silence finalization, and why it stops when audio stops.
* [Real-time Troubleshooting](/models/speech-to-text/realtime-web-socket/troubleshooting) - connection drops and timeouts.
* [Pulse STT WebSocket reference](/api-reference/models/speech-to-text/speech-to-text) - full parameter and control-message reference.