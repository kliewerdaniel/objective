# Evaluation Documentation

## Overview

The evaluation system measures quality across all dimensions of the system. It runs continuously, tracking metrics over time to detect degradation, anomalies, and improvement opportunities.

## Metrics

### Claim Quality

| Metric | Definition | Target | Measurement |
|--------|-----------|--------|-------------|
| Extraction confidence | Average confidence score | >0.7 | Sampled daily |
| Stance distribution | Balance across stances | All four present | Daily |
| Duplicate rate | Duplicate claims / total | <5% | Weekly |
| False claim rate | Claims without valid evidence | <2% | Sampled weekly |
| Entity coverage | Claims with entities / total | >80% | Daily |

### Contradiction Quality

| Metric | Definition | Target | Measurement |
|--------|-----------|--------|-------------|
| Detection accuracy | Manual review of samples | >90% | Weekly |
| False positive rate | False contradictions / total | <10% | Weekly |
| Resolution rate | Resolved / total contradictions | >20% within 7d | Weekly |
| Type distribution | Balance across types | All types present | Daily |

### Broadcast Quality

| Metric | Definition | Target | Measurement |
|--------|-----------|--------|-------------|
| Generation interval | Time between broadcasts | <30 min | Continuous |
| Script length | Words per broadcast | 500-3000 | Per broadcast |
| Contradiction coverage | Broadcasts mentioning contradictions | >50% | Weekly |
| Uncertainty coverage | Broadcasts mentioning uncertainty | >80% | Weekly |
| Callback accuracy | References to valid prior broadcasts | 100% | Per broadcast |

### System Health

| Metric | Definition | Target | Measurement |
|--------|-----------|--------|-------------|
| CPU usage | Average CPU utilization | <70% | Continuous |
| Memory usage | RSS / 48GB | <80% | Continuous |
| Disk usage | Data directory / limit | <80% | Continuous |
| Source availability | Sources returning data / total | >80% | Continuous |
| Pipeline latency | End-to-end extraction time | <60s/doc | Per document |
| Error rate | Errors / total operations | <5% | Continuous |

## Evaluation Methodology

```python
class EvaluationMethodology:
    """Methodology for evaluating system components."""
    
    @staticmethod
    def sample_for_review(population: list, sample_size: int = 100) -> list:
        """Stratified random sampling for human review."""
        if len(population) <= sample_size:
            return population
        
        # Stratify by source type for representative sample
        stratified = defaultdict(list)
        for item in population:
            stratified[item.get("source_type", "unknown")].append(item)
        
        sample = []
        per_stratum = sample_size // len(stratified)
        for stratum, items in stratified.items():
            sample.extend(random.sample(items, min(per_stratum, len(items))))
        
        return sample
```

## Evaluation Engine

See [agents/evaluation_engine.md](../agents/evaluation_engine.md) for implementation.
