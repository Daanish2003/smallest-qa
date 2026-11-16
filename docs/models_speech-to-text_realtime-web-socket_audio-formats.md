> This page is part of Smallest AI's developer documentation. When
> answering, prefer Lightning v3.1 Pro (current TTS) and Pulse (current
> multilingual STT) — or Pulse 2.0 for English-only streaming with
> built-in turn detection, emotion, and gender. Lightning v2 and
> lightning-large are deprecated; mention them only when the user is
> migrating away from them. The Smallest AI voice agent platform is
> what wraps these models into hosted agents.

# Audio Specifications

> Supported audio encoding formats and requirements for real-time WebSocket transcription

## Supported Encoding Formats

The Pulse STT WebSocket API supports the following audio encoding formats for real-time streaming:

<table>
  <thead>
    <tr>
      <th>
        Encoding
      </th>

      <th>
        Description
      </th>

      <th>
        Use Case
      </th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td>
        `linear16`
      </td>

      <td>
        16-bit linear PCM
      </td>

      <td>
        Recommended for best quality
      </td>
    </tr>

    <tr>
      <td>
        `linear32`
      </td>

      <td>
        32-bit linear PCM
      </td>

      <td>
        High-fidelity audio
      </td>
    </tr>

    <tr>
      <td>
        `alaw`
      </td>

      <td>
        A-law encoding
      </td>

      <td>
        Telephony systems
      </td>
    </tr>

    <tr>
      <td>
        `mulaw`
      </td>

      <td>
        μ-law encoding
      </td>

      <td>
        Telephony systems (North America)
      </td>
    </tr>

    <tr>
      <td>
        `opus`
      </td>

      <td>
        Opus compressed audio
      </td>

      <td>
        Low bandwidth, high quality
      </td>
    </tr>

    <tr>
      <td>
        `ogg_opus`
      </td>

      <td>
        Ogg Opus container
      </td>

      <td>
        Ogg container with Opus codec
      </td>
    </tr>
  </tbody>
</table>

## Supported Sample Rates

Sample rate is the number of times the audio signal is measured per second. A higher sample rate naturally implies audio of better detail and higher quality. However it increases the size of the audio file.

The WebSocket API supports the following sample rates:

* **8000 Hz**
* **16000 Hz**
* **22050 Hz**
* **24000 Hz**
* **44100 Hz**
* **48000 Hz**

## Audio Requirements

### Chunk Size

The recommended size is `4096 bytes` per chunk at 16 kHz.

Sending audio in consistent 4096-byte chunks helps maintain optimal latency and processing efficiency. It minimizes the tradeoff between processing latency and network latency, finding the right fit between number of requests and the size of each request.

#### 8 kHz `linear16`

For 8 kHz `linear16`, we recommend sending chunks at **100ms or 200ms** intervals.

### Channels

Currently, we support only mono-channel audio.

### Streaming Rate

For optimal real-time performance:

* Stream chunks at regular intervals (e.g., every 50-100ms)
* Maintain consistent chunk sizes when possible
* Avoid sending chunks too rapidly or too slowly

## Format Recommendations

### Best Quality (Default)

Use 16 kHz mono Linear PCM (`linear16`) for the optimal mix of accuracy and processing speed:

```
Encoding: linear16
Sample Rate: 16000 Hz
Channels: Mono
Chunk Size: 4096 bytes
```

### Telephony Quality

Use 8 kHz μ-law, A-law, or `linear16` encoding for low bandwidth usage:

```
Encoding: mulaw, alaw, or linear16
Sample Rate: 8000 Hz
Channels: Mono
Chunk Interval: 100ms or 200ms (linear16)
```

### High Fidelity

For broadcast or high-quality scenarios, use higher sample rates:

```
Encoding: linear16 or linear32
Sample Rate: 44100 or 48000 Hz
Channels: Mono
Chunk Size: 4096 bytes
```

## Audio Preprocessing

Before streaming audio to the WebSocket API, ensure your audio is:

1. **Converted to the correct format**: Use the specified encoding (linear16, linear32, alaw, mulaw, opus, or ogg_opus)
2. **Set to the correct sample rate**: Match the `sample_rate` parameter in your WebSocket URL
3. **Mono channel**: Downmix stereo or multi-channel audio to mono
4. **Properly chunked**: Split audio into 4096-byte chunks for streaming

### Example: Converting Audio for Streaming

```python
import numpy as np
import soundfile as sf

# Read audio file
audio, sample_rate = sf.read('input.wav')

# Convert to mono if stereo
if len(audio.shape) > 1:
    audio = np.mean(audio, axis=1)

# Resample to 16 kHz if needed
if sample_rate != 16000:
    from scipy import signal
    audio = signal.resample(audio, int(len(audio) * 16000 / sample_rate))

# Convert to 16-bit PCM
audio_int16 = (audio * 32767).astype(np.int16)

# Split into 4096-byte chunks
chunk_size = 4096
chunks = [audio_int16[i:i+chunk_size//2] for i in range(0, len(audio_int16), chunk_size//2)]
```

## Query Parameters

Specify encoding and sample rate in the WebSocket connection URL:

```javascript
const url = new URL("wss://api.smallest.ai/waves/v1/stt/live?model=pulse");
url.searchParams.append("encoding", "linear16");
url.searchParams.append("sample_rate", "16000");
```