# Streaming Pipeline Architecture

## Overview

The streaming pipeline is the data processing backbone of objective03. It transforms raw source material through successive stages into graph data, scripts, and finally audio. The pipeline is designed for throughput, reliability, and observability.

## Pipeline Stages

### Stage 0: Configuration and Routing

Each document is classified by source type and routed to the appropriate connector:

```python
class Router:
    def route(self, source_type: str) -> Connector:
        connectors = {
            "rss": RSSConnector,
            "reddit": RedditConnector,
            "youtube": YouTubeConnector,
            "gov_rss": GovRSSConnector,
            "news_api": NewsAPIConnector,
            "podcast": PodcastConnector,
        }
        return connectors[source_type](self.config)
```

### Stage 1: Source Polling

The ingestion coordinator manages all source pollers:

```python
class IngestionCoordinator:
    def __init__(self, config: SourceConfig):
        self.pollers: list[Poller] = self._build_pollers(config)
        self.state = IngestionState()
    
    def _build_pollers(self, config) -> list[Poller]:
        pollers = []
        for source_type, sources in config.items():
            connector = Router().route(source_type)
            for source_config in sources:
                pollers.append(Poller(connector, source_config, self.state))
        return pollers
    
    async def poll_all(self) -> list[RawDocument]:
        """Poll all sources that are due for polling."""
        documents = []
        for poller in self.pollers:
            if poller.is_due():
                try:
                    docs = await poller.poll()
                    documents.extend(docs)
                except Exception as e:
                    logger.error("poll.failed", source=poller.name, error=str(e))
        return documents
```

### Stage 2: Normalization

```python
@dataclass
class NormalizedDocument:
    id: str                      # SHA-256 of normalized content
    source_type: str
    source_name: str
    title: str
    body: str                    # Cleaned text
    url: str
    published_at: datetime
    ingested_at: datetime
    author: Optional[str]
    language: str
    raw_metadata: dict

class Normalizer:
    def normalize(self, raw: RawDocument) -> NormalizedDocument:
        body = self._clean_html(raw.body)
        body = self._fix_encoding(body)
        body = self._normalize_whitespace(body)
        body = self._strip_boilerplate(body)
        
        return NormalizedDocument(
            id=sha256(body.encode()),
            source_type=raw.source_type,
            source_name=raw.source_name,
            title=self._clean_html(raw.title),
            body=body,
            url=raw.url,
            published_at=raw.published_at or datetime.utcnow(),
            ingested_at=datetime.utcnow(),
            author=raw.author,
            language=self._detect_language(body),
            raw_metadata=raw.metadata,
        )
```

### Stage 3: Deduplication

```python
class Deduplicator:
    def __init__(self, metadata_store: SQLiteStore):
        self.store = metadata_store
        self.seen_hashes: set[str] = set(self.store.get_all_document_hashes())
    
    def is_duplicate(self, doc: NormalizedDocument) -> bool:
        """Exact dedup via SHA-256."""
        if doc.id in self.seen_hashes:
            return True
        return False
    
    def is_near_duplicate(self, doc: NormalizedDocument, threshold: float = 0.85) -> bool:
        """Fuzzy dedup via MinHash on body text."""
        hash = self._minhash(doc.body)
        similarity = self._max_similarity_to_existing(hash)
        return similarity >= threshold
    
    def _minhash(self, text: str, num_hashes: int = 128) -> list[int]:
        shingles = {text[i:i+5] for i in range(len(text)-4)}
        return [min(h(shingle) for shingle in shingles) for h in self.hash_functions]
```

### Stage 4: Claim Extraction

See [agents/claim_extractor.md](../agents/claim_extractor.md) for full detail.

```python
class ClaimExtractor:
    def __init__(self, model_registry: ModelRegistry):
        self.model = model_registry  # Uses extraction model
    
    async def extract(self, doc: NormalizedDocument) -> list[Claim]:
        prompt = self._build_extraction_prompt(doc)
        response = await self.model.get("extraction").generate(
            prompt=prompt,
            temperature=0.0,
            max_tokens=2048,
            structured=True,
        )
        claims = self._parse_response(response.text)
        return claims
```

### Stage 5: Entity Resolution

```python
class EntityResolver:
    def __init__(self, graph: GraphStore):
        self.graph = graph
    
    async def resolve(self, claims: list[Claim]) -> list[Claim]:
        """Resolve entity references to canonical IDs."""
        for claim in claims:
            resolved = []
            for entity_name in claim.entity_names:
                canonical = self.graph.find_entity(entity_name)
                if canonical:
                    resolved.append(canonical)
                else:
                    new_id = self.graph.create_entity(entity_name)
                    resolved.append(new_id)
            claim.entity_ids = resolved
        return claims
```

### Stage 6: Graph Update

```python
class GraphUpdater:
    def __init__(self, graph: GraphStore, vector: VectorStore):
        self.graph = graph
        self.vector = vector
    
    async def update(self, doc: NormalizedDocument, claims: list[Claim]):
        # Insert source node
        source_id = self.graph.upsert_source(doc.source_name, doc.source_type)
        
        # Insert document node
        doc_id = self.graph.insert_document(doc)
        self.graph.create_edge(doc_id, "FROM_SOURCE", source_id)
        
        # Insert claim nodes
        for claim in claims:
            claim_id = self.graph.insert_claim(claim)
            self.graph.create_edge(claim_id, "EXTRACTED_FROM", doc_id)
            
            for entity_id in claim.entity_ids:
                self.graph.create_edge(claim_id, "MENTIONS", entity_id)
            
            # Generate embedding
            embedding = await self.generate_embedding(claim.text)
            self.vector.insert(claim_id, embedding)
```

### Stage 7: Contradiction Detection

```python
class ContradictionDetector:
    def __init__(self, model: ModelRegistry, graph: GraphStore, vector: VectorStore):
        self.model = model
        self.graph = graph
        self.vector = vector
    
    async def detect(self, new_claims: list[Claim]) -> list[Contradiction]:
        contradictions = []
        
        for claim in new_claims:
            # Find semantically similar claims
            similar = self.vector.search(claim.embedding, top_k=20)
            
            for other_id, score in similar:
                if score < 0.75:
                    continue  # Not similar enough
                
                other_claim = self.graph.get_claim(other_id)
                if not other_claim:
                    continue
                
                # Check if they're about the same event/entities
                if not self._same_context(claim, other_claim):
                    continue
                
                # Use LLM to check contradiction
                contradiction_type = await self._check_contradiction(
                    claim.text, other_claim.text
                )
                
                if contradiction_type:
                    contradictions.append(Contradiction(
                        claim_a=claim.id,
                        claim_b=other_id,
                        contradiction_type=contradiction_type,
                        confidence=score,
                        detected_at=datetime.utcnow(),
                    ))
        
        return contradictions
```

### Stage 8: Narrative Analysis

```python
class NarrativeAnalyzer:
    def __init__(self, model: ModelRegistry, graph: GraphStore):
        self.model = model
        self.graph = graph
    
    async def analyze(self):
        """Analyze current narrative state of the graph."""
        # Cluster claims into narrative threads
        threads = self.graph.get_active_narrative_threads()
        
        for thread in threads:
            # Measure drift since last analysis
            prev_embedding = thread.embedding
            current_claims = self.graph.get_thread_claims(thread.id)
            current_embedding = await self._embed_thread(current_claims)
            
            drift = cosine_distance(prev_embedding, current_embedding)
            
            # Analyze framing
            framing = await self._analyze_framing(current_claims)
            
            # Update thread
            self.graph.update_narrative_thread(
                thread.id,
                embedding=current_embedding,
                drift_score=drift,
                framing=framing,
                updated_at=datetime.utcnow(),
            )
```

### Stage 9: Broadcast Generation

```python
class BroadcastWriter:
    def __init__(self, model: ModelRegistry, graph: GraphStore):
        self.model = model
        self.graph = graph
    
    async def generate(self) -> Script:
        # Gather current state
        top_events = self.graph.get_top_events(limit=5)
        contradictions = self.graph.get_top_contradictions(limit=3)
        narratives = self.graph.get_active_narratives(limit=3)
        drift_scores = self.graph.get_drift_scores(time_horizon="24h")
        previous_broadcast = self.graph.get_latest_broadcast()
        
        prompt = self._build_broadcast_prompt(
            top_events=top_events,
            contradictions=contradictions,
            narratives=narratives,
            drift_scores=drift_scores,
            previous_broadcast=previous_broadcast,
        )
        
        response = await self.model.get("broadcast").generate(
            prompt=prompt,
            temperature=0.5,
            max_tokens=4096,
        )
        
        script = self._parse_script(response.text)
        self.graph.store_broadcast(script)
        return script
```

### Stage 10: Audio Production

```python
class AudioProducer:
    def __init__(self, tts_engine: PiperTTS, stitch: AudioStitcher):
        self.tts = tts_engine
        self.stitch = stitch
    
    async def produce(self, script: Script) -> AudioSegment:
        audio_chunks = []
        
        for segment in script.segments:
            wav = self.tts.synthesize(segment.text, voice="default")
            audio_chunks.append(wav)
        
        # Add atmospheric intro/outro
        full_audio = self.stitch.assemble(
            chunks=audio_chunks,
            intro=script.intro,
            outro=script.outro,
            transitions=True,
        )
        
        return AudioSegment(
            id=script.id,
            audio=full_audio,
            duration=len(full_audio) / 22050,
            generated_at=datetime.utcnow(),
        )
```

## Throughput Characteristics

| Stage | Throughput | Bottleneck | Mitigation |
|-------|-----------|------------|------------|
| Polling | 50 docs/min | Network latency | Parallel polling per source |
| Normalization | 500 docs/min | HTML parsing | lxml with caching |
| Dedup | 1000 docs/min | Hash lookup | In-memory hash set |
| Claim extraction | 4-8 docs/min | LLM inference | Batching, quantized models |
| Entity resolution | 200 claims/min | Graph queries | Entity cache, batch resolution |
| Graph update | 500 ops/min | KuzuDB writes | Batch insert |
| Contradiction detection | 10 pairs/min | LLM + vector | Pre-filter by similarity |
| Narrative analysis | 1 analysis/cycle | LLM synthesis | Only run when needed |
| Broadcast writing | 1 script/cycle | LLM synthesis | Pre-generation, queue |
| TTS | 1:12 realtime | Model inference | Pre-generation, caching |

## Pipeline Observability

Every pipeline stage emits metrics:

```python
@dataclass
class StageMetrics:
    stage: str
    documents_in: int
    documents_out: int
    latency_ms: float
    errors: int
    memory_mb: float
    
    def to_dict(self):
        return asdict(self)
```

These metrics are:
- Written to the SQLite metrics table
- Exposed via the terminal UI
- Available for health checks
- Logged for offline analysis
