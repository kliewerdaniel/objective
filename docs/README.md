# objective03

**A synthetic epistemology engine masquerading as an infinite radio station.**

objective03 is a continuously running, terminal-first autonomous system that:
- Ingests live information streams from RSS, Reddit, YouTube transcripts, and government feeds
- Extracts atomic claims and links them into evolving event-centric knowledge graphs
- Preserves contradictions instead of collapsing them into false consensus
- Tracks narrative drift, political framing, and epistemic confidence over time
- Generates an infinite, eerily detached AI audio broadcast
- Remembers history through temporal graph relationships
- Runs entirely locally on Apple Silicon via llama.cpp

This is not a news summarizer. This is a geopolitical memory organism.

## Core Philosophy

> The broadcast is merely the visible layer. The real system is a continuously evolving geopolitical memory organism.

### What makes this novel

- **Persistent contradictory temporal memory** — the system remembers what it said, tracks how narratives change, and surfaces uncertainty
- **Graph-native architecture** — knowledge is stored as an evolving temporal graph, not flat documents
- **Contradiction preservation** — conflicting claims are stored and broadcast, not resolved
- **Narrative drift tracking** — the evolution of language around events is itself a first-class signal
- **Local-first inference** — everything runs on a laptop using quantized open models

### What this is NOT

- NOT a news aggregator
- NOT an RSS reader
- NOT a summarization pipeline
- NOT an engagement-optimized feed
- NOT pretending certainty exists where it does not

## Repository Structure

```
├── spec.md                    # Canonical philosophical / architectural vision
├── docs/
│   ├── README.md              # This file
│   ├── SYSTEM_OVERVIEW.md     # High-level system description
│   ├── ARCHITECTURE.md        # Complete architecture documentation
│   ├── DEVELOPMENT_PLAN.md    # Implementation strategy
│   ├── ROADMAP.md             # Phased development roadmap
│   ├── CONTRIBUTING.md        # Contribution guidelines
│   ├── architecture/          # Detailed architecture documents
│   ├── agents/                # Agent/module specifications
│   ├── database/              # Database schemas and strategies
│   ├── pipelines/             # Pipeline designs
│   ├── audio/                 # Audio generation system
│   ├── evaluation/            # Evaluation metrics and methodology
│   ├── security/              # Security and resilience
│   ├── deployment/            # Deployment and operations
│   ├── operations/            # Runbooks and maintenance
│   ├── research/              # Speculative future directions
│   ├── roadmap/               # Phase-by-phase breakdowns
│   ├── schemas/               # Data schemas
│   └── ui/                    # Terminal interface design
└── src/                       # Implementation (forthcoming)
```

## Quick Start

See [docs/deployment/local_setup.md](docs/deployment/local_setup.md) for setup instructions.

Prerequisites:
- Python 3.11+
- Apple Silicon Mac (M-series)
- llama.cpp (local build recommended)
- FFmpeg
- KuzuDB (embedded)
- Qdrant (local instance)

## System Architecture (One Paragraph)

Sources flow through an ingestion pipeline that normalizes and deduplicates content. A claim extraction agent (small fast instruct model) parses each document into atomic claims with confidence scores, entity links, and stance annotations. These claims populate a KuzuDB temporal property graph with event clustering, contradiction edges, and provenance chains. A narrative analysis layer tracks linguistic drift, political framing, and epistemic confidence evolution over time. A broadcast writer (larger reasoning model) synthesizes the current state of the graph into cold analytical scripts. Piper TTS renders these scripts into audio segments that are queued and played as an infinite broadcast. The entire system runs as a daemon, visible through a Textual terminal dashboard.

## License

See LICENSE file.

## Acknowledgments

Built on the shoulders of open-source AI, graph database, and audio synthesis communities.
