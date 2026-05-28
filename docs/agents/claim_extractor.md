# Claim Extractor Agent

## Overview

The claim extractor transforms normalized documents into atomic claims. This is the document → knowledge boundary. Claims are the atomic unit of information in the system.

## Responsibility

Extract factual claims from documents with:
- Confidence scoring
- Stance annotation
- Evidence extraction (direct quotes)
- Topic classification
- Entity mention identification

## Interface

```python
class ClaimExtractor(BaseAgent):
    name = "claim_extractor"
    timeout_seconds = 60.0
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Extract claims from a batch of documents."""
        documents: list[NormalizedDocument] = context.state["documents"]
        model = await context.models.get("extraction")
        
        all_claims = []
        stats = {"documents_processed": 0, "claims_extracted": 0, "errors": 0}
        
        for doc in documents:
            try:
                claims = await self._extract_from_document(doc, model)
                all_claims.extend(claims)
                stats["documents_processed"] += 1
                stats["claims_extracted"] += len(claims)
            except Exception as e:
                stats["errors"] += 1
                context.logger.error("extraction.failed", 
                    doc_id=doc.id, error=str(e))
        
        return AgentResult(
            success=True,
            data=all_claims,
            metrics=stats,
        )
    
    async def _extract_from_document(self, doc: NormalizedDocument, 
                                       model: LLMClient) -> list[Claim]:
        prompt = self._build_prompt(doc)
        response = await model.generate(
            prompt=prompt,
            temperature=0.0,
            max_tokens=2048,
            structured=True,
        )
        return self._parse_claims(response.text, doc)
    
    def validate(self, result: AgentResult) -> bool:
        if not result.success:
            return False
        claims = result.data
        if not claims:
            return True  # Zero claims is valid (no factual content)
        # Validate required fields
        for claim in claims:
            if not claim.text or len(claim.text) < 10:
                return False
            if not claim.evidence:
                return False
        return True
```

## Extraction Prompt

```
You are a claim extraction system. Extract atomic factual claims from the following document.

Rules:
- Extract ONLY verifiable factual claims, not opinions or speculation
- Each claim must be a single atomic statement
- Include the exact evidence text that supports each claim
- Rate confidence 0.0-1.0 based on clarity and specificity
- Classify stance: "support", "neutral", "oppose", or "uncertain"
- Extract all mentioned entities (people, orgs, locations, events)
- Classify topic into one of: conflict, politics, disaster, economy, science, health, technology, environment, crime, other

Document:
Title: {doc.title}
Source: {doc.source_name}
Published: {doc.published_at}
Body:
{doc.body}

Output ONLY valid JSON array:
[
  {{
    "text": "The explosion resulted in 47 confirmed casualties.",
    "confidence": 0.92,
    "stance": "neutral",
    "entities": [],
    "topic": "conflict",
    "evidence": "The explosion resulted in 47 confirmed casualties, according to hospital officials."
  }}
]
```

## Claim Model

```python
@dataclass
class Claim:
    id: str                          # UUID, generated after extraction
    text: str                        # Atomic claim text
    confidence: float                # 0.0-1.0
    stance: str                      # support, neutral, oppose, uncertain
    topic: str                       # conflict, politics, disaster, etc.
    evidence: str                    # Direct quote from source
    source_document_id: str          # Link to source document
    source_name: str
    source_type: str
    published_at: datetime
    entities: list[EntityMention]    # Entity mentions with spans
    embedding: Optional[list[float]] # Set after extraction
    timestamp: datetime              # When extracted
```

## Claim Quality Criteria

| Criterion | Requirement | Enforcement |
|-----------|-------------|-------------|
| Atomicity | One factual statement per claim | Prompt instruction + validation |
| Evidence | Must include supporting quote from source | Validation rejects null evidence |
| Confidence | Must be 0.0-1.0 | Type validation |
| Stance | Must be one of four values | Enum validation |
| Length | 20-500 characters | Validation range |
| Verifiability | Must be a claim about reality | Prompt instruction |

## Performance Characteristics

| Metric | Expected | Notes |
|--------|----------|-------|
| Claims per document | 3-15 | Depends on document length and density |
| Latency per document | 15-60s | Qwen 7B Q4 on M4 Pro |
| RAM usage | ~5GB | Model loaded in GPU memory |
| Batch size | 1-4 documents | Context window limited |
| Error rate | <5% | Model parsing errors, timeouts |
| False positive rate | ~10% | Non-factual content extracted as claims |
