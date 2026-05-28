# Claim Extraction Pipeline

## Pipeline Flow

```
Normalized Document
    │
    ▼
Truncation (context window management)
    │
    ▼
Prompt Construction
    │
    ▼
LLM Inference (Qwen 7B Q4)
    │
    ▼
Response Parsing (structured JSON)
    │
    ▼
Claim Validation
    │
    ▼
Entity Extraction (separate model)
    │
    ▼
Claim + Entity Pairing
    │
    ▼
Claim Deduplication (semantic)
    │
    ▼
Output to Graph Update
```

## Prompt Design

```
System: You are a claim extraction system. Extract atomic factual claims.
Rules:
- Atomic: one verifiable fact per claim
- Evidence: include supporting quote
- Confidence: 0.0-1.0 based on specificity
- Stance: support/neutral/oppose/uncertain
- No opinions, speculation, or editorial content

Input: [document title and body]

Output: JSON array of claims with fields: text, confidence, stance, topic, evidence, entities
```

## Structured Output

The model is constrained to output valid JSON via GBNF grammar:

```
root ::= "[" ws claim ("," ws claim)* ws "]"
claim ::= "{" ws members "}"
members ::= member ("," ws member)*
member ::= string ":" value
```

## Validation

```python
def validate_claim(claim: dict) -> tuple[bool, str]:
    if not claim.get("text") or len(claim["text"]) < 10:
        return False, "Claim text too short"
    if not claim.get("evidence"):
        return False, "Missing evidence"
    if "confidence" not in claim or not 0 <= claim["confidence"] <= 1:
        return False, "Invalid confidence"
    if claim.get("stance") not in ("support", "neutral", "oppose", "uncertain"):
        return False, "Invalid stance"
    return True, "OK"
```

## Performance

| Metric | Value | Notes |
|--------|-------|-------|
| Claims/doc | 3-15 | Depends on doc length |
| Latency/doc | 15-60s | Qwen 7B Q4 |
| Max doc length | 4096 tokens | Context window limit |
| Extraction model | Qwen 2.5 7B Q4_K_M | 32 GPU layers |
| RAM | ~5GB | When model is loaded |
| Throughput | 4-8 docs/min | Single concurrent |
