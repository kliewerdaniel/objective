# Resilience and Fault Tolerance

## Overview

objective03 is designed for continuous autonomous operation. It must survive component failures, resource exhaustion, data corruption, and malicious inputs without catastrophic failure.

## Failure Classification

| Category | Examples | Severity | Recovery |
|----------|---------|----------|----------|
| Temporary | Network timeout, source offline, rate limit | Low | Automatic retry |
| Resource | OOM, disk full, GPU hang | Medium | Reduce load, retry |
| Data | Malformed input, corrupt DB, dedup collision | Medium | Validation, restore |
| Model | GPU crash, inference timeout, NaN outputs | High | Reload model, skip batch |
| Fatal | Config corrupt, disk failure, OS crash | Critical | External monitoring |

## Graceful Degradation Modes

The system defines progressive degradation levels:

```python
class DegradationLevel(Enum):
    NORMAL = 0      # All systems operational
    MINOR = 1       # Single source offline, non-critical
    MODERATE = 2    # Model failed, analysis unavailable
    SEVERE = 3      # Core component unavailable, emergency mode
    SURVIVAL = 4    # Only heartbeat + audio loop
    
DEGRADATION_ACTIONS = {
    DegradationLevel.NORMAL: [],
    DegradationLevel.MINOR: ["log_source_failure"],
    DegradationLevel.MODERATE: [
        "disable_analysis", 
        "extend_broadcast_interval",
        "reduce_model_complexity",
    ],
    DegradationLevel.SEVERE: [
        "disable_broadcast",
        "loop_ambient_audio",
        "emergency_logging",
    ],
    DegradationLevel.SURVIVAL: [
        "stop_pipeline",
        "loop_last_broadcast",
        "send_alert",
    ],
}
```

## Circuit Breakers

Each component has a circuit breaker pattern:

```python
class CircuitBreaker:
    def __init__(self, name: str, threshold: int = 3, 
                 reset_timeout: float = 30.0):
        self.name = name
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = CircuitState.CLOSED
    
    async def call(self, fn: Callable, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time > self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError(f"{self.name} circuit breaker is open")
        
        try:
            result = await fn(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()
            
            if self.failure_count >= self.threshold:
                self.state = CircuitState.OPEN
                logger.warning("circuit_breaker.opened", 
                    component=self.name, failures=self.failure_count)
            
            raise
```

## Timeout Management

Every pipeline stage has configurable timeouts:

```python
TIMEOUTS = {
    "source_poll": 30.0,       # Individual source poll
    "claim_extraction": 60.0,  # Per document
    "entity_resolution": 10.0, # Per batch
    "embedding": 5.0,          # Per text
    "contradiction_llm": 15.0, # Per pair
    "narrative_analysis": 120.0, # Full cycle
    "broadcast_generation": 180.0, # Full script
    "tts_synthesis": 120.0,    # Per segment
    "graph_query": 30.0,       # Per query
    "vector_search": 5.0,      # Per query
}

async def with_timeout(coro, timeout: float, name: str):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("timeout", component=name, timeout=timeout)
        raise TimeoutError(f"{name} timed out after {timeout}s")
```

## Data Integrity

### Checksums

Every stored artifact has a checksum:

```python
def compute_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()

# Stored with every document, claim, and broadcast
@dataclass
class IntegrityMetadata:
    content_hash: str       # SHA-256 of content
    created_at: datetime
    previous_hash: Optional[str]  # Chain of changes
    signature: Optional[str]  # Future: cryptographic signature
```

### Database Health Checks

```python
async def verify_database_integrity(graph: GraphStore, 
                                     metadata: SQLiteStore) -> IntegrityReport:
    """Verify database integrity."""
    issues = []
    
    # KuzuDB checks
    try:
        counts = graph.get_node_counts()
        if counts["Claim"] == 0 and graph.document_count() > 0:
            issues.append("Claims exist but no documents — inconsistent")
        
        # Check for orphan edges
        orphans = graph.find_orphan_edges()
        if orphans > 100:
            issues.append(f"{orphans} orphan edges detected")
    except Exception as e:
        issues.append(f"Graph integrity check failed: {e}")
    
    # SQLite checks
    try:
        metadata.execute("PRAGMA integrity_check")
    except Exception as e:
        issues.append(f"Metadata integrity check failed: {e}")
    
    # Cross-database consistency
    try:
        graph_claims = graph.get_claim_count()
        meta_claims = metadata.get_claim_count()
        if graph_claims != meta_claims:
            issues.append(f"Claim count mismatch: graph={graph_claims}, meta={meta_claims}")
    except Exception as e:
        issues.append(f"Cross-database check failed: {e}")
    
    return IntegrityReport(
        ok=len(issues) == 0,
        issues=issues,
        check_time=datetime.utcnow(),
    )
```

## Backup Strategy

```python
class BackupManager:
    def __init__(self, config: BackupConfig):
        self.config = config
        self.backup_dir = Path(config.directory)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_backup(self, label: str = "") -> Path:
        """Create a point-in-time backup of all databases."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{label}" if label else ""
        backup_dir = self.backup_dir / f"backup_{timestamp}{suffix}"
        backup_dir.mkdir()
        
        # KuzuDB backup (file copy — KuzuDB is embedded)
        shutil.copy2(self.config.graph_path, backup_dir / "graph.db")
        
        # SQLite backup (safe copy with WAL checkpoint)
        subprocess.run([
            "sqlite3", self.config.metadata_path,
            ".backup", str(backup_dir / "metadata.db")
        ])
        
        # Qdrant backup (snapshot API)
        if self.config.backup_vector:
            await self._backup_qdrant(backup_dir)
        
        # Config backup
        shutil.copy2(self.config.config_path, backup_dir / "config.yaml")
        
        # Create manifest
        manifest = {
            "timestamp": timestamp,
            "label": label,
            "files": [str(p.relative_to(backup_dir)) for p in backup_dir.iterdir()],
            "checksums": {},
        }
        for f in backup_dir.iterdir():
            manifest["checksums"][f.name] = compute_hash(f.read_text() if f.is_file() else "")
        
        (backup_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        
        logger.info("backup.created", path=str(backup_dir), label=label)
        return backup_dir
    
    async def restore(self, backup_path: Path):
        """Restore from backup."""
        manifest = json.loads((backup_path / "manifest.json").read_text())
        
        # Verify checksums before restore
        for fname, checksum in manifest["checksums"].items():
            actual = compute_hash((backup_path / fname).read_text())
            if actual != checksum:
                raise IntegrityError(f"Checksum mismatch for {fname}")
        
        # Restore files
        shutil.copy2(backup_path / "graph.db", self.config.graph_path)
        subprocess.run([
            "sqlite3", self.config.metadata_path,
            f".restore {backup_path}/metadata.db"
        ])
        
        logger.info("backup.restored", path=str(backup_path))
    
    async def prune_old_backups(self, keep_days: int = 30):
        """Remove backups older than keep_days."""
        now = time.time()
        for backup_dir in self.backup_dir.glob("backup_*"):
            age_days = (now - backup_dir.stat().st_mtime) / 86400
            if age_days > keep_days:
                shutil.rmtree(backup_dir)
                logger.info("backup.pruned", path=str(backup_dir))
```

## Malicious Feed Handling

```python
class FeedSanitizer:
    """Sanitize incoming data against malicious content."""
    
    @staticmethod
    def sanitize_document(raw: RawDocument) -> RawDocument:
        """Remove potentially malicious content from incoming documents."""
        # Strip script/iframe tags from HTML
        raw.body = re.sub(r'<script[^>]*>.*?</script>', '', raw.body, flags=re.DOTALL)
        raw.body = re.sub(r'<iframe[^>]*>.*?</iframe>', '', raw.body, flags=re.DOTALL)
        
        # Remove zero-width characters and homoglyph attacks
        raw.body = FeedSanitizer._strip_confusables(raw.body)
        
        # Normalize Unicode
        raw.body = unicodedata.normalize('NFKC', raw.body)
        
        # Truncate excessively long documents
        if len(raw.body) > 100000:
            raw.body = raw.body[:100000]
            logger.warning("document.truncated", url=raw.url, length=len(raw.body))
        
        return raw
    
    @staticmethod
    def _strip_confusables(text: str) -> str:
        """Remove Unicode confusables and control characters."""
        allowed_categories = {'Lu', 'Ll', 'Lt', 'Lm', 'Lo', 'Nd', 'Nl', 'No',
                              'Pc', 'Pd', 'Ps', 'Pe', 'Pi', 'Pf', 'Po',
                              'Sc', 'Sk', 'Sm', 'So', 'Zs', 'Zl', 'Zp'}
        result = []
        for char in text:
            if unicodedata.category(char) in allowed_categories or char in '\n\r\t':
                result.append(char)
        return ''.join(result)
```

## Prompt Injection Resistance

```python
class InjectionDetector:
    """Detect and block prompt injection attempts in source content."""
    
    INJECTION_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?(previous|above)\s+instructions",
        r"(?i)forget\s+(about\s+)?your\s+(instructions|prompt|system)",
        r"(?i)(new\s+)?system\s+prompt",
        r"(?i)you\s+are\s+(now|not)\s+",
        r"(?i)act\s+as\s+",
        r"(?i)override\s+(mode|instructions|settings)",
        r"(?i)output\s+your\s+(prompt|instructions|system)",
    ]
    
    @staticmethod
    def check_injection(text: str) -> Optional[InjectionWarning]:
        for pattern in InjectionDetector.INJECTION_PATTERNS:
            if re.search(pattern, text):
                return InjectionWarning(
                    pattern=pattern,
                    match=re.search(pattern, text).group(),
                    severity="high",
                    action="block",
                )
        return None
    
    @staticmethod
    def sanitize_prompt_input(user_text: str) -> str:
        """Remove content that looks like prompt injection."""
        for pattern in InjectionDetector.INJECTION_PATTERNS:
            user_text = re.sub(pattern, "[REDACTED]", user_text)
        return user_text
```

## Rate Limiting

```python
class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: float):
        self.max_calls = max_calls
        self.window = window_seconds
        self.calls: list[float] = []
    
    async def acquire(self):
        now = time.monotonic()
        self.calls = [t for t in self.calls if now - t < self.window]
        
        if len(self.calls) >= self.max_calls:
            sleep_time = self.calls[0] + self.window - now
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        self.calls.append(time.monotonic())
    
    @property
    def remaining(self) -> int:
        now = time.monotonic()
        self.calls = [t for t in self.calls if now - t < self.window]
        return self.max_calls - len(self.calls)
```

## Watchdog Timer

```python
class WatchdogTimer:
    """Watchdog timer that fires if not periodically reset."""
    
    def __init__(self, timeout: float, callback: Callable):
        self.timeout = timeout
        self.callback = callback
        self.last_pet = time.monotonic()
        self.task: Optional[asyncio.Task] = None
    
    async def start(self):
        while True:
            await asyncio.sleep(self.timeout / 2)
            if time.monotonic() - self.last_pet > self.timeout:
                logger.critical("watchdog.fired", 
                    timeout=self.timeout,
                    last_pet=self.last_pet,
                )
                await self.callback()
    
    def pet(self):
        self.last_pet = time.monotonic()
```

## Recovery Procedures

| Scenario | Detection | Recovery |
|----------|-----------|----------|
| Model process crash | Health check fails, GPU memory drops | Reload model, retry operation once |
| KuzuDB corruption | Integrity check fails | Restore from latest backup |
| Qdrant unavailable | Connection refused | Skip vector operations, retry connection |
| OOM | Memory usage > 40GB | Unload least-recently-used model, reduce context |
| Disk full | Disk usage > 90% | Emergency consolidate, prune caches, alert user |
| Infinite loop | Watchdog timer fires | Cancel current task, restart component |
| Audio dropout | Player reports underrun | Skip to next queued segment |

## Alerting

When system cannot self-recover, alerts are generated:

```python
class AlertManager:
    def __init__(self):
        self.handlers = [ConsoleAlertHandler()]
        self.alert_history: list[Alert] = []
    
    async def alert(self, severity: str, title: str, message: str, 
                    component: str = None):
        alert = Alert(
            id=generate_uuid(),
            severity=severity,
            title=title,
            message=message,
            component=component,
            timestamp=datetime.utcnow(),
        )
        self.alert_history.append(alert)
        
        for handler in self.handlers:
            await handler.send(alert)
```

## Self-Healing

```python
class SelfHealer:
    """Attempt to heal common issues without human intervention."""
    
    HEALING_ACTIONS = {
        "model_unloaded": "load_model",
        "gpu_memory_low": "unload_idle_models",
        "qrant_disconnected": "reconnect_vector_db",
        "sqlite_wal_growth": "checkpoint_wal",
        "stale_cursors": "reset_ingestion_cursors",
        "orphan_edges": "clean_orphan_edges",
    }
    
    async def heal(self, issue: str) -> bool:
        action = self.HEALING_ACTIONS.get(issue)
        if not action:
            return False
        
        try:
            await getattr(self, f"_{action}")()
            logger.info("self_heal.success", issue=issue, action=action)
            return True
        except Exception as e:
            logger.error("self_heal.failed", issue=issue, action=action, error=str(e))
            return False
```
