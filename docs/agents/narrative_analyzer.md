# Narrative Analyzer Agent

## Overview

The narrative analyzer identifies and tracks narrative threads through the claim graph. It clusters related claims into narratives, measures drift, and tracks narrative evolution over time.

## Responsibility

- Cluster claims into narrative threads by topic, entities, and temporal proximity
- Measure narrative drift across multiple dimensions
- Track narrative lifecycle (emergence, evolution, consolidation, archival)
- Detect narrative branching and merging
- Update narrative state in the graph

## Interface

```python
class NarrativeAnalyzer(BaseAgent):
    name = "narrative_analyzer"
    timeout_seconds = 120.0
    
    async def run(self, context: AgentContext) -> AgentResult:
        model = await context.models.get("reasoning")
        
        # Get unclustered claims and existing narratives
        unclustered = context.graph.get_unclustered_claims(hours=24)
        existing_narratives = context.graph.get_active_narratives()
        
        stats = {"narratives_updated": 0, "narratives_created": 0, "claims_clustered": 0}
        
        # Cluster new claims into narratives
        if unclustered:
            new_narratives = await self._cluster_claims(unclustered, model, context)
            for narrative in new_narratives:
                context.graph.create_narrative(narrative)
                for claim_id in narrative.claim_ids:
                    context.graph.link_claim_to_narrative(claim_id, narrative.id)
                stats["narratives_created"] += 1
                stats["claims_clustered"] += len(narrative.claim_ids)
        
        # Update existing narratives
        for narrative in existing_narratives:
            drift = await self._measure_drift(narrative, context)
            context.graph.update_narrative_drift(narrative.id, drift)
            stats["narratives_updated"] += 1
        
        return AgentResult(success=True, data={
            "narratives_created": stats["narratives_created"],
            "narratives_updated": stats["narratives_updated"],
            "claims_clustered": stats["claims_clustered"],
        }, metrics=stats)
    
    async def _cluster_claims(self, claims: list[Claim], model: LLMClient,
                               context: AgentContext) -> list[Narrative]:
        # Step 1: Embed all claims
        embeddings = await self._embed_claims(claims, context)
        
        # Step 2: Cluster by embedding similarity + temporal proximity
        clusters = self._cluster_by_similarity(claims, embeddings, threshold=0.75)
        
        # Step 3: For each cluster, generate narrative label
        narratives = []
        for cluster in clusters:
            label = await self._generate_label(cluster, model)
            embedding = np.mean([embeddings[c.id] for c in cluster], axis=0)
            
            narratives.append(Narrative(
                id=generate_uuid(),
                label=label,
                description="",
                drift_score=0.0,
                framing="unknown",
                active=True,
                first_seen=min(c.timestamp for c in cluster),
                last_updated=datetime.utcnow(),
                claim_ids=[c.id for c in cluster],
                embedding=embedding.tolist(),
            ))
        
        return narratives
    
    def _cluster_by_similarity(self, claims: list[Claim], 
                                embeddings: dict[str, np.ndarray],
                                threshold: float) -> list[list[Claim]]:
        """Simple clustering: connect claims with similarity > threshold."""
        if not claims:
            return []
        
        # Build similarity graph
        adjacency = {c.id: set() for c in claims}
        for i, a in enumerate(claims):
            for j, b in enumerate(claims):
                if i >= j:
                    continue
                sim = cosine_similarity(embeddings[a.id], embeddings[b.id])
                
                # Temporal bonus: claims within 24h are more likely related
                time_diff = abs((a.timestamp - b.timestamp).total_seconds())
                temporal_bonus = max(0, 1 - time_diff / 86400) * 0.1
                
                if sim + temporal_bonus > threshold:
                    adjacency[a.id].add(b.id)
                    adjacency[b.id].add(a.id)
        
        # Find connected components
        visited = set()
        clusters = []
        for claim in claims:
            if claim.id in visited:
                continue
            cluster = []
            stack = [claim.id]
            while stack:
                cid = stack.pop()
                if cid in visited:
                    continue
                visited.add(cid)
                cluster.append(next(c for c in claims if c.id == cid))
                stack.extend(adjacency[cid] - visited)
            clusters.append(cluster)
        
        return clusters
    
    async def _generate_label(self, claims: list[Claim], model: LLMClient) -> str:
        texts = [c.text for c in claims[:5]]  # First 5 for efficiency
        prompt = f"""Generate a concise label for this narrative thread (5 words max):
{chr(10).join(f"- {t}" for t in texts)}
Label:"""
        response = await model.generate(prompt, temperature=0.3, max_tokens=50)
        return response.text.strip().strip('"')
```

## Drift Measurement

```python
async def _measure_drift(self, narrative: Narrative, 
                          context: AgentContext) -> DriftMeasurement:
    """Measure how much a narrative has drifted since last measurement."""
    current_claims = context.graph.get_thread_claims(narrative.id, 
                                                      since=narrative.last_updated)
    if not current_claims:
        return DriftMeasurement(total=0.0, linguistic=0.0, confidence=0.0, source=0.0)
    
    # Get previous claim embeddings for comparison
    prev_claims = context.graph.get_thread_claims(narrative.id, 
                                                    before=narrative.last_updated)
    
    if not prev_claims:
        return DriftMeasurement(total=0.0, linguistic=0.0, confidence=0.0, source=0.0)
    
    # Compute embeddings
    model = await context.models.get("embedding")
    prev_emb = await self._embed_batch([c.text for c in prev_claims], model)
    curr_emb = await self._embed_batch([c.text for c in current_claims], model)
    
    # Linguistic drift
    prev_centroid = np.mean(prev_emb, axis=0)
    curr_centroid = np.mean(curr_emb, axis=0)
    linguistic = float(1 - cosine_similarity([prev_centroid], [curr_centroid])[0][0])
    
    # Confidence drift
    prev_conf = np.mean([c.confidence for c in prev_claims])
    curr_conf = np.mean([c.confidence for c in current_claims])
    confidence = float(abs(curr_conf - prev_conf))
    
    # Source drift
    prev_sources = set(c.source_name for c in prev_claims)
    curr_sources = set(c.source_name for c in current_claims)
    source_jaccard = len(prev_sources & curr_sources) / max(len(prev_sources | curr_sources), 1)
    source = 1.0 - source_jaccard
    
    total = linguistic * 0.4 + confidence * 0.3 + source * 0.3
    
    return DriftMeasurement(total=total, linguistic=linguistic, 
                           confidence=confidence, source=source)
```

## Narrative Lifecycle

```python
class NarrativeLifecycle:
    @staticmethod
    def classify_stage(narrative: Narrative, graph: GraphStore) -> str:
        """Determine the lifecycle stage of a narrative."""
        age_days = (datetime.utcnow() - narrative.first_seen).days
        claim_count = graph.get_narrative_claim_count(narrative.id)
        recent_claims = graph.get_narrative_claim_count_since(
            narrative.id, hours=24
        )
        
        if age_days < 1 and claim_count < 5:
            return "emerging"
        elif recent_claims > 0:
            return "active"
        elif age_days < 7:
            return "fading"
        elif narrative.drift_score < 0.1:
            return "stable"
        else:
            return "evolving"
    
    @staticmethod
    def should_archive(narrative: Narrative, graph: GraphStore) -> bool:
        """Determine if a narrative should be archived."""
        age_days = (datetime.utcnow() - narrative.last_updated).days
        return age_days > 7 and not graph.get_narrative_claim_count_since(narrative.id, days=7)
```
