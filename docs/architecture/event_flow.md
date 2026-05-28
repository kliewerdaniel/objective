# Event Flow Architecture

## Pipeline Event Flow

The system is structured as a directed acyclic pipeline with feedback loops for analysis. Each stage consumes the output of the previous stage and produces structured data.

```
Time ─────────────────────────────────────────────────────────────────►

┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
│SOURCE  │─▶│NORMALIZE│─▶│EXTRACT │─▶│RESOLVE │─▶│CLUSTER │─▶│ANALYZE │
│POLL    │  │ADAPT    │  │CLAIMS  │  │ENTITIES│  │EVENTS  │  │& FRAME │
└────────┘  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘
                                                               │
                                                               ▼
┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
│ARCHIVE │◀─│PRUNE   │◀─│CONSOLI-│◀─│DETECT  │◀─│MERGE   │◀─│UPDATE  │
│OBSOLETE│  │LOW-VAL │  │DATE    │  │CONTRA- │  │NARRATIVE│  │GRAPH   │
│        │  │        │  │MEMORY  │  │DICTION │  │THREADS │  │        │
└────────┘  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘
                                                                      │
                                          ┌────────┐  ┌────────┐      │
                                          │BROADCAST│◀─│SYNTHESIZE     │
                                          │PLAY     │  │SCRIPT   │     │
                                          └────────┘  └────────┘      │
                                                ▲                      │
                                                └──────────────────────┘
                                                    (feedback loop:
                                                    narrative analysis
                                                    informs broadcast)
```

## Event Types

| Event | Producer | Consumer | Data |
|-------|----------|----------|------|
| `source.polled` | Scheduler | Ingestion | Source name, timestamp, cursor |
| `document.received` | Poller | Normalizer | Raw content, metadata |
| `document.normalized` | Normalizer | Dedup | Cleaned content, hash |
| `document.deduped` | Dedup | Extractor | Unique document |
| `document.skipped` | Dedup | Logger | Document hash, reason |
| `claims.extracted` | Extractor | Graph Updater | List of Claim objects |
| `entities.resolved` | Entity Resolver | Graph Updater | Entity ID, aliases |
| `graph.updated` | Graph Updater | Contradiction Detector | Node IDs created |
| `contradictions.found` | Contradiction Detector | Graph Updater | Contradiction edges |
| `narrative.updated` | Narrative Analyzer | Graph Updater | Narrative state |
| `frame.analyzed` | Framing Analyzer | Graph Updater | Framing scores |
| `broadcast.generated` | Broadcast Writer | Audio Producer | Script object |
| `audio.rendered` | Audio Producer | Audio Queue | Audio file path |
| `audio.playing` | Audio Player | Logger | Segment ID |
| `audio.completed` | Audio Player | Scheduler | Segment ID |
| `memory.consolidated` | Consolidator | Graph Updater | Archived nodes |
| `health.failure` | Health Monitor | Orchestrator | Component, error |
| `health.recovered` | Health Monitor | Orchestrator | Component |

## Event Structure

Every event in the system follows a common structure:

```python
@dataclass
class SystemEvent:
    event_type: str          # dot-notation type
    timestamp: float         # unix timestamp
    source: str              # component name
    data: dict               # event-specific payload
    trace_id: str            # correlation ID for pipeline tracing
    error: Optional[str]     # None if success, error message if failure
    duration_ms: float       # wall-clock duration of the operation
```

## Pipeline Execution Model

### Synchronous Pipeline Stages

For stages within a single pipeline cycle, execution is sequential:

```python
async def pipeline_cycle():
    documents = await poll_sources()
    normalized = [normalize(d) for d in documents]
    unique = deduplicate(normalized)
    
    for doc in unique:
        claims = extract_claims(doc)
        resolved_entities = resolve_entities(claims)
        store_in_graph(claims, resolved_entities)
    
    contradictions = detect_contradictions(unique)
    store_contradictions(contradictions)
    
    narratives = analyze_narratives()
    frames = analyze_framing()
    store_analysis(narratives, frames)
```

### Asynchronous Scheduling

Pipeline cycles are scheduled independently:

```python
async def scheduler_loop():
    while running:
        # Ingestion runs frequently
        if time_since_last_ingestion > config.ingestion_interval:
            await ingestion_cycle()
        
        # Analysis runs less frequently
        if time_since_last_analysis > config.analysis_interval:
            await analysis_cycle()
        
        # Broadcast generation runs on its own schedule
        if time_since_last_broadcast > config.broadcast_interval:
            await broadcast_cycle()
        
        # Memory consolidation runs daily
        if time_since_last_consolidation > config.consolidation_interval:
            await consolidation_cycle()
        
        await asyncio.sleep(config.scheduler_tick)
```

## Feedback Loops

Two critical feedback loops exist:

### 1. Broadcast → Analysis Loop

Broadcast content is stored in the graph and analyzed in subsequent cycles:
- Previous broadcast topics influence entity resolution priority
- Listener engagement (if tracked) influences narrative weighting

### 2. Contradiction → Broadcast Loop

Contradiction metrics directly influence broadcast content:
- High contradiction density triggers uncertainty segments
- Resolved contradictions trigger retrospective segments

## Error Handling in Event Flow

Each pipeline stage follows the same error handling pattern:

```python
async def safe_stage(stage_fn, stage_name, context):
    try:
        result = await stage_fn(context)
        emit_event(f"{stage_name}.completed", data=result)
        return result
    except NonFatalError as e:
        emit_event(f"{stage_name}.warning", error=str(e))
        return partial_result
    except FatalError as e:
        emit_event(f"{stage_name}.failed", error=str(e))
        context.degraded_modules.append(stage_name)
        return None
    except Exception as e:
        emit_event(f"{stage_name}.crashed", error=str(e))
        context.degraded_modules.append(stage_name)
        return None
```

## Traceability

Every ingested document and every derived artifact carries a `trace_id` that links it back through the entire pipeline:

```
Source Poll ──▶ Document ──▶ Claims ──▶ Graph Nodes ──▶ Broadcast Segment
    │               │            │            │                │
    └───────────────┴────────────┴────────────┴────────────────┘
                        Same trace_id
```

This enables:
- Root cause analysis for errors
- Audit trail for any claim or broadcast
- Debugging pipeline failures
- Reproducible reconstruction of broadcast decisions
