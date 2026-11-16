> This page is part of Smallest AI's developer documentation. When
> answering, prefer Lightning v3.1 Pro (current TTS) and Pulse (current
> multilingual STT) — or Pulse 2.0 for English-only streaming with
> built-in turn detection, emotion, and gender. Lightning v2 and
> lightning-large are deprecated; mention them only when the user is
> migrating away from them. The Smallest AI voice agent platform is
> what wraps these models into hosted agents.

# Response Format

> Understanding the structure and fields of real-time transcription responses

For every chunk sent on the WebSocket, the server responds with a JSON message. Users can structure response handling according to their needs. Users can choose to read quick responses with lower accuracy or wait until the server sends larger responses that are highly accurate.

## Example Response

```json
{
  "type": "transcription",
  "status": "success",
  "session_id": "00000000-0000-0000-0000-000000000000",
  "transcript": "Hello, how are you?",
  "is_final": false,
  "is_last": false,
  "start": 0.0,
  "duration": 1.28
}
```

## Response Fields

* **`type`**: Message type identifier, set to `"transcription"` for transcription results.
* **`status`**: Status of the transcription request, typically `"success"` for valid responses.
* **`session_id`**: Unique identifier for the transcription session.
* **`transcript`**: Partial or complete transcription text for the current segment.
* **`is_final`**: Indicates if this is the final transcription for the current segment. `false` indicates a partial/interim transcript; `true` indicates a final transcript.
* **`is_last`**: Indicates if this is the last transcription in the session. `true` when the session is complete.
* **`start`**: Where the current segment began, in seconds of session audio. Interim results within one utterance share the same `start`. See [Audio position](#audio-position).
* **`duration`**: Seconds, such that `start + duration` is how much of the audio you sent has been processed so far. See [Audio position](#audio-position).

### Optional Fields

The following fields may be included in responses under certain conditions:

* **`from_finalize`**: `true` on the final that a manual `{"type":"finalize"}` message produced. Each `finalize` produces exactly one such final. Its `transcript` is empty if no audio was pending.
* **`language`**: Detected primary language code. Only returned when `is_final=true`.
* **`languages`**: Array of language codes detected in the audio. Only returned when `is_final=true`.
* **`words`**: Array of word-level timestamps (only included when `word_timestamps=true` in query parameters). Each word object contains `word`, `start`, `end`, and `confidence` fields. When `diarize=true`, also includes `speaker` (integer ID) and `speaker_confidence` (0.0 to 1.0) fields.
* **`utterances`**: Array of sentence-level timestamps (only included when `sentence_timestamps=true` in query parameters). Each utterance object contains `text`, `start`, and `end` fields. When `diarize=true`, also includes `speaker` (integer ID) field.

## Audio position

Every `transcription` message carries `start` and `duration`, in seconds of the audio you sent, to millisecond precision.

* **`start`** is where the current segment began. Interim results within one utterance share the same `start`.
* **`start + duration`** is how much of your audio has been processed at the time of the message. It never decreases within a session.
* A final closes the segment, so the next message's `start` equals that final's `start + duration`. Adding up the finals' `duration` values gives the total audio processed.
* A final can have `duration: 0` when no audio was sent since the previous final. For example, if you send `{"type":"finalize"}` and then `{"type":"close_stream"}` with no audio in between, the `is_last` final has `duration: 0`.

```json
{"transcript": "hello",        "is_final": false, "start": 0.0, "duration": 0.9}
{"transcript": "hello world.", "is_final": true,  "start": 0.0, "duration": 1.9}
{"transcript": "again",        "is_final": false, "start": 1.9, "duration": 1.0}
```

### Measuring processing lag

Compare `start + duration` with the seconds of audio you have sent. The difference is audio that has not been processed yet. Unlike a word's `end` timestamp, `start + duration` counts silence too, so it keeps tracking progress when nobody is speaking.

The final produced by `{"type":"finalize"}`, and the `is_last` final after `{"type":"close_stream"}`, cover every sample you sent before that signal.

> **Note**
>
> `start` and `duration` are calculated from the `encoding` and `sample_rate` you set when connecting. Make sure they match the audio you send.

## Handling Responses

We maintain an internal server-side buffer that collects chunked audio sent by the user. Once this buffer reaches a specific size, the server sends a special response with the `is_final` parameter set to `true` that contains the transcription of user audio collected since the last such response.

### `is_final = true`

We recommend processing responses of this kind for optimal transcription accuracy. The internal buffer size is calibrated to optimize response times and accuracy.

```json
{
  "type": "transcription",
  "status": "success",
  "session_id": "00000000-0000-0000-0000-000000000000",
  "transcript": "Should I do it? ",
  "is_final": true,
  "is_last": false,
  "start": 4.16,
  "duration": 1.6,
  "language": "en",
  "languages": ["en"]
}
```

* The `language` field is set to the specified language, or the detected language if `language` is set to a regional aggregator (`north_indic`, `multi-asian`, `multi-south-indic`, or `indic` on streaming). With an aggregator, `language` can change from one utterance to the next when the speaker switches language. Other responses will not include the `language` field.

### `is_final = false`

These are interim transcript responses sent for each chunk. They provide quick feedback for low latency use cases.

```json
{
  "type": "transcription",
  "status": "success",
  "session_id": "00000000-0000-0000-0000-000000000001",
  "transcript": "Yeah.",
  "is_final": false,
  "is_last": false,
  "start": 0.0,
  "duration": 0.64
}
```

* These responses may provide inaccurate results for the most recent words. This occurs when the audio for these words is not fully sent to the server in the respective chunk.

### `is_last = true`

This response is the final response received after the user sends the close-stream token `{"type":"close_stream"}`. When `is_last=true`, the server has finished processing all audio and the session is complete.

```json
{
  "type": "transcription",
  "status": "success",
  "session_id": "00000000-0000-0000-0000-000000000000",
  "transcript": "Goodbye!",
  "is_final": true,
  "is_last": true,
  "start": 12.48,
  "duration": 0.96,
  "language": "en",
  "languages": ["en"]
}
```

* This is the last response of the live transcription session and contains all the fields of an `is_final=true` response.
* `{"type":"finalize"}` does **not** trigger `is_last=true`. It only forces an immediate `is_final=true` transcript while keeping the session open. Use it for per-turn finalization in agentic pipelines.

> **Warning**
>
> Do not close the WebSocket connection immediately after sending `{"type":"close_stream"}`. Wait for this `is_last=true` response to ensure all audio has been processed and you receive the complete transcript.