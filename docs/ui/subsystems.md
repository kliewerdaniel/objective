# UI Subsystems

## Layout

4-panel design: (1) Ingestion Feed + Active Narratives on left, (2) Broadcast Status + System Metrics on right, (3) Log panel at bottom. Optional fifth panel for contradiction map.

## Dashboards

Four dashboard views switchable via keyboard shortcuts:
- **Main** (default): All 4 panels as described
- **Graph**: Full-screen graph statistics, node/edge counts, growth trends
- **Contradiction**: Contradiction map showing active contradictions, resolution rates
- **Log**: Full-screen structured log viewer with filters

## Wireframes

See [ui/overview.md](overview.md) for the terminal mockup layout. The design uses a dark theme (#0a0a0a background, #333 borders, green/amber/red status indicators).

## Interaction Flow

The UI is primarily read-only. Keyboard shortcuts:
- `1-4`: Switch dashboard
- `q`: Quit (triggers graceful shutdown)
- `r`: Refresh all panels
- `/`: Open log search filter

Configuration is file-based (config.yaml), not UI-driven. This reinforces the system philosophy: the UI is an observability layer, not a control layer.
