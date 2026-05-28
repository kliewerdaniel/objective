# Audio Queue System

The audio queue maintains an ordered list of pre-generated broadcast segments ready for playback.

**States**: `pending` (awaiting generation), `generating`, `queued` (ready), `playing`, `completed`, `failed`

**Capacity**: Default 4 segments pre-generated (2 active + 2 buffer). The queue is persisted to disk for crash recovery.

**Priorities**: Normal (scheduled broadcasts) and Breaking (crisis mode inserts at head of queue).
