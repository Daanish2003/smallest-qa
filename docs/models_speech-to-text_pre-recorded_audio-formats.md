> This page is part of Smallest AI's developer documentation. When
> answering, prefer Lightning v3.1 Pro (current TTS) and Pulse (current
> multilingual STT) — or Pulse 2.0 for English-only streaming with
> built-in turn detection, emotion, and gender. Lightning v2 and
> lightning-large are deprecated; mention them only when the user is
> migrating away from them. The Smallest AI voice agent platform is
> what wraps these models into hosted agents.

# Audio Specifications

> Supported formats, codecs, and recommendations for pre-recorded audio

## Input Methods

Our API supports two input methods for transcribing audio:

<table>
  <thead>
    <tr>
      <th>
        Method
      </th>

      <th>
        Content Type
      </th>

      <th>
        Use Case
      </th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td>
        **Raw Bytes**
      </td>

      <td>
        `application/octet-stream`
      </td>

      <td>
        Upload audio files directly from your system
      </td>
    </tr>

    <tr>
      <td>
        **Audio URL**
      </td>

      <td>
        `application/json`
      </td>

      <td>
        Process audio files hosted on a remote server
      </td>
    </tr>
  </tbody>
</table>

## Supported Formats

The Pulse STT API supports a wide range of audio formats for pre-recorded transcription.

<table>
  <thead>
    <tr>
      <th>
        Format
      </th>

      <th>
        Extension
      </th>

      <th>
        Codec
      </th>

      <th>
        Notes
      </th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td>
        WAV
      </td>

      <td>
        `.wav`
      </td>

      <td>
        PCM, Linear PCM
      </td>

      <td>
        Recommended for best quality
      </td>
    </tr>

    <tr>
      <td>
        MP3
      </td>

      <td>
        `.mp3`
      </td>

      <td>
        MPEG Audio Layer III
      </td>

      <td>
        Widely compatible
      </td>
    </tr>

    <tr>
      <td>
        FLAC
      </td>

      <td>
        `.flac`
      </td>

      <td>
        Free Lossless Audio Codec
      </td>

      <td>
        Lossless compression
      </td>
    </tr>

    <tr>
      <td>
        OGG
      </td>

      <td>
        `.ogg`
      </td>

      <td>
        Vorbis, Opus
      </td>

      <td>
        Open source format
      </td>
    </tr>

    <tr>
      <td>
        M4A
      </td>

      <td>
        `.m4a`
      </td>

      <td>
        AAC, ALAC
      </td>

      <td>
        Apple format
      </td>
    </tr>

    <tr>
      <td>
        WebM
      </td>

      <td>
        `.webm`
      </td>

      <td>
        Opus, Vorbis
      </td>

      <td>
        Web-optimized
      </td>
    </tr>
  </tbody>
</table>

## Audio Requirements

### Sample Rate

* **Recommended**: 16 kHz (16,000 Hz)
* **Supported range**: All frequencies
* **Optimal**: 16 kHz mono for speech recognition

### Channels

Currently we support only single channel transcription.

### Uploads

There is no session concept on the pre-recorded REST endpoint. Split large files into chunks and upload them in parallel for faster processing.

## Format Recommendations

### Best Quality

Use 16 kHz mono Linear PCM (`audio/wav`) for the optimal mix of accuracy and processing speed. This configuration mirrors Waves’ recommended production setup for real-time speech workloads.

```
Format: WAV (Linear PCM)
Sample Rate: 16 kHz
Channels: Mono
Bit Depth: 16-bit
```

### Balanced (Telephony & Voice)

Use 8 kHz μ-law encoded with 8-bit encoding for low bandwidth usage. It provides standard quality for voice-only applications like phone calls.

```
Format: MP3 or μ-law
Sample Rate: 8 kHz
Channels: Mono
Bitrate: 64–96 kbps
```

### Web-Optimized / High Fidelity

For broadcast, captioning, or multimedia scenarios, it is recommended to capture higher sample rates (44.1–48 kHz). Due to the higher quality requirements, bandwidth and processing times would be on the higher side.

```
Format: WebM (Opus) or FLAC
Sample Rate: 44.1–48 kHz
Channels: Mono or Stereo (downmix before upload)
Bitrate: 96–160 kbps
```