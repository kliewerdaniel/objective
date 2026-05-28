# Contributing

objective03 is an open infrastructure project. Contributions should align with the architectural philosophy: prefer practical, observable, deterministic systems over hype-driven architecture.

## Principles

1. **Graph-native thinking** — The data model is a graph from conception, not retrofitted.
2. **Deterministic over autonomous** — Agents are pipeline stages with clear inputs and outputs, not autonomous LLM loops.
3. **Observability is infrastructure** — Every component emits structured events. Logging is not optional.
4. **Fail degraded, not silently** — Components should degrade gracefully, logging the failure mode.
5. **Test the edges** — Focus tests on failure modes, boundary conditions, and data invariants.
6. **No buzzwords** — Don't add a message broker "because microservices." Add complexity only when measured.

## Getting Started

1. Read [docs/SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)
2. Read [docs/ARCHITECTURE.md](ARCHITECTURE.md)
3. Read the relevant architecture documents in `docs/architecture/`
4. Read the relevant agent specification in `docs/agents/`
5. Set up local development environment per [docs/deployment/local_setup.md](deployment/local_setup.md)

## Development Workflow

### Branch Strategy

- `main` — Stable, deployable
- `develop` — Integration branch
- `feature/*` — Feature branches from `develop`
- `fix/*` — Bug fix branches

### Commit Standards

- Conventional commits: `type(scope): description`
- Types: `feat`, `fix`, `docs`, `perf`, `test`, `refactor`, `chore`
- Scope: module name (e.g., `ingestion`, `graph`, `broadcast`)

### PR Requirements

- Passes all tests
- Includes test coverage for new code
- Includes documentation updates
- Includes structured logging
- Follows existing code patterns
- Branch is up to date with `develop`

## Code Standards

### Python

- Python 3.11+ type annotations on all functions
- Black formatting (88 chars)
- Import order: stdlib, third-party, local
- No wildcard imports
- Explicit over implicit
- F-strings preferred over `.format()` or `%`

### Agent Structure

Every agent must implement the base class from `src/agents/base.py`:

```python
class BaseAgent(ABC):
    @abstractmethod
    def run(self, context: AgentContext) -> AgentResult: ...
    @abstractmethod
    def validate(self, result: AgentResult) -> bool: ...
    @property
    def name(self) -> str: ...
```

### Testing

- pytest with coverage target >80%
- Test files mirror source structure (`tests/agents/test_claim_extractor.py`)
- Database operations use throwaway KuzuDB instances
- LLM calls are mocked in unit tests
- Integration tests use real models on a small scale

### Logging

Every agent and pipeline stage must emit structured logs:

```python
import structlog
logger = structlog.get_logger()

logger.info("claim.extracted", 
    claim_id=claim.id,
    source=claim.source,
    confidence=claim.confidence,
    entities=len(claim.entities),
    latency_ms=elapsed_ms,
)
```

## Documentation Standards

- Every module must have docstrings
- Every agent must have a corresponding spec in `docs/agents/`
- Schema changes require updates to `docs/schemas/`
- Architecture decisions must be recorded in `docs/architecture/`

## Review Process

1. Author opens PR against `develop`
2. Automated checks run (lint, typecheck, tests)
3. At least one maintainer reviews
4. Author addresses feedback
5. Squash merge to `develop`

## Conduct

Be precise. Be rigorous. Don't pretend certainty exists where it doesn't. The system's philosophy applies to its development process too.
