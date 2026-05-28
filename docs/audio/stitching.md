# Audio Stitching Pipeline

The stitcher combines TTS-generated WAV segments into a complete broadcast with transitions.

**FFmpeg command**:
```bash
ffmpeg -i intro.wav -i seg1.wav -i seg2.wav -i seg3.wav -i outro.wav \
  -filter_complex "[0][1]acrossfade=d=0.5[o1];[o1][2]acrossfade=d=0.5[o2];\
  [o2][3]acrossfade=d=0.5[o3];[o3][4]acrossfade=d=1.5" \
  -c:a pcm_s16le output.wav
```

**Caching**: Stitched broadcasts are cached by script hash. Cache is invalidated when the underlying TTS cache is cleared.
