# Terminal User Interface

## Design Philosophy

The terminal UI is the primary human interface to objective03. It is designed to be:
- **Informational** — Shows system state, not just raw data
- **Atmospheric** — Matches the cold, detached aesthetic
- **Monitorable** — At-a-glance status for all subsystems
- **Non-interactive** — Primarily read-only, config via files

## Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  objective03 v0.1.0              RUNNING         uptime: 4d 12h    │
├────────────────────┬────────────────────┬──────────────────────────┤
│  INGESTION FEED    │  BROADCAST STATUS  │  SYSTEM METRICS          │
│                    │                    │                          │
│  NYT World    [OK] │  Current: 14:30    │  Events:      127       │
│  BBC World    [OK] │  Next:    14:45    │  Claims:    14,892      │
│  r/worldnews  [OK] │  Queue:   2 segs   │  Sources:   3,421       │
│  r/geopolitics [OK]│  Cache:   4 segs   │  Narratives: 43         │
│  BBC YouTube  [OK] │                    │  Contradictions: 892    │
│  WhiteHouse   [WARN]│                   │                          │
│                    │  ───────────────  │  Memory:    21.4 GB     │
│  Last poll: 23s    │  Now playing: ✓    │  Graph:     3.2 GB      │
│  Docs/hour: 47     │                    │  Disk:      14% used    │
├────────────────────┴────────────────────┴──────────────────────────┤
│  ACTIVE NARRATIVES                         CONTRADICTION MAP       │
│                                                                     │
│  ● Eastern Mediterranean Maritime Dispute (drift: 0.34 ▲)         │
│  ● European Energy Policy Realignment (drift: 0.21 ▲)             │
│  ○ South China Sea Resource Claims (drift: 0.12)                  │
│                                                                     │
├────────────────────────────────────────────────────────────────────┤
│  LOG                                                    LEVEL TIME │
│  [14:29:47] ingestion.poll.completed  47 docs, 0 errors    INFO   │
│  [14:29:52] extraction.completed      127 claims extracted INFO   │
│  [14:30:01] contradiction.found       DIRECT contra 0.89  INFO   │
│  [14:30:05] broadcast.generated       Script #142        INFO   │
└────────────────────────────────────────────────────────────────────┘
```

## Textual Implementation

```python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, RichLog, DataTable
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive

class Objective03Dashboard(App):
    TITLE = "objective03"
    CSS = """
    Screen {
        background: #0a0a0a;
    }
    #feed-panel {
        border: solid #333;
        height: 100%;
    }
    #metrics-panel {
        border: solid #333;
    }
    #broadcast-panel {
        border: solid #333;
    }
    #narrative-panel {
        border: solid #333;
    }
    #log-panel {
        border: solid #333;
        height: 8;
    }
    .ok { color: #0a0; }
    .warn { color: #aa0; }
    .error { color: #a00; }
    """
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="left-panel"):
                yield Static(id="feed-panel")
                yield Static(id="narrative-panel")
            with Vertical(id="right-panel"):
                yield Static(id="broadcast-panel")
                yield Static(id="metrics-panel")
        yield RichLog(id="log-panel", highlight=True)
        yield Footer()
    
    def on_mount(self):
        self.set_interval(1.0, self.update_metrics)
    
    async def update_metrics(self):
        # Update all panels from shared state
        pass
```

## Panels

### Ingestion Feed Panel
- Source name, status indicator (OK/WARN/ERROR)
- Time since last poll
- Documents per hour
- Error count

### Broadcast Status Panel
- Current segment name
- Next scheduled generation
- Queue depth
- Cache status
- Now playing indicator

### System Metrics Panel
- Node counts (events, claims, sources, narratives, contradictions)
- Memory usage
- Graph size
- Disk usage

### Active Narratives Panel
- Narrative label
- Drift score with trend indicator
- Active indicator

### Log Panel
- Last 20 log entries
- Color-coded by level
- Auto-scroll

## Refresh Intervals

| Panel | Interval | Source |
|-------|----------|--------|
| Feed status | 1s | SQLite + in-memory state |
| Broadcast | 1s | Audio queue state |
| Metrics | 5s | KuzuDB counts |
| Narratives | 10s | KuzuDB query |
| Log | 1s | Log buffer |
