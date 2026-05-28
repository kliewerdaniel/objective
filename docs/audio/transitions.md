# Audio Transitions

Transitions between segments use FFmpeg crossfade (default 500ms). The transition type varies by segment:
- `intro → state`: 2s ambient crossfade
- `state → events`: 500ms quick crossfade
- `events → contradictions`: 500ms quick crossfade
- `system → outro`: 3s ambient crossfade

All transitions are pre-computed during audio stitching, not applied in real-time.
