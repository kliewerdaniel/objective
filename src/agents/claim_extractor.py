"""Claim extraction agent."""

import json
import re
from pathlib import Path
from src.agents.base import BaseAgent, AgentContext, AgentResult
from src.models.types import Claim
from src.prompts import load_prompt

MAX_DOCUMENTS_PER_CYCLE = 25

Rules:
- Extract ALL factual claims, observations, and notable statements
- Short summaries still contain claims — treat the full body as claim-worthy
- Each claim should be a single atomic statement
- Include the exact evidence text that supports each claim
- Rate confidence 0.0-1.0 based on clarity and specificity
- Classify stance: "support", "neutral", "oppose", or "uncertain"
- Extract all mentioned entity names (people, orgs, locations, events)
- Classify topic into one of: conflict, politics, disaster, economy, science, health, technology, environment, crime, other
- Output at least 2 claims per document even if it means splitting the body into multiple claims
- If the body is a short summary, output the entire content as one or more claims

Document:
Title: {title}
Source: {source}
Published: {published}
URL: {url}
Body:
{body}

Output ONLY a valid JSON array of objects with keys: text, confidence, stance, topic, entities (array of strings), evidence
"""


class ClaimExtractor(BaseAgent):
    name = "claim_extractor"
    timeout_seconds = 120.0

    async def run(self, context: AgentContext) -> AgentResult:
        documents = context.state.get("documents", [])[:MAX_DOCUMENTS_PER_CYCLE]
        if not documents:
            return AgentResult(success=True, data=[], metrics={"documents_processed": 0, "claims_extracted": 0, "errors": 0})

        model = await context.models.get("extraction")

        all_claims = []
        stats = {"documents_processed": 0, "claims_extracted": 0, "errors": 0}

        for doc in documents:
            try:
                claims = self._extract(doc, model)
                all_claims.extend(claims)
                stats["documents_processed"] += 1
                stats["claims_extracted"] += len(claims)
            except Exception as e:
                stats["errors"] += 1
                if context.logger:
                    context.logger.error("extraction.failed", doc_id=doc.id, error=str(e))

        context.state["claims"] = all_claims
        return AgentResult(success=True, data=all_claims, metrics=stats)

    def _extract(self, doc, model) -> list[Claim]:
        prompt = CLAIM_EXTRACTION_PROMPT.format(
            title=doc.title[:500],
            source=doc.source_name,
            published=str(doc.published_at),
            url=str(doc.url)[:200],
            body=doc.body[:3000],
        )
        try:
            response = model.generate(prompt, temperature=0.0, max_tokens=2048, structured=True)
            return self._parse(response.text, doc)
        except Exception as e:
            return []

    def _parse(self, text: str, doc) -> list[Claim]:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Fallback: try to extract any JSON array from the text
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except (json.JSONDecodeError, ValueError):
                    return []
            else:
                return []
        if isinstance(data, dict):
            data = [data]

        claims = []
        for item in data if isinstance(data, list) else []:
            try:
                claim = Claim(
                    text=str(item.get("text", ""))[:500],
                    confidence=float(item.get("confidence", 0.5)),
                    stance=str(item.get("stance", "neutral")),
                    topic=str(item.get("topic", "other")),
                    evidence=str(item.get("evidence", "")),
                    source_document_id=doc.id,
                    source_name=doc.source_name,
                    source_type=doc.source_type,
                    published_at=doc.published_at,
                    entity_names=list(item.get("entities", [])),
                )
                if len(claim.text) >= 5:
                    claims.append(claim)
            except (ValueError, TypeError):
                continue
        return claims

    def validate(self, result: AgentResult) -> bool:
        if not result.success:
            return False
        claims = result.data
        if not claims:
            return True
        return all(c.text and len(c.text) >= 5 for c in claims)
