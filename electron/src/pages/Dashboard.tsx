import { useEffect, useState } from 'react'
import { getStatus, getDaemonStatus, getAssignedModels, subscribeEvents } from '@/lib/api'
import { Activity, Clock, Zap } from 'lucide-react'

interface Status {
  system_name: string
  config_path: string
  prompts_dir: string
  voices_dir: string
  models_dir: string
}

interface DaemonStatus {
  daemon_running: boolean
  pid: string | null
  uptime: string | null
  launchd_managed: boolean
  scheduler_intervals: Record<string, number>
}

interface LogEntry {
  timestamp: string
  type: string
  data: Record<string, unknown>
}

function formatInterval(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  return `${Math.floor(seconds / 3600)}h`
}

export default function Dashboard() {
  const [status, setStatus] = useState<Status | null>(null)
  const [daemon, setDaemon] = useState<DaemonStatus | null>(null)
  const [assignedModels, setAssignedModels] = useState<Record<string, { path: string; name: string }>>({})
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getStatus().then(setStatus).catch((e) => setError(e.message))
    getDaemonStatus().then(setDaemon).catch(() => {})
    getAssignedModels().then((r) => setAssignedModels(r.assigned)).catch(() => {})

    const iv = setInterval(() => {
      getDaemonStatus().then(setDaemon).catch(() => {})
    }, 10000)

    const unsub = subscribeEvents((event) => {
      setLogs((prev) => [{ timestamp: event.timestamp, type: event.type, data: event.data }, ...prev].slice(0, 30))
    })

    return () => { clearInterval(iv); unsub() }
  }, [])

  if (error) {
    return (
      <div className="space-y-3">
        <h2 className="text-xl font-bold">Dashboard</h2>
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-xs text-destructive-foreground">
          Cannot connect to backend: {error}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Dashboard</h2>

      {/* Status row */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-border bg-card p-3">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="h-3.5 w-3.5 text-muted-foreground" />
            <h3 className="text-xs font-semibold">Daemon</h3>
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div className={`h-2 w-2 rounded-full ${daemon?.daemon_running ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-sm">{daemon?.daemon_running ? 'Running' : 'Stopped'}</span>
            </div>
            {daemon?.pid && (
              <p className="text-xs text-muted-foreground">
                PID <span className="font-mono">{daemon.pid}</span>
              </p>
            )}
            {daemon?.uptime && (
              <p className="text-xs text-muted-foreground">
                Uptime <span>{daemon.uptime}</span>
              </p>
            )}
            {daemon?.launchd_managed && (
              <div className="flex items-center gap-1 text-xs text-green-500">
                <Zap className="h-3 w-3" />
                launchd
              </div>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-3">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="h-3.5 w-3.5 text-muted-foreground" />
            <h3 className="text-xs font-semibold">Scheduler</h3>
          </div>
          <div className="space-y-1">
            {daemon?.scheduler_intervals && Object.entries(daemon.scheduler_intervals).map(([task, interval]) => (
              <div key={task} className="flex justify-between text-xs">
                <span className="text-muted-foreground">{task}</span>
                <span className="font-mono">{formatInterval(interval)}</span>
              </div>
            ))}
            {(!daemon?.scheduler_intervals || Object.keys(daemon.scheduler_intervals).length === 0) && (
              <p className="text-xs text-muted-foreground">Loading...</p>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-3">
          <h3 className="text-xs font-semibold mb-2">System</h3>
          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Name</span>
              <span>{status?.system_name ?? '...'}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Config</span>
              <span className="truncate ml-2 max-w-[120px] text-right font-mono text-[10px]">{status?.config_path ?? '...'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Assigned Models */}
      <div className="rounded-lg border border-border bg-card p-3">
        <h3 className="text-xs font-semibold mb-2">Assigned Models</h3>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {Object.entries(assignedModels).map(([task, cfg]) => (
            <div key={task} className="flex justify-between text-xs">
              <span className="text-muted-foreground">{task}</span>
              <span className="truncate ml-2">{cfg.name || cfg.path.split('/').pop()}</span>
            </div>
          ))}
          {Object.keys(assignedModels).length === 0 && (
            <p className="text-xs text-muted-foreground">Loading...</p>
          )}
        </div>
      </div>

      {/* Event Log */}
      <div className="rounded-lg border border-border bg-card p-3">
        <h3 className="text-xs font-semibold mb-2">Event Log</h3>
        <div className="space-y-0.5 max-h-48 overflow-y-auto">
          {logs.length === 0 && (
            <p className="text-xs text-muted-foreground">Waiting for events...</p>
          )}
          {logs.map((log, i) => (
            <div key={i} className="flex gap-2 text-[10px] font-mono">
              <span className="text-muted-foreground shrink-0">{new Date(log.timestamp).toLocaleTimeString()}</span>
              <span className="text-primary truncate">{log.type}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
