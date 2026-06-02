import { useState, useEffect } from 'react'
import { Download, Check, AlertCircle, Loader2, FolderOpen, ArrowRight } from 'lucide-react'
import catalogData from '../data/model-catalog.json'
import type { ModelTier, DownloadState } from './types'

interface DownloadStep {
  selectedTier: string
  modelsPath: string
  onNext: () => void
  onBack: () => void
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(0)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function formatSpeed(bytesPerSec: number): string {
  if (bytesPerSec < 1024 * 1024) return `${(bytesPerSec / 1024).toFixed(0)} KB/s`
  return `${(bytesPerSec / (1024 * 1024)).toFixed(1)} MB/s`
}

function formatTimeRemaining(bytesRemaining: number, bytesPerSec: number): string {
  if (bytesPerSec === 0) return '...'
  const seconds = bytesRemaining / bytesPerSec
  if (seconds < 60) return `${Math.ceil(seconds)}s`
  const minutes = Math.floor(seconds / 60)
  const secs = Math.ceil(seconds % 60)
  return `${minutes}m ${secs}s`
}

export default function DownloadStep({ selectedTier, modelsPath, onNext, onBack }: DownloadStep) {
  const tier = (catalogData.tiers as ModelTier[]).find((t) => t.id === selectedTier)
  const [mode, setMode] = useState<'choose' | 'download' | 'existing'>('choose')
  const [downloads, setDownloads] = useState<DownloadState[]>(
    (tier?.models || []).map((m) => ({
      filename: m.filename,
      name: m.name,
      status: 'queued',
      progress: 0,
      size_bytes: m.size_bytes,
      downloaded_bytes: 0,
      speed: 0,
    }))
  )
  const [allDone, setAllDone] = useState(false)
  const [graphInit, setGraphInit] = useState(false)
  const [metadataInit, setMetadataInit] = useState(false)
  const [vectorInit, setVectorInit] = useState(false)

  // Simulate initialization steps
  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = []
    timers.push(setTimeout(() => setGraphInit(true), 1500))
    timers.push(setTimeout(() => setMetadataInit(true), 2500))
    timers.push(setTimeout(() => setVectorInit(true), 3500))
    return () => timers.forEach(clearTimeout)
  }, [])

  // Simulate download progress
  useEffect(() => {
    if (allDone || mode !== 'download') return

    const interval = setInterval(() => {
      setDownloads((prev) => {
        let allFinished = true
        const next = prev.map((d) => {
          if (d.status === 'done' || d.status === 'error') return d
          if (d.status === 'queued') {
            const idx = prev.indexOf(d)
            if (idx === 0 || prev[idx - 1].status === 'done') {
              allFinished = false
              return { ...d, status: 'downloading' as const }
            }
            allFinished = false
            return d
          }
          const newDownloaded = Math.min(
            d.downloaded_bytes + d.size_bytes * 0.02,
            d.size_bytes
          )
          const progress = (newDownloaded / d.size_bytes) * 100
          const speed = d.size_bytes * 0.02 * 2
          if (newDownloaded >= d.size_bytes) {
            return {
              ...d,
              status: 'done' as const,
              progress: 100,
              downloaded_bytes: d.size_bytes,
              speed: 0,
            }
          }
          allFinished = false
          return {
            ...d,
            downloaded_bytes: newDownloaded,
            progress,
            speed,
          }
        })
        if (allFinished) setAllDone(true)
        return next
      })
    }, 500)

    return () => clearInterval(interval)
  }, [allDone, mode])

  // If user chose to use existing models
  if (mode === 'existing') {
    return (
      <div className="flex flex-col h-full px-8 py-6">
        <div className="mb-6">
          <h2 className="text-2xl font-bold">Models Ready</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Using existing models from your specified directory.
          </p>
        </div>

        <div className="flex-1 flex flex-col items-center justify-center text-center">
          <FolderOpen className="h-16 w-16 text-primary mb-4" />
          <h3 className="text-lg font-semibold mb-1">Models found</h3>
          <code className="text-xs bg-secondary px-3 py-1.5 rounded font-mono mb-4 max-w-full truncate">
            {modelsPath}
          </code>
          <p className="text-xs text-muted-foreground max-w-md">
            You can configure individual model assignments from the sidebar after setup.
          </p>
        </div>

        <div className="flex justify-between pt-4 border-t border-border">
          <button onClick={() => setMode('choose')} className="px-4 py-2 text-sm rounded-lg border border-border hover:bg-accent transition-colors">
            Back
          </button>
          <button onClick={onNext} className="px-6 py-2 text-sm rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors flex items-center gap-2">
            Continue <ArrowRight className="h-3 w-3" />
          </button>
        </div>
      </div>
    )
  }

  // Mode selection screen
  if (mode === 'choose') {
    return (
      <div className="flex flex-col h-full px-8 py-6">
        <div className="mb-6">
          <h2 className="text-2xl font-bold">Models</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Choose how to provide the required model files ({tier?.name || selectedTier} tier).
          </p>
        </div>

        <div className="flex-1 flex flex-col items-center justify-center gap-4 max-w-md mx-auto w-full">
          <button
            onClick={() => setMode('download')}
            className="w-full text-left rounded-lg border border-border bg-card p-6 hover:border-primary/50 hover:bg-accent/30 transition-all"
          >
            <Download className="h-8 w-8 text-primary mb-3" />
            <h3 className="text-sm font-semibold mb-1">Download Models</h3>
            <p className="text-xs text-muted-foreground">
              Download models from Hugging Face Hub (~{tier?.total_size_gb.toFixed(1) || '?'} GB).
            </p>
          </button>

          <button
            onClick={() => setMode('existing')}
            className="w-full text-left rounded-lg border border-border bg-card p-6 hover:border-primary/50 hover:bg-accent/30 transition-all"
          >
            <FolderOpen className="h-8 w-8 text-primary mb-3" />
            <h3 className="text-sm font-semibold mb-1">Use Existing Models</h3>
            <p className="text-xs text-muted-foreground">
              Point to a directory that already contains model files at{' '}
              <code className="text-[10px] bg-secondary px-1 rounded">{modelsPath}</code>.
            </p>
          </button>
        </div>

        <div className="flex justify-between pt-4 border-t border-border">
          <button onClick={onBack} className="px-4 py-2 text-sm rounded-lg border border-border hover:bg-accent transition-colors">
            Back
          </button>
        </div>
      </div>
    )
  }

  // Download mode
  const totalSize = downloads.reduce((sum, d) => sum + d.size_bytes, 0)
  const totalDownloaded = downloads.reduce((sum, d) => sum + d.downloaded_bytes, 0)
  const totalProgress = totalSize > 0 ? (totalDownloaded / totalSize) * 100 : 0

  return (
    <div className="flex flex-col h-full px-8 py-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold">Downloading Models</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Downloading to {modelsPath}
        </p>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto">
        <div className="rounded-lg border border-border bg-card p-4 space-y-2">
          <h3 className="text-xs font-semibold mb-2">Initializing</h3>
          {[
            { label: 'Graph database', done: graphInit },
            { label: 'Metadata store', done: metadataInit },
            { label: 'Vector index', done: vectorInit },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-2 text-xs">
              {item.done ? (
                <Check className="h-3 w-3 text-green-500" />
              ) : (
                <Loader2 className="h-3 w-3 text-primary animate-spin" />
              )}
              <span className={item.done ? 'text-muted-foreground' : ''}>{item.label}</span>
              {item.done && <span className="text-[10px] text-green-500 ml-auto">Done</span>}
            </div>
          ))}
        </div>

        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-semibold">Overall Progress</h3>
            <span className="text-[10px] text-muted-foreground font-mono">
              {formatBytes(totalDownloaded)} / {formatBytes(totalSize)}
            </span>
          </div>
          <div className="h-2 rounded-full bg-secondary overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all duration-300"
              style={{ width: `${totalProgress}%` }}
            />
          </div>
        </div>

        <div className="space-y-2">
          {downloads.map((d) => (
            <div key={d.filename} className="rounded-lg border border-border bg-card p-3">
              <div className="flex items-center gap-2 mb-1.5">
                {d.status === 'done' ? (
                  <Check className="h-3 w-3 text-green-500 shrink-0" />
                ) : d.status === 'error' ? (
                  <AlertCircle className="h-3 w-3 text-destructive shrink-0" />
                ) : d.status === 'downloading' ? (
                  <Download className="h-3 w-3 text-primary shrink-0" />
                ) : (
                  <div className="h-3 w-3 rounded-full border border-muted-foreground/30 shrink-0" />
                )}
                <span className="text-xs font-medium flex-1 truncate">{d.name}</span>
                <span className="text-[10px] text-muted-foreground font-mono shrink-0">
                  {d.status === 'done' ? 'Done' : d.status === 'downloading' ? `${d.progress.toFixed(0)}%` : d.status === 'error' ? 'Failed' : 'Queued'}
                </span>
              </div>
              {d.status === 'downloading' && (
                <div className="space-y-1">
                  <div className="h-1 rounded-full bg-secondary overflow-hidden">
                    <div className="h-full rounded-full bg-primary transition-all duration-200" style={{ width: `${d.progress}%` }} />
                  </div>
                  <div className="flex justify-between text-[10px] text-muted-foreground">
                    <span>{formatBytes(d.downloaded_bytes)} / {formatBytes(d.size_bytes)}</span>
                    <span>{formatSpeed(d.speed)} — {formatTimeRemaining(d.size_bytes - d.downloaded_bytes, d.speed)} remaining</span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="flex justify-between pt-4 border-t border-border">
        <button onClick={() => setMode('choose')} disabled={downloads.some((d) => d.status === 'downloading')} className="px-4 py-2 text-sm rounded-lg border border-border hover:bg-accent disabled:opacity-50 transition-colors">
          Back
        </button>
        <button onClick={onNext} disabled={!allDone} className="px-6 py-2 text-sm rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors">
          {allDone ? 'Continue' : 'Downloading...'}
        </button>
      </div>
    </div>
  )
}
