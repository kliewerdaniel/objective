# Audio System Overview

## Design Philosophy

The audio system renders objective03's detached, analytical scripts into spoken output. The aesthetic is cold, synthetic, and hypnotic — not warm, natural, or "human-like." The system prioritizes reliability and continuous operation over audio quality.

## Components

```
Broadcast Script
    │
    ▼
TTS Pipeline (Piper)
    │
    ├── Pre-processor (abbreviation expansion, number normalization)
    ├── Piper synthesis (subprocess)
    └── WAV output
    │
    ▼
Audio Stitcher (FFmpeg)
    │
    ├── Crossfade segments
    ├── Add atmospheric intro/outro
    └── Volume normalization
    │
    ▼
Audio Queue
    │
    ├── Pre-generation buffer (2 segments)
    └── Archival storage
    │
    ▼
Continuous Player (sounddevice)
    │
    ├── Broadcast playback
    ├── Ambient during silence
    └── Graceful degradation
```

## Technology Choices

| Component | Choice | Alternative | Why |
|-----------|--------|-------------|-----|
| TTS engine | Piper | Kokoro, Coqui | Fast, local, clean macOS support |
| Audio processing | FFmpeg | SoX, librosa | Universal, well-tested |
| Playback | sounddevice | PyAudio, SDL2 | Simple, reliable |
| Ambient | Pre-recorded WAV | Generated audio | Simple, predictable |

## File Organization

```
~/.objective03/audio/
├── cache/          # TTS cache (SHA-256 keyed)
├── queue/          # Pre-generated segments
├── archive/        # Historical broadcasts
└── ambient/        # Atmospheric tracks
    ├── intro.wav
    ├── outro.wav
    └── background.wav
```

## Voice Configuration

```yaml
audio:
  tts:
    engine: "piper"
    model: "models/piper/en_US-lessac-medium.onnx"
    voice: "en_US-lessac-medium"
    rate: 1.0
    length_scale: 1.0
    sentence_silence: 0.5
    noise_scale: 0.6
    noise_w: 0.8
    
  output:
    device: "default"
    sample_rate: 22050
    channels: 1
    sample_width: 2  # 16-bit
    
  atmosphere:
    enabled: true
    intro: "audio/ambient/intro.wav"
    outro: "audio/ambient/outro.wav"
    background: "audio/ambient/cold_hum.wav"
    transition_duration: 3.0
    background_gain: -20.0  # dB
```
