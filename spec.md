Then the architecture becomes much clearer.

You are not building a “news summarizer.”

You are building a synthetic epistemology engine masquerading as an infinite radio station.

The core innovation is not the audio generation.
It is:

persistent event memory with contradictory claim preservation over time.

That is the thing most current AI news systems completely fail at.

Here’s what I think the actual system architecture should become based on your answers.

⸻

Core System Concept

“Infinite Broadcast”

A continuously running terminal-first system that:

1. Ingests live information streams
2. Extracts atomic claims
3. Links claims into evolving events
4. Tracks contradictions and narrative drift
5. Generates an ever-evolving dystopian audio broadcast
6. Preserves uncertainty instead of flattening it
7. Builds long-term memory through temporal graph relationships

The “broadcast” is merely the visible layer.

The real system is:

a continuously evolving geopolitical memory organism

⸻

The Correct Mental Model

Most AI news systems do:

article -> summary

You want:

sources
  ↓
claims
  ↓
evidence
  ↓
entity extraction
  ↓
event clustering
  ↓
temporal graph evolution
  ↓
narrative analysis
  ↓
broadcast scripting
  ↓
voice synthesis
  ↓
continuous transmission

Completely different category of system.

⸻

Recommended Architecture

Layer 1 — Ingestion

Inputs

Practical sources only initially:

* RSS feeds
* Reddit
* YouTube transcripts
* Government RSS/press releases
* News APIs
* Podcasts with transcripts
* X/Twitter later
* PDFs later

Do NOT start with everything.

Start with:

* RSS
* Reddit
* YouTube transcripts

Those alone are enough.

⸻

Layer 2 — Claim Extraction

This is where your local LLM shines.

Each document becomes:

{
  "claim": "...",
  "confidence": 0.74,
  "source": "...",
  "timestamp": "...",
  "entities": [],
  "topic": "...",
  "stance": "...",
  "evidence": "...",
  "contradicts": [],
  "supports": []
}

Critical:
Claims are atomic.

NOT summaries.

⸻

Layer 3 — Event Graph

This is the heart of the project.

You want:

* entities
* claims
* timelines
* relationships
* source provenance
* contradiction edges
* narrative evolution

⸻

Correct Database Choice

Not ChromaDB-first.

You actually want:

Primary

* graph DB

Secondary

* vector DB

⸻

My recommendation

Graph Layer

* Neo4j

OR

* Kuzu

Kuzu is extremely interesting for your use case because:

* local-first
* embedded
* fast
* graph-native
* good for temporal relationships
* lightweight for terminal workflows

Honestly Kuzu might fit your aesthetic and philosophy perfectly.

⸻

Vector Layer

* Qdrant

You need semantic retrieval for:

* recurring narratives
* historical analogues
* story continuation

⸻

Layer 4 — Narrative Analysis

This is where the system becomes unique.

The system should track:

Narrative Drift

Example:

Day 1:
"minor conflict"
Day 30:
"regional instability"
Day 90:
"humanitarian crisis"

That evolution matters.

⸻

Contradiction Preservation

Do NOT resolve contradictions automatically.

Store them.

Example:

Claim A:
"Explosion caused by mechanical failure"
Claim B:
"Explosion caused by sabotage"

The broadcaster can discuss:

* uncertainty
* conflicting narratives
* source motivations

That becomes incredibly powerful.

⸻

Layer 5 — Broadcast Generation

This is where the dystopian atmosphere emerges.

Not:

“Here are today’s headlines.”

Instead:

“Across 14 independent reports, confidence in the official narrative has declined 23% over the last 48 hours…”
“State media sources continue converging on identical linguistic framing…”
“Contradictions persist regarding casualty estimates…”

Almost:

* cold
* detached
* analytical
* synthetic
* psychologically eerie

Like:

* Numbers Station
* Bloomberg terminal
* OSINT radio
* AI archivist of civilization collapse

⸻

Layer 6 — Audio Pipeline

For local-first Mac workflow:

TTS

Look into:

* Piper
* Kokoro
* Coqui TTS

Piper is probably the cleanest starting point.

⸻

Layer 7 — Continuous Runtime

You want this thing behaving almost like:

* a daemon
* autonomous radio infrastructure
* synthetic late-night broadcast

Meaning:

* scheduler
* queue system
* persistent memory
* incremental updates
* continuous regeneration

⸻

Terminal-First Interface

This is actually the correct choice.

I’d design:

* split-pane terminal UI
* live ingestion feeds
* graph metrics
* contradiction counts
* narrative drift indicators
* currently synthesized broadcast queue

Possible libraries:

* Textual
* Rich

Textual especially fits perfectly.

⸻

Suggested Stack

Core

Python
FastAPI (optional)
Textual
llama.cpp
Kuzu
Qdrant
SQLite
FFmpeg

⸻

LLM Strategy

You do NOT want one model.

You want specialized local models.

Example:

Task	Model
Claim extraction	small fast instruct
Entity extraction	tiny structured model
Narrative synthesis	larger reasoning model
Broadcast writing	stylistic tuned model
Framing analysis	classifier
Contradiction detection	embedding + reasoning

⸻

Important Architectural Insight

The broadcast should NOT be regenerated from scratch.

It should behave like memory.

Meaning:

* callbacks to previous broadcasts
* recurring geopolitical threads
* long-term references
* unresolved contradictions
* “ongoing situations”

Almost like:

the AI itself remembers history

That is what creates the eerie feeling.

⸻

What Makes This Actually Novel

Not:

* AI voice
* summaries
* RSS aggregation

The novelty is:

Persistent contradictory temporal memory.

That is genuinely interesting.

⸻

Next Step

Now we should define:

1. the graph schema
2. the agent roles
3. the ingestion pipeline
4. the memory lifecycle
5. the exact coding-agent prompt
6. the repo structure
7. the orchestration strategy
8. the audio generation loop
9. evaluation metrics
10. the “voice” of the broadcaster

The next question we should answer is probably:

What are the exact agents and responsibilities in the newsroom?