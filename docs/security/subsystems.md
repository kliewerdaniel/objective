# Security Subsystems

## Feed Hardening

See [security/overview.md](overview.md) for input sanitization.

## Prompt Injection Resistance

```python
INJECTION_PATTERNS = [
    r"ignore (all )?(previous|above) instructions",
    r"(new )?system prompt",
    r"you are (now|not) ",
    r"override (mode|instructions)",
]
```

All extraction and analysis prompts are prepended with an immutable system prompt that is not user-controllable. User content (source documents) is strictly limited to the `<document>` section of the prompt and separated from instructions.

## Provenance

Every claim carries full provenance chain. See [architecture/claim_provenance_engine.md](../architecture/claim_provenance_engine.md).

## Hallucination Containment

Claims with confidence <0.3 are flagged as speculative and are never broadcast as fact. The broadcast system explicitly notes uncertainty: "Some sources indicate, though verification is limited."

## Audit Logging

All mutations are logged to SQLite `audit_log` table with timestamp, component, trace_id, and error context. Retention: 30 days.
