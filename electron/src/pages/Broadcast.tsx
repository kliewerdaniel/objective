import { useEffect, useState, useRef } from 'react'
import {
  getPipeline,
  getBroadcasts,
  getNowPlaying,
  playBroadcast,
  stopBroadcast,
  startNewBroadcast,
  deleteBroadcast,
  clearBroadcasts,
  renameBroadcast,
  downloadBroadcastUrl,
  subscribeEvents,
  type PipelineState,
  type Broadcast,
} from '@/lib/api'
import {
  Play,
  Pause,
  Square,
  CheckCircle,
  Circle,
  AlertCircle,
  Clock,
  Music,
  Radio,
  Loader2,
  Trash2,
  Download,
  Pencil,
  Check,
  X,
} from 'lucide-react'

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}m ${s}s`
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getDisplayName(filename: string): string {
  const stem = filename.replace('.wav', '')
  const parts = stem.split('_', 2)
  return parts.length > 2 ? parts.slice(2).join('_') : stem
}

export default function BroadcastPage() {
  const [pipeline, setPipeline] = useState<PipelineState | null>(null)
  const [broadcasts, setBroadcasts] = useState<Broadcast[]>([])
  const [nowPlaying, setNowPlaying] = useState<{ is_playing: boolean; now_playing: { path: string; filename: string; duration: number } | null; playback_position: number; playback_duration: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const editInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    getPipeline().then(setPipeline).catch((e) => setError(e.message))
    getBroadcasts().then((r) => setBroadcasts(r.broadcasts)).catch(() => {})
    getNowPlaying().then(setNowPlaying).catch(() => {})

    const unsub = subscribeEvents((event) => {
      if (event.type === 'pipeline_progress') {
        setPipeline(event.data as unknown as PipelineState)
        if ((event.data as any)?.current_stage === 'ready') {
          getBroadcasts().then((r) => setBroadcasts(r.broadcasts)).catch(() => {})
        }
      }
    })
    return unsub
  }, [])

  useEffect(() => {
    const iv = setInterval(() => {
      getNowPlaying().then(setNowPlaying).catch(() => {})
    }, 1000)
    return () => clearInterval(iv)
  }, [])

  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus()
      editInputRef.current.select()
    }
  }, [editingId])

  const handlePlay = async (audioPath: string) => {
    setError(null)
    try {
      await playBroadcast(audioPath)
      getNowPlaying().then(setNowPlaying).catch(() => {})
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Playback failed')
    }
  }

  const handleStop = async () => {
    try {
      await stopBroadcast()
      getNowPlaying().then(setNowPlaying).catch(() => {})
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Stop failed')
    }
  }

  const handleNewBroadcast = async () => {
    setError(null)
    try {
      await startNewBroadcast()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to start broadcast')
    }
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await deleteBroadcast(id)
      setBroadcasts((prev) => prev.filter((b) => b.id !== id))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Delete failed')
    }
  }

  const handleClearAll = async () => {
    if (!confirm('Delete all broadcasts?')) return
    try {
      await clearBroadcasts()
      setBroadcasts([])
      setNowPlaying(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Clear failed')
    }
  }

  const handleRenameStart = (b: Broadcast, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingId(b.id)
    setEditName(getDisplayName(b.filename))
  }

  const handleRenameSave = async (id: string) => {
    if (!editName.trim()) return
    try {
      await renameBroadcast(id, editName.trim())
      setBroadcasts((prev) => prev.map((b) => {
        if (b.id === id) {
          return { ...b, filename: `bcast_${id}_${editName.trim()}.wav` }
        }
        return b
      }))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Rename failed')
    }
    setEditingId(null)
  }

  const handleRenameCancel = () => {
    setEditingId(null)
    setEditName('')
  }

  const isGenerating = pipeline?.generating ?? false
  const progress = pipeline?.stages
    ? ((pipeline.completed_stages.length / pipeline.stages.length) * 100)
    : 0

  return (
    <div className="space-y-4 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h2 className="text-xl font-bold">Broadcast</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Generate and listen to AI news broadcasts
          </p>
        </div>
        <div className="flex items-center gap-2">
          {nowPlaying?.is_playing && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-500/10 border border-green-500/30">
              <div className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
              <span className="text-[10px] text-green-500 font-medium">LIVE</span>
            </div>
          )}
          <button
            onClick={handleNewBroadcast}
            disabled={isGenerating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {isGenerating ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Radio className="h-3.5 w-3.5" />
            )}
            {isGenerating ? 'Generating...' : 'New Broadcast'}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-2.5 text-xs text-destructive-foreground shrink-0">
          {error}
        </div>
      )}

      {pipeline?.generation_error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-2.5 text-xs text-destructive-foreground shrink-0">
          {pipeline.generation_error}
        </div>
      )}

      {/* Now Playing bar */}
      {nowPlaying?.now_playing && (
        <div className="rounded-lg border border-border bg-card p-3 shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => nowPlaying.is_playing ? handleStop() : handlePlay(nowPlaying.now_playing!.path)}
              className="h-9 w-9 rounded-full bg-primary text-primary-foreground flex items-center justify-center hover:bg-primary/90 transition-colors shrink-0"
            >
              {nowPlaying.is_playing ? (
                <Square className="h-3.5 w-3.5" />
              ) : (
                <Play className="h-3.5 w-3.5 ml-0.5" />
              )}
            </button>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">
                {getDisplayName(nowPlaying.now_playing.filename)}
              </p>
              <div className="mt-1.5 flex items-center gap-2">
                <span className="text-[10px] text-muted-foreground w-8 text-right font-mono">
                  {formatTime(nowPlaying.playback_position)}
                </span>
                <div className="flex-1 h-1 rounded-full bg-secondary overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-200"
                    style={{ width: `${nowPlaying.playback_duration > 0 ? (nowPlaying.playback_position / nowPlaying.playback_duration) * 100 : 0}%` }}
                  />
                </div>
                <span className="text-[10px] text-muted-foreground w-8 font-mono">
                  {formatTime(nowPlaying.playback_duration)}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="flex-1 grid grid-cols-3 gap-4 min-h-0">
        {/* Pipeline progress */}
        <div className="col-span-2 flex flex-col gap-3 min-h-0">
          {/* Progress bar */}
          <div className="rounded-lg border border-border bg-card p-3 shrink-0">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold">Pipeline Progress</h3>
              <span className="text-[10px] text-muted-foreground">
                {pipeline?.completed_stages.length ?? 0} / {pipeline?.stages.length ?? 0}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>

            {pipeline?.current_stage === 'tts' && (pipeline.segments_total ?? 0) > 0 && (
              <div className="mt-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-muted-foreground">Synthesizing</span>
                  <span className="text-[10px] font-mono text-primary">
                    {pipeline.segments_done ?? 0}/{pipeline.segments_total ?? 0}
                  </span>
                </div>
                <div className="h-1 rounded-full bg-secondary overflow-hidden">
                  <div
                    className="h-full rounded-full bg-green-500 transition-all duration-300"
                    style={{ width: `${pipeline.segments_total ? ((pipeline.segments_done ?? 0) / pipeline.segments_total) * 100 : 0}%` }}
                  />
                </div>
              </div>
            )}

            {pipeline?.current_stage === 'stitching' && (
              <div className="mt-2 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin text-primary" />
                Stitching audio...
              </div>
            )}
          </div>

          {/* Stage list */}
          <div className="rounded-lg border border-border bg-card p-3 flex-1 min-h-0 overflow-y-auto">
            <div className="space-y-1">
              {pipeline?.stages.map((stage) => {
                const isCompleted = pipeline.completed_stages.includes(stage.id)
                const isCurrent = pipeline.current_stage === stage.id
                const isFailed = pipeline.failed_stage === stage.id
                return (
                  <div
                    key={stage.id}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs transition-colors ${
                      isCurrent
                        ? 'bg-primary/10'
                        : isCompleted
                        ? 'opacity-60'
                        : isFailed
                        ? 'bg-destructive/10'
                        : 'opacity-30'
                    }`}
                  >
                    {isCompleted ? (
                      <CheckCircle className="h-3 w-3 text-green-500 shrink-0" />
                    ) : isFailed ? (
                      <AlertCircle className="h-3 w-3 text-destructive shrink-0" />
                    ) : isCurrent ? (
                      <Loader2 className="h-3 w-3 text-primary animate-spin shrink-0" />
                    ) : (
                      <Circle className="h-3 w-3 text-muted-foreground shrink-0" />
                    )}
                    <span>{stage.label}</span>
                    {isCurrent && (
                      <span className="text-[10px] text-muted-foreground ml-auto">...</span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Broadcast history */}
        <div className="rounded-lg border border-border bg-card flex flex-col min-h-0">
          <div className="p-2.5 border-b border-border shrink-0">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold flex items-center gap-1.5">
                <Music className="h-3 w-3" />
                History
                <span className="text-muted-foreground">({broadcasts.length})</span>
              </h3>
              {broadcasts.length > 0 && (
                <button
                  onClick={handleClearAll}
                  className="text-[10px] text-muted-foreground hover:text-destructive transition-colors flex items-center gap-1"
                >
                  <Trash2 className="h-2.5 w-2.5" />
                  Clear
                </button>
              )}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
            {broadcasts.map((b) => {
              const isActive = nowPlaying?.now_playing?.path === b.path
              const displayName = getDisplayName(b.filename)
              const isEditing = editingId === b.id
              return (
                <div
                  key={b.id}
                  className={`group rounded transition-colors ${
                    isActive
                      ? 'bg-primary/10'
                      : 'hover:bg-accent/50'
                  }`}
                >
                  <div className="flex items-center gap-1.5 px-1.5 py-1.5">
                    <button
                      onClick={() => handlePlay(b.path)}
                      className="flex items-center gap-2 flex-1 min-w-0 text-left"
                    >
                      <div className={`h-7 w-7 rounded flex items-center justify-center shrink-0 ${
                        isActive && nowPlaying?.is_playing
                          ? 'bg-green-500 text-white'
                          : 'bg-secondary text-secondary-foreground'
                      }`}>
                        {isActive && nowPlaying?.is_playing ? (
                          <Pause className="h-3 w-3" />
                        ) : (
                          <Play className="h-3 w-3 ml-0.5" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        {isEditing ? (
                          <div className="flex items-center gap-1">
                            <input
                              ref={editInputRef}
                              value={editName}
                              onChange={(e) => setEditName(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleRenameSave(b.id)
                                if (e.key === 'Escape') handleRenameCancel()
                              }}
                              className="flex-1 bg-background border border-border rounded px-1.5 py-0.5 text-xs min-w-0"
                              onClick={(e) => e.stopPropagation()}
                            />
                            <button
                              onClick={(e) => { e.stopPropagation(); handleRenameSave(b.id) }}
                              className="p-0.5 rounded hover:bg-green-500/20 text-green-500"
                            >
                              <Check className="h-3 w-3" />
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleRenameCancel() }}
                              className="p-0.5 rounded hover:bg-destructive/20 text-destructive"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </div>
                        ) : (
                          <>
                            <p className="text-xs font-medium truncate">{displayName}</p>
                            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mt-0.5">
                              <span>{formatDuration(b.duration)}</span>
                              <span className="opacity-40">|</span>
                              <span>{formatSize(b.size_bytes)}</span>
                            </div>
                          </>
                        )}
                      </div>
                    </button>
                    {!isEditing && (
                      <div className="opacity-0 group-hover:opacity-100 flex items-center gap-0.5 transition-all">
                        <button
                          onClick={(e) => handleRenameStart(b, e)}
                          className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground"
                          title="Rename"
                        >
                          <Pencil className="h-3 w-3" />
                        </button>
                        <a
                          href={downloadBroadcastUrl(b.id)}
                          download
                          onClick={(e) => e.stopPropagation()}
                          className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground"
                          title="Download"
                        >
                          <Download className="h-3 w-3" />
                        </a>
                        <button
                          onClick={(e) => handleDelete(b.id, e)}
                          className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                          title="Delete"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
            {broadcasts.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Clock className="h-6 w-6 mb-2 opacity-40" />
                <p className="text-[10px]">No broadcasts yet</p>
                <p className="text-[10px] mt-0.5 opacity-60">Click "New Broadcast" to generate one</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
