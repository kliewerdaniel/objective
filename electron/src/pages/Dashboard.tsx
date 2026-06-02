import { useEffect, useState } from 'react'
import {
  getDashboardStats,
  getDashboardEvents,
  getDaemonStatus,
  subscribeEvents,
  type DashboardStats,
  type DashboardEvent,
} from '@/lib/api'
import {
  Activity,
  ChevronDown,
  ChevronRight,
  Radio,
} from 'lucide-react'

interface LogEntry {
  timestamp: string
  type: string
  data: Record<string, unknown>
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [events, setEvents] = useState<DashboardEvent[]>([])
  const [daemonRunning, setDaemonRunning] = useState(false)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [streamOpen, setStreamOpen] = useState(true)
  const [selectedEvent, setSelectedEvent] = useState<DashboardEvent | null>(null)

  useEffect(() => {
    let mounted = true

    const fetchAll = async () => {
      try {
        const [s, e, d] = await Promise.all([
          getDashboardStats().catch(() => null),
          getDashboardEvents(20).catch(() => ({ events: [] })),
          getDaemonStatus().catch(() => ({ daemon_running: false })),
        ])
        if (mounted) {
          if (s) setStats(s)
          setEvents(e.events)
          setDaemonRunning(d.daemon_running)
        }
      } catch {}
    }

    fetchAll()
    const iv = setInterval(fetchAll, 15000)

    const unsub = subscribeEvents((event) => {
      setLogs((prev) => [{ timestamp: event.timestamp, type: event.type, data: event.data }, ...prev].slice(0, 50))
    })

    return () => { mounted = false; clearInterval(iv); unsub() }
  }, [])

  const systemStatus = daemonRunning ? 'running' : 'idle'
  const statusColor = systemStatus === 'running' ? 'bg-green-500' : 'bg-muted-foreground/40'
  const statusLabel = systemStatus === 'running' ? 'RUNNING' : 'IDLE'

  return (
    <div className="h-full flex flex-col bg-[#0d0d0d]">
      {/* Row 1: Health Bar */}
      <div className="h-14 shrink-0 flex items-center justify-between px-6 border-b border-[#1e1e1e] bg-[#141414]">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full ${statusColor}`} />
            <span className="text-xs font-semibold tracking-wide">{statusLabel}</span>
          </div>
          {daemonRunning && (
            <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-500/10 border border-green-500/20">
              <div className="h-1 w-1 rounded-full bg-green-500 animate-pulse" />
              <span className="text-[10px] text-green-500">LIVE</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-6 text-xs text-muted-foreground">
          <span>
            <span className="font-mono text-foreground">{stats?.events ?? 0}</span> events
          </span>
          <span>
            <span className="font-mono text-foreground">{stats?.claims ?? 0}</span> claims
          </span>
          <span>
            <span className="font-mono text-foreground">{stats?.contradictions ?? 0}</span> contradictions
          </span>
          <span>
            <span className="font-mono text-foreground">{stats?.narratives ?? 0}</span> narratives
          </span>
        </div>
      </div>

      {/* Row 2: Primary Content */}
      <div className="flex-1 flex min-h-0">
        {/* Left: Event Feed */}
        <div className="flex-1 flex flex-col border-r border-[#1e1e1e] min-w-0">
          <div className="px-4 py-3 border-b border-[#1e1e1e] shrink-0">
            <h3 className="text-xs font-semibold flex items-center gap-1.5">
              <Radio className="h-3 w-3 text-primary" />
              Events Detected
              <span className="text-muted-foreground font-normal">({events.length})</span>
            </h3>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {events.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Activity className="h-6 w-6 mb-2 opacity-40" />
                <p className="text-[10px]">No events detected yet</p>
                <p className="text-[10px] mt-0.5 opacity-60">Events appear after ingestion begins</p>
              </div>
            ) : (
              events.map((ev) => {
                const isSelected = selectedEvent?.id === ev.id
                const confidenceColor = ev.importance > 0.7 ? 'bg-green-500' : ev.contradiction_count > 0 ? 'bg-amber-500' : 'bg-muted-foreground/30'
                return (
                  <div key={ev.id}>
                    <button
                      onClick={() => setSelectedEvent(isSelected ? null : ev)}
                      className={`w-full text-left rounded-lg p-3 transition-colors ${
                        isSelected
                          ? 'bg-primary/10 border border-primary/30'
                          : 'hover:bg-accent/50 border border-transparent'
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <div className={`h-2 w-2 rounded-full mt-1.5 shrink-0 ${confidenceColor}`} />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium truncate">{ev.title || 'Untitled Event'}</p>
                          <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
                            <span>{ev.claim_count} claims</span>
                            {ev.contradiction_count > 0 && (
                              <span className="text-amber-500">{ev.contradiction_count} contradicts</span>
                            )}
                            <span>·</span>
                            <span>{Math.round(ev.importance * 100)}% confidence</span>
                          </div>
                        </div>
                        {isSelected ? (
                          <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0 mt-1" />
                        ) : (
                          <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0 mt-1" />
                        )}
                      </div>
                    </button>
                    {isSelected && (
                      <div className="mx-4 mb-2 p-3 rounded-lg bg-secondary/50 text-xs space-y-2">
                        {ev.description && (
                          <p className="text-muted-foreground">{ev.description}</p>
                        )}
                        <div className="grid grid-cols-2 gap-2 text-[10px]">
                          <div>
                            <span className="text-muted-foreground">Status: </span>
                            <span className="capitalize">{ev.status}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Importance: </span>
                            <span>{Math.round(ev.importance * 100)}%</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Right: Epistemic State */}
        <div className="w-72 flex flex-col shrink-0 overflow-y-auto">
          <div className="px-4 py-3 border-b border-border shrink-0">
            <h3 className="text-xs font-semibold">Epistemic State</h3>
          </div>
          <div className="p-4 space-y-5">
            {/* Contradiction Density */}
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Contradiction Density</p>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden">
                  <div
                    className="h-full rounded-full bg-amber-500 transition-all"
                    style={{ width: `${stats ? Math.min((stats.contradictions / Math.max(stats.claims, 1)) * 100, 100) : 0}%` }}
                  />
                </div>
                <span className="text-[10px] font-mono text-muted-foreground w-8 text-right">
                  {stats ? Math.round((stats.contradictions / Math.max(stats.claims, 1)) * 100) : 0}%
                </span>
              </div>
              <p className="text-[10px] text-muted-foreground/60 mt-1">
                of claims contested
              </p>
            </div>

            {/* Source Reliability */}
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Source Reliability</p>
              <div className="space-y-2">
                {stats?.source_reliability && Object.entries(stats.source_reliability).length > 0 ? (
                  Object.entries(stats.source_reliability)
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 6)
                    .map(([name, score]) => (
                      <div key={name}>
                        <div className="flex justify-between text-[10px] mb-0.5">
                          <span className="truncate">{name}</span>
                          <span className="font-mono text-muted-foreground">{score.toFixed(2)}</span>
                        </div>
                        <div className="h-1 rounded-full bg-secondary overflow-hidden">
                          <div
                            className="h-full rounded-full bg-primary/60 transition-all"
                            style={{ width: `${score * 100}%` }}
                          />
                        </div>
                      </div>
                    ))
                ) : (
                  <p className="text-[10px] text-muted-foreground/60">No data yet</p>
                )}
              </div>
            </div>

            {/* Active Claims */}
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Active Claims</p>
              <div className="flex items-baseline gap-1">
                <span className="text-2xl font-bold font-mono">{stats?.claims ?? 0}</span>
              </div>
              <p className="text-[10px] text-muted-foreground/60">
                {stats?.documents ?? 0} documents ingested
              </p>
            </div>

            {/* Documents */}
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Documents</p>
              <div className="grid grid-cols-2 gap-3">
                <div className="text-center p-2 rounded bg-secondary/50">
                  <p className="text-lg font-bold font-mono">{stats?.documents ?? 0}</p>
                  <p className="text-[10px] text-muted-foreground">Total</p>
                </div>
                <div className="text-center p-2 rounded bg-secondary/50">
                  <p className="text-lg font-bold font-mono">{stats?.sources ?? 0}</p>
                  <p className="text-[10px] text-muted-foreground">Sources</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Row 3: Activity Stream */}
      <div className="shrink-0 border-t border-border">
        <button
          onClick={() => setStreamOpen(!streamOpen)}
          className="w-full flex items-center gap-2 px-4 py-2 text-xs font-semibold text-muted-foreground hover:bg-accent/30 transition-colors"
        >
          {streamOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          Activity Stream
          <span className="text-muted-foreground/60 font-normal">({logs.length})</span>
        </button>
        {streamOpen && (
          <div className="h-32 overflow-y-auto px-4 pb-2 space-y-0.5">
            {logs.length === 0 ? (
              <p className="text-[10px] text-muted-foreground/60 py-2">Waiting for events...</p>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="flex gap-2 text-[10px] font-mono py-0.5">
                  <span className="text-muted-foreground shrink-0 w-16">{new Date(log.timestamp).toLocaleTimeString()}</span>
                  <span className={`truncate ${
                    log.type.includes('error') ? 'text-destructive' : log.type.includes('pipeline') ? 'text-primary' : 'text-muted-foreground'
                  }`}>
                    {log.type}
                  </span>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}
