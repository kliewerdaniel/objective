# Memory Consolidator Agent

## Overview

The memory consolidator manages the lifecycle of graph data. It archives old data, prunes low-value claims, summarizes dense subgraphs, and maintains overall graph health.

## Responsibility

- Archive old raw documents
- Consolidate resolved contradictions
- Summarize inactive narrative threads
- Prune orphaned nodes
- Generate graph health reports
- Manage backup scheduling

## Interface

```python
class MemoryConsolidator(BaseAgent):
    name = "memory_consolidator"
    timeout_seconds = 300.0  # 5 minutes
    
    async def run(self, context: AgentContext) -> AgentResult:
        stats = {
            "documents_archived": 0,
            "contradictions_consolidated": 0,
            "threads_summarized": 0,
            "claims_pruned": 0,
            "orphans_removed": 0,
        }
        
        # 1. Archive old documents
        archived = await self._archive_old_documents(context)
        stats["documents_archived"] = archived
        
        # 2. Consolidate resolved contradictions
        consolidated = await self._consolidate_contradictions(context)
        stats["contradictions_consolidated"] = consolidated
        
        # 3. Summarize inactive threads
        summarized = await self._summarize_inactive_threads(context)
        stats["threads_summarized"] = summarized
        
        # 4. Prune low-confidence orphans
        pruned = await self._prune_orphans(context)
        stats["claims_pruned"] = pruned
        
        # 5. Clean orphan edges
        cleaned = context.graph.clean_orphan_edges()
        stats["orphans_removed"] = cleaned
        
        # 6. Generate health report
        health = self._generate_health_report(context)
        
        return AgentResult(
            success=True,
            data={"stats": stats, "health": health},
            metrics=stats,
        )
    
    async def _archive_old_documents(self, context: AgentContext) -> int:
        """Move old raw documents to archival storage."""
        cutoff = datetime.utcnow() - timedelta(days=7)
        old_docs = context.graph.get_documents_before(cutoff)
        
        for doc in old_docs:
            # Serialize to archival format
            archival_blob = json.dumps(doc.to_dict())
            
            # Store in archive table
            context.metadata.insert_archived_document(
                doc.id, archival_blob, cutoff.isoformat()
            )
            
            # Remove from active graph
            context.graph.delete_document(doc.id)
        
        return len(old_docs)
    
    async def _consolidate_contradictions(self, context: AgentContext) -> int:
        """Summarize resolved contradictions."""
        resolved = context.graph.get_resolved_contradictions(
            older_than_hours=168  # 7 days
        )
        
        for contra in resolved:
            # Create summary node
            summary = ContradictionSummary(
                id=generate_uuid(),
                claim_a_text=contra.claim_a_text,
                claim_b_text=contra.claim_b_text,
                contradiction_type=contra.contradiction_type,
                resolution=contra.resolution,
                resolved_at=contra.resolved_at,
                evidence_summary=contra.resolution_evidence,
            )
            context.graph.create_contradiction_summary(summary)
            context.graph.remove_edge(contra.edge_id)
        
        return len(resolved)
    
    async def _summarize_inactive_threads(self, context: AgentContext) -> int:
        """Create summary nodes for inactive narratives."""
        inactive = context.graph.get_inactive_narratives(
            inactive_days=7
        )
        
        model = await context.models.get("reasoning")
        count = 0
        
        for narrative in inactive:
            claims = context.graph.get_thread_claims(narrative.id)
            
            if len(claims) < 3:
                continue  # Not worth summarizing
            
            # Generate summary
            texts = [c.text for c in claims[:10]]
            prompt = f"""Summarize this narrative thread in one paragraph:
{chr(10).join(f"- {t}" for t in texts)}
Summary:"""
            
            response = await model.generate(prompt, temperature=0.3, max_tokens=256)
            summary_text = response.text.strip()
            
            # Store summary and mark narrative as archived
            context.graph.set_narrative_summary(narrative.id, summary_text)
            context.graph.mark_narrative_archived(narrative.id)
            count += 1
        
        return count
    
    async def _prune_orphans(self, context: AgentContext) -> int:
        """Remove low-confidence orphan claims."""
        orphans = context.graph.find_orphan_claims(
            older_than_days=7,
            max_confidence=0.3,
            max_contradictions=0,
        )
        
        for claim in orphans:
            context.graph.delete_node("Claim", claim.id)
        
        return len(orphans)
    
    def _generate_health_report(self, context: AgentContext) -> dict:
        """Generate a graph health report."""
        try:
            return {
                "node_counts": {
                    "sources": context.graph.count_nodes("Source"),
                    "documents": context.graph.count_nodes("Document"),
                    "claims": context.graph.count_nodes("Claim"),
                    "entities": context.graph.count_nodes("Entity"),
                    "events": context.graph.count_nodes("Event"),
                    "narratives": context.graph.count_nodes("Narrative"),
                    "broadcasts": context.graph.count_nodes("Broadcast"),
                },
                "edge_counts": {
                    "contradictions": context.graph.count_edges("CONTRADICTS"),
                    "mentions": context.graph.count_edges("MENTIONS"),
                    "about_events": context.graph.count_edges("ABOUT_EVENT"),
                },
                "db_size_mb": self._get_db_size(context.config.graph_path),
                "orphan_edges": context.graph.count_orphan_edges(),
                "inactive_narratives": context.graph.count_inactive_narratives(days=7),
            }
        except Exception as e:
            return {"error": str(e)}
```

## Consolidation Schedule

| Operation | Interval | Trigger | Duration |
|-----------|----------|---------|----------|
| Archive documents | 24h | Scheduled | 30-60s |
| Consolidate contradictions | 24h | Scheduled | 10-30s |
| Summarize threads | 24h | Scheduled | 60-120s |
| Prune orphans | 24h | Scheduled | 10-30s |
| Health report | 1h | Scheduled | <5s |
| Full backup | 24h | Scheduled | 60-120s |

## Resource Impact

| Operation | CPU | RAM | Disk I/O | Duration |
|-----------|-----|-----|----------|----------|
| Archive documents | Low | Low | Medium | 30-60s |
| Consolidate contradictions | Low | Low | Low | 10-30s |
| Summarize threads | High (LLM) | High | Low | 60-120s |
| Prune orphans | Low | Low | Low | 10-30s |
| Full backup | Medium | Medium | High | 60-120s |
