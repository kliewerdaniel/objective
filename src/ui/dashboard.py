"""Terminal dashboard using Rich (no alternate screen buffer)."""

import time
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text


console = Console()


def _make_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="top", size=8),
        Layout(name="middle", size=8),
        Layout(name="bottom"),
    )
    layout["top"].split_row(
        Layout(name="status"),
        Layout(name="metrics"),
    )
    layout["middle"].split_row(
        Layout(name="narratives"),
        Layout(name="broadcast"),
    )
    layout["bottom"].split_row(
        Layout(name="activity"),
    )
    return layout


def _render(orchestrator) -> Layout:
    o = orchestrator
    g = o.components.get("graph") if o else None
    layout = _make_layout()

    # Status
    state = o.state.value if o else "unknown"
    uptime = int(time.monotonic() - o.start_time) if o else 0
    agents = len(o.components.get("agents", {})) if o else 0
    status_text = Text()
    status_text.append("Status\n", style="bold")
    status_text.append(f"System: {state}\n", style="green" if state == "running" else "red")
    status_text.append(f"Uptime: {uptime}s\n")
    status_text.append(f"Agents: {agents}")
    layout["status"].update(Panel(status_text, border_style="green"))

    # Metrics
    metrics_text = Text()
    metrics_text.append("Metrics\n", style="bold")
    if g:
        try:
            e = g.count_nodes("Event")
            c = g.count_nodes("Claim")
            n = g.count_nodes("Narrative")
            co = g.count_edges("CONTRADICTS")
            s = g.count_nodes("Source")
            b = g.count_nodes("Broadcast")
            metrics_text.append(f"Events: {e}  Claims: {c}  Narratives: {n}\n")
            metrics_text.append(f"Contradictions: {co}  Sources: {s}  Broadcasts: {b}")
        except Exception:
            metrics_text.append("Graph error", style="red")
    else:
        metrics_text.append("Graph not connected", style="dim")
    layout["metrics"].update(Panel(metrics_text, border_style="cyan"))

    # Narratives
    nar_text = Text()
    nar_text.append("Narratives\n", style="bold")
    if g:
        try:
            rows = g.get_active_narratives(limit=5)
            if rows:
                for r in rows:
                    nar_text.append(f"  {r.get('n.label','?')[:40]} (drift: {r.get('n.drift_score',0):.2f})\n")
            else:
                nar_text.append("  None yet", style="dim")
        except Exception:
            nar_text.append("  Error", style="red")
    else:
        nar_text.append("  No data", style="dim")
    layout["narratives"].update(Panel(nar_text, border_style="yellow"))

    # Broadcast
    bc_text = Text()
    bc_text.append("Broadcast\n", style="bold")
    if g:
        try:
            b = g.get_latest_broadcast()
            if b:
                script = b.get("b.script", "")[:150]
                bc_text.append(f"{b.get('b.aired_at','')}\n{script}...")
            else:
                bc_text.append("No broadcasts yet", style="dim")
        except Exception:
            bc_text.append("Error", style="red")
    else:
        bc_text.append("No data", style="dim")
    layout["broadcast"].update(Panel(bc_text, border_style="magenta"))

    # Activity Log
    act_text = Text()
    act_text.append("Activity Log\n", style="bold")
    if o and o.activity_log:
        for e in o.activity_log[-12:]:
            sym = {"info": ".", "warn": "!", "error": "x"}.get(e["level"], ".")
            style = "red" if e["level"] == "error" else "yellow" if e["level"] == "warn" else ""
            act_text.append(f"  [{e['time']}] {sym} {e['message']}\n", style=style)
    else:
        act_text.append("  Waiting...", style="dim")
    layout["activity"].update(Panel(act_text, border_style="white"))

    return layout


class RichDashboard:
    """Non-blocking Rich dashboard that renders in-place."""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self._running = False

    def run(self):
        """Run the dashboard (blocking). Press Ctrl+C to stop."""
        self._running = True
        try:
            with Live(_render(self.orchestrator), console=console, refresh_per_second=1) as live:
                while self._running:
                    time.sleep(1)
                    try:
                        live.update(_render(self.orchestrator))
                    except Exception:
                        pass
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False

    def stop(self):
        self._running = False
