"""Scoring utilities."""

from src.models.types import Claim


def compute_claim_confidence(claim: Claim, extraction_score: float = 0.5) -> float:
    return min(1.0, extraction_score * (1.0 if claim.evidence else 0.5))


def compute_event_importance(claim_count: int, source_count: int,
                              contradiction_count: int = 0) -> float:
    volume = min(claim_count / 50, 1.0) * 0.3
    diversity = min(source_count / 10, 1.0) * 0.25
    contested = min(contradiction_count / max(claim_count, 1), 1.0) * 0.15
    return min(1.0, volume + diversity + contested + 0.3)
