# Audio Interrupt Handling

Interrupts occur when a breaking broadcast needs to preempt the current playback.

**Flow**:
1. Current segment fades out (500ms)
2. Breaking segment fades in (500ms)
3. Interrupted segment is re-queued at position 1 (after breaking segment)
4. If multiple interrupts occur within 60s, they're batched into a single segment

**Edge cases**: Interrupt during ambient → immediately start breaking; Interrupt during outro → skip to breaking.
