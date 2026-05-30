"""Test Dashboard - Web-based monitoring for objective03.

Run: python tests/dashboard.py
Open: http://localhost:8080
"""

import json
import subprocess
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs

PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_FILE = PROJECT_ROOT / "tests" / "last_results.json"
LOG_FILE = PROJECT_ROOT / "tests" / "dashboard.log"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>objective03 - Test Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'SF Mono', 'Fira Code', monospace; background: #0a0a0a; color: #e0e0e0; }
  .header { background: #111; border-bottom: 1px solid #333; padding: 16px 24px; display: flex; align-items: center; gap: 16px; }
  .header h1 { font-size: 18px; color: #00ff88; font-weight: 600; }
  .header .status { font-size: 12px; color: #888; }
  .container { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 24px; max-width: 1400px; margin: 0 auto; }
  .panel { background: #111; border: 1px solid #222; border-radius: 8px; overflow: hidden; }
  .panel-header { background: #1a1a1a; padding: 12px 16px; border-bottom: 1px solid #222; font-size: 13px; font-weight: 600; color: #aaa; text-transform: uppercase; letter-spacing: 1px; display: flex; justify-content: space-between; align-items: center; }
  .panel-body { padding: 16px; max-height: 400px; overflow-y: auto; }
  .full-width { grid-column: 1 / -1; }
  .test-result { padding: 8px 12px; border-radius: 4px; margin-bottom: 4px; font-size: 13px; display: flex; justify-content: space-between; align-items: center; }
  .test-pass { background: #0a2a0a; border-left: 3px solid #00ff88; }
  .test-fail { background: #2a0a0a; border-left: 3px solid #ff4444; }
  .test-error { background: #2a1a0a; border-left: 3px solid #ffaa00; }
  .test-name { color: #ccc; }
  .test-time { color: #666; font-size: 11px; }
  .badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
  .badge-pass { background: #00ff8822; color: #00ff88; }
  .badge-fail { background: #ff444422; color: #ff4444; }
  .badge-error { background: #ffaa0022; color: #ffaa00; }
  .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
  .stat-card { background: #1a1a1a; border-radius: 6px; padding: 16px; text-align: center; }
  .stat-value { font-size: 28px; font-weight: 700; color: #00ff88; }
  .stat-label { font-size: 11px; color: #666; margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; }
  .stat-value.warn { color: #ffaa00; }
  .stat-value.error { color: #ff4444; }
  .log-entry { padding: 6px 0; border-bottom: 1px solid #1a1a1a; font-size: 12px; line-height: 1.6; }
  .log-time { color: #555; }
  .log-level-info { color: #00aaff; }
  .log-level-warn { color: #ffaa00; }
  .log-level-error { color: #ff4444; }
  .log-level-pass { color: #00ff88; }
  .btn { padding: 8px 16px; border: 1px solid #333; background: #1a1a1a; color: #ccc; border-radius: 4px; cursor: pointer; font-size: 12px; font-family: inherit; transition: all 0.2s; }
  .btn:hover { background: #222; border-color: #00ff88; color: #00ff88; }
  .btn:active { transform: scale(0.98); }
  .btn.running { opacity: 0.5; pointer-events: none; }
  .summary-bar { display: flex; gap: 12px; align-items: center; }
  .schema-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .schema-table th { text-align: left; padding: 8px 12px; background: #1a1a1a; color: #888; font-weight: 600; }
  .schema-table td { padding: 6px 12px; border-bottom: 1px solid #1a1a1a; }
  .schema-table .type { color: #00aaff; }
  .error-detail { background: #1a0a0a; border: 1px solid #331111; border-radius: 4px; padding: 12px; margin-top: 8px; font-size: 12px; color: #ff8888; white-space: pre-wrap; max-height: 200px; overflow-y: auto; }
  .pipeline-step { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
  .pipeline-dot { width: 8px; height: 8px; border-radius: 50%; }
  .dot-ok { background: #00ff88; }
  .dot-err { background: #ff4444; }
  .dot-skip { background: #555; }
  .refresh-indicator { width: 6px; height: 6px; border-radius: 50%; background: #00ff88; animation: pulse 2s infinite; }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
</style>
</head>
<body>
<div class="header">
  <h1>objective03</h1>
  <span class="status">Test Dashboard</span>
  <div class="refresh-indicator" title="Auto-refreshing"></div>
</div>
<div class="container">
  <div class="panel full-width">
    <div class="panel-header">
      <span>System Overview</span>
      <div class="summary-bar">
        <span id="last-run" style="color:#555;font-size:11px;">No tests run yet</span>
        <button class="btn" onclick="runTests()" id="run-btn">Run Tests</button>
        <button class="btn" onclick="refresh()">Refresh</button>
      </div>
    </div>
    <div class="panel-body">
      <div class="stat-grid" id="stats"></div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-header">
      <span>Test Results</span>
      <span id="test-summary" style="color:#555;font-size:11px;"></span>
    </div>
    <div class="panel-body" id="test-results"></div>
  </div>

  <div class="panel">
    <div class="panel-header">
      <span>Pipeline Status</span>
    </div>
    <div class="panel-body" id="pipeline"></div>
  </div>

  <div class="panel full-width">
    <div class="panel-header">
      <span>Graph Schema</span>
    </div>
    <div class="panel-body" id="schema"></div>
  </div>

  <div class="panel full-width">
    <div class="panel-header">
      <span>Activity Log</span>
      <button class="btn" onclick="clearLog()">Clear</button>
    </div>
    <div class="panel-body" id="log-viewer"></div>
  </div>

  <div class="panel full-width" id="error-panel" style="display:none;">
    <div class="panel-header">
      <span style="color:#ff4444;">Errors</span>
    </div>
    <div class="panel-body" id="error-details"></div>
  </div>
</div>

<script>
let logs = [];
let running = false;

function addLog(level, msg) {
  const now = new Date().toISOString().slice(11, 23);
  logs.push({ time: now, level, msg });
  if (logs.length > 200) logs.shift();
  renderLog();
}

function renderLog() {
  const el = document.getElementById('log-viewer');
  el.innerHTML = logs.slice().reverse().map(l =>
    `<div class="log-entry"><span class="log-time">${l.time}</span> <span class="log-level-${l.level}">[${l.level.toUpperCase()}]</span> ${l.msg}</div>`
  ).join('');
}

function clearLog() { logs = []; renderLog(); }

async function refresh() {
  try {
    addLog('info', 'Refreshing data...');
    const res = await fetch('/api/status');
    const data = await res.json();

    // Stats
    document.getElementById('stats').innerHTML = data.stats.map(s =>
      `<div class="stat-card"><div class="stat-value ${s.class || ''}">${s.value}</div><div class="stat-label">${s.label}</div></div>`
    ).join('');

    // Pipeline
    document.getElementById('pipeline').innerHTML = data.pipeline.map(p =>
      `<div class="pipeline-step"><div class="pipeline-dot dot-${p.status}"></div><span>${p.name}</span><span style="color:#555;font-size:11px;margin-left:auto;">${p.detail}</span></div>`
    ).join('');

    // Schema
    if (data.schema) {
      let html = '<table class="schema-table"><tr><th>Node Tables</th><th>Columns</th></tr>';
      data.schema.nodes.forEach(n => {
        html += `<tr><td>${n.name}</td><td class="type">${n.columns}</td></tr>`;
      });
      html += '<tr><th colspan="2" style="padding-top:12px;">Edge Tables</th></tr>';
      data.schema.edges.forEach(e => {
        html += `<tr><td>${e.name}</td><td class="type">${e.detail}</td></tr>`;
      });
      html += '</table>';
      document.getElementById('schema').innerHTML = html;
    }

    addLog('info', 'Refresh complete');
  } catch(e) {
    addLog('error', 'Refresh failed: ' + e.message);
  }
}

async function runTests() {
  if (running) return;
  running = true;
  const btn = document.getElementById('run-btn');
  btn.textContent = 'Running...';
  btn.classList.add('running');

  addLog('info', 'Starting test run...');

  try {
    const res = await fetch('/api/run-tests', { method: 'POST' });
    const data = await res.json();
    addLog('pass', `Tests complete: ${data.passed} passed, ${data.failed} failed, ${data.errors} errors`);

    document.getElementById('last-run').textContent = `Last run: ${new Date().toLocaleTimeString()}`;

    // Render test results
    const el = document.getElementById('test-results');
    el.innerHTML = data.results.map(r => {
      const cls = r.outcome === 'passed' ? 'test-pass' : r.outcome === 'failed' ? 'test-fail' : 'test-error';
      const badge = r.outcome === 'passed' ? 'badge-pass' : r.outcome === 'failed' ? 'badge-fail' : 'badge-error';
      return `<div class="test-result ${cls}">
        <span class="test-name">${r.name}</span>
        <span><span class="badge ${badge}">${r.outcome}</span> <span class="test-time">${r.duration}s</span></span>
      </div>`;
    }).join('');

    document.getElementById('test-summary').innerHTML =
      `<span class="badge badge-pass">${data.passed} passed</span> ` +
      (data.failed > 0 ? `<span class="badge badge-fail">${data.failed} failed</span> ` : '') +
      (data.errors > 0 ? `<span class="badge badge-error">${data.errors} errors</span>` : '');

    // Show errors
    const errorPanel = document.getElementById('error-panel');
    const errorDetails = document.getElementById('error-details');
    const failures = data.results.filter(r => r.outcome !== 'passed' && r.longrepr);
    if (failures.length > 0) {
      errorPanel.style.display = 'block';
      errorDetails.innerHTML = failures.map(f =>
        `<div style="margin-bottom:12px;"><strong style="color:#ff8888;">${f.name}</strong><div class="error-detail">${escapeHtml(f.longrepr)}</div></div>`
      ).join('');
    } else {
      errorPanel.style.display = 'none';
    }

    // Update stats after tests
    refresh();
  } catch(e) {
    addLog('error', 'Test run failed: ' + e.message);
  } finally {
    running = false;
    btn.textContent = 'Run Tests';
    btn.classList.remove('running');
  }
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// Auto-refresh every 30s
setInterval(refresh, 30000);
refresh();
addLog('info', 'Dashboard initialized');
</script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/' or parsed.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode())
        elif parsed.path == '/api/status':
            self.send_json(self.get_status())
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/run-tests':
            result = self.run_tests()
            self.send_json(result)
        else:
            self.send_error(404)

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def get_status(self):
        try:
            sys.path.insert(0, str(PROJECT_ROOT))
            from src.database.graph import GraphStore
            from src.database.metadata import MetadataStore

            graph_path = str(PROJECT_ROOT / ".objective03" / "test_graph_dashboard.db")
            metadata_path = str(PROJECT_ROOT / ".objective03" / "test_metadata_dashboard.db")

            graph = GraphStore(graph_path)
            metadata = MetadataStore(metadata_path)

            stats = [
                {"label": "Documents", "value": graph.count_nodes("Document")},
                {"label": "Claims", "value": graph.count_nodes("Claim")},
                {"label": "Events", "value": graph.count_nodes("Event")},
                {"label": "Narratives", "value": graph.count_nodes("Narrative")},
                {"label": "Contradictions", "value": graph.count_edges("CONTRADICTS")},
                {"label": "Sources", "value": graph.count_nodes("Source")},
                {"label": "Entities", "value": graph.count_nodes("Entity")},
                {"label": "Broadcasts", "value": graph.count_nodes("Broadcast")},
            ]

            # Get schema info
            schema = {
                "nodes": [],
                "edges": [],
            }
            node_tables = ["Source", "Document", "Claim", "Entity", "Event", "Narrative", "Broadcast", "ContradictionSummary"]
            edge_tables = [
                ("FROM_SOURCE", "Document -> Source"),
                ("EXTRACTED_FROM", "Claim -> Document (confidence, extracted_at)"),
                ("MENTIONS", "Claim -> Entity (first_seen, last_seen, frequency, confidence)"),
                ("ABOUT_EVENT", "Claim -> Event (confidence, first_seen)"),
                ("CONTRADICTS", "Claim -> Claim (type, strength, confidence, detected_at, status)"),
                ("SUPPORTS", "Claim -> Claim (strength, confidence)"),
                ("PART_OF_THREAD", "Claim -> Narrative (confidence)"),
                ("APPEARS_IN", "Entity -> Event (role, confidence)"),
                ("REFERENCES", "Broadcast -> Event (snippet)"),
                ("NEXT_EVENT", "Event -> Event (time_gap_hours)"),
                ("SUBEVENT_OF", "Event -> Event"),
                ("PRECEDES", "Narrative -> Narrative (drift_amount)"),
                ("CALLS_BACK", "Broadcast -> Broadcast (snippet, time_delta)"),
            ]
            for t in node_tables:
                count = graph.count_nodes(t)
                try:
                    sample = graph.execute(f"MATCH (n:{t}) RETURN n.* LIMIT 1")
                    cols = ", ".join(k.split(".")[-1] for k in sample[0].keys()) if sample else "empty"
                except:
                    cols = "error reading"
                schema["nodes"].append({"name": f"{t} ({count})", "columns": cols})
            for name, detail in edge_tables:
                try:
                    count = graph.count_edges(name)
                except:
                    count = "?"
                schema["edges"].append({"name": f"{name} ({count})", "detail": detail})

            # Pipeline check
            pipeline = [
                {"name": "Graph Store (KuzuDB)", "status": "ok", "detail": "Connected"},
                {"name": "Metadata Store (SQLite)", "status": "ok", "detail": f"{metadata_path}"},
                {"name": "Ingestion Pipeline", "status": "ok" if graph.count_nodes("Source") > 0 else "skip", "detail": f"{graph.count_nodes('Source')} sources"},
                {"name": "Claim Extraction", "status": "ok" if graph.count_nodes("Claim") > 0 else "skip", "detail": f"{graph.count_nodes('Claim')} claims"},
                {"name": "Event Clustering", "status": "ok" if graph.count_nodes("Event") > 0 else "skip", "detail": f"{graph.count_nodes('Event')} events"},
                {"name": "Contradiction Detection", "status": "ok" if graph.count_edges("CONTRADICTS") > 0 else "skip", "detail": f"{graph.count_edges('CONTRADICTS')} contradictions"},
                {"name": "Narrative Analysis", "status": "ok" if graph.count_nodes("Narrative") > 0 else "skip", "detail": f"{graph.count_nodes('Narrative')} narratives"},
            ]

            graph.close()
            metadata.conn.close()

            return {"stats": stats, "schema": schema, "pipeline": pipeline}
        except Exception as e:
            return {
                "stats": [{"label": "Error", "value": "!", "class": "error"}],
                "schema": {"nodes": [], "edges": []},
                "pipeline": [{"name": "System", "status": "err", "detail": str(e)}],
            }

    def run_tests(self):
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "--json-report", "--json-report-file=" + str(RESULTS_FILE)],
                capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=120
            )

            # Parse pytest output
            results = []
            passed = failed = errors = 0

            # Try JSON report first
            if RESULTS_FILE.exists():
                try:
                    report = json.loads(RESULTS_FILE.read_text())
                    for test in report.get("tests", []):
                        outcome = test.get("outcome", "unknown")
                        r = {
                            "name": test.get("nodeid", "unknown"),
                            "outcome": outcome,
                            "duration": round(test.get("duration", 0), 3),
                            "longrepr": test.get("longrepr", ""),
                        }
                        results.append(r)
                        if outcome == "passed":
                            passed += 1
                        elif outcome == "failed":
                            failed += 1
                        else:
                            errors += 1
                    return {"results": results, "passed": passed, "failed": failed, "errors": errors}
                except (json.JSONDecodeError, KeyError):
                    pass

            # Fallback: parse stdout
            for line in result.stdout.split("\n"):
                if "PASSED" in line:
                    name = line.split("::")[-1].split(" ")[0].strip() if "::" in line else line.strip()
                    results.append({"name": name, "outcome": "passed", "duration": 0, "longrepr": ""})
                    passed += 1
                elif "FAILED" in line:
                    name = line.split("::")[-1].split(" ")[0].strip() if "::" in line else line.strip()
                    results.append({"name": name, "outcome": "failed", "duration": 0, "longrepr": ""})
                    failed += 1
                elif "ERROR" in line and "test" in line.lower():
                    results.append({"name": line.strip(), "outcome": "error", "duration": 0, "longrepr": ""})
                    errors += 1

            if not results:
                # At minimum show the raw output
                results.append({"name": "Test run output", "outcome": "passed" if result.returncode == 0 else "failed", "duration": 0, "longrepr": result.stdout[-500:] if result.stdout else ""})
                if result.returncode == 0:
                    passed = 1
                else:
                    failed = 1

            return {"results": results, "passed": passed, "failed": failed, "errors": errors}
        except subprocess.TimeoutExpired:
            return {"results": [{"name": "Tests timed out", "outcome": "error", "duration": 120, "longrepr": ""}], "passed": 0, "failed": 0, "errors": 1}
        except Exception as e:
            return {"results": [{"name": f"Run error: {e}", "outcome": "error", "duration": 0, "longrepr": ""}], "passed": 0, "failed": 0, "errors": 1}


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"objective03 Test Dashboard running at http://localhost:{port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
