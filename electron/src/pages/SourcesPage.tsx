import { useState, useEffect } from 'react'
import {
  getSources,
  addSource,
  deleteSource,
  toggleSource,
  validateSource,
  type SourceConfig,
} from '@/lib/api'
import {
  Globe,
  Plus,
  Trash2,
  Check,
  X,
  Loader2,
  AlertCircle,
  MessageSquare,
  Youtube,
  RefreshCw,
} from 'lucide-react'

export default function SourcesPage() {
  const [sources, setSources] = useState<{ rss: SourceConfig[]; reddit: SourceConfig[]; youtube: SourceConfig[] }>({ rss: [], reddit: [], youtube: [] })
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [newType, setNewType] = useState<'rss' | 'reddit' | 'youtube'>('rss')
  const [newName, setNewName] = useState('')
  const [newUrl, setNewUrl] = useState('')
  const [newSubreddit, setNewSubreddit] = useState('')
  const [validating, setValidating] = useState(false)
  const [validationResult, setValidationResult] = useState<{ valid: boolean; title?: string; error?: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchSources = async () => {
    try {
      const data = await getSources()
      setSources(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSources()
  }, [])

  const handleValidate = async () => {
    if (!newUrl.trim()) return
    setValidating(true)
    setValidationResult(null)
    try {
      const result = await validateSource(newUrl)
      setValidationResult(result)
      if (result.valid && result.title && !newName) {
        setNewName(result.title)
      }
    } catch {
      setValidationResult({ valid: false, error: 'Validation failed' })
    } finally {
      setValidating(false)
    }
  }

  const handleAdd = async () => {
    if (!newName.trim()) return
    setError(null)
    try {
      await addSource({ type: newType, name: newName, url: newUrl, subreddit: newSubreddit })
      setAdding(false)
      setNewName('')
      setNewUrl('')
      setNewSubreddit('')
      setValidationResult(null)
      await fetchSources()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const handleDelete = async (type: string, name: string) => {
    try {
      await deleteSource(type, name)
      await fetchSources()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const handleToggle = async (type: string, name: string) => {
    try {
      await toggleSource(type, name)
      await fetchSources()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const totalCount = sources.rss.length + sources.reddit.length + sources.youtube.length

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border shrink-0">
        <div>
          <h2 className="text-xl font-bold">Sources</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {totalCount} source{totalCount !== 1 ? 's' : ''} configured
          </p>
        </div>
        <button
          onClick={() => setAdding(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          Add Source
        </button>
      </div>

      {error && (
        <div className="mx-6 mt-4 rounded-lg border border-destructive/50 bg-destructive/10 p-2.5 text-xs text-destructive-foreground">
          {error}
        </div>
      )}

      {/* Add source form */}
      {adding && (
        <div className="mx-6 mt-4 rounded-lg border border-border bg-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Add Source</h3>
            <button onClick={() => setAdding(false)} className="text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="flex gap-2">
            {(['rss', 'reddit', 'youtube'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setNewType(t)}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                  newType === t
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                }`}
              >
                {t.toUpperCase()}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Source name"
              className="text-xs bg-secondary border border-border rounded px-3 py-2 placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary"
            />
            {newType === 'rss' ? (
              <div className="flex gap-2">
                <input
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  placeholder="https://example.com/feed.xml"
                  className="flex-1 text-xs bg-secondary border border-border rounded px-3 py-2 placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <button
                  onClick={handleValidate}
                  disabled={validating || !newUrl.trim()}
                  className="px-3 py-2 rounded bg-secondary hover:bg-secondary/80 disabled:opacity-50 transition-colors"
                >
                  {validating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                </button>
              </div>
            ) : newType === 'reddit' ? (
              <input
                value={newSubreddit}
                onChange={(e) => setNewSubreddit(e.target.value)}
                placeholder="subreddit name"
                className="text-xs bg-secondary border border-border rounded px-3 py-2 placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary"
              />
            ) : (
              <input
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                placeholder="Channel URL or handle"
                className="text-xs bg-secondary border border-border rounded px-3 py-2 placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary"
              />
            )}
          </div>

          {validationResult && (
            <div className={`text-xs p-2 rounded ${validationResult.valid ? 'bg-green-500/10 text-green-500' : 'bg-destructive/10 text-destructive-foreground'}`}>
              {validationResult.valid ? (
                <div className="flex items-center gap-1.5">
                  <Check className="h-3 w-3" />
                  Valid feed: {validationResult.title}
                </div>
              ) : (
                <div className="flex items-center gap-1.5">
                  <AlertCircle className="h-3 w-3" />
                  {validationResult.error}
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button
              onClick={() => setAdding(false)}
              className="px-3 py-1.5 text-xs rounded border border-border hover:bg-accent transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleAdd}
              disabled={!newName.trim()}
              className="px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              Add Source
            </button>
          </div>
        </div>
      )}

      {/* Source list */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 text-muted-foreground animate-spin" />
          </div>
        ) : (
          <>
            {/* RSS */}
            {sources.rss.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Globe className="h-3 w-3" />
                  RSS Feeds ({sources.rss.length})
                </h3>
                <div className="space-y-1">
                  {sources.rss.map((s) => (
                    <SourceRow key={s.name} source={s} type="rss" onDelete={handleDelete} onToggle={handleToggle} />
                  ))}
                </div>
              </div>
            )}

            {/* Reddit */}
            {sources.reddit.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <MessageSquare className="h-3 w-3" />
                  Reddit ({sources.reddit.length})
                </h3>
                <div className="space-y-1">
                  {sources.reddit.map((s) => (
                    <SourceRow key={s.name} source={s} type="reddit" onDelete={handleDelete} onToggle={handleToggle} />
                  ))}
                </div>
              </div>
            )}

            {/* YouTube */}
            {sources.youtube.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Youtube className="h-3 w-3" />
                  YouTube ({sources.youtube.length})
                </h3>
                <div className="space-y-1">
                  {sources.youtube.map((s) => (
                    <SourceRow key={s.name} source={s} type="youtube" onDelete={handleDelete} onToggle={handleToggle} />
                  ))}
                </div>
              </div>
            )}

            {totalCount === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Globe className="h-8 w-8 mb-3 opacity-40" />
                <p className="text-sm">No sources configured</p>
                <p className="text-xs mt-1">Click "Add Source" to get started</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function SourceRow({
  source,
  type,
  onDelete,
  onToggle,
}: {
  source: SourceConfig
  type: string
  onDelete: (type: string, name: string) => void
  onToggle: (type: string, name: string) => void
}) {
  const enabled = source.enabled !== false
  return (
    <div className={`flex items-center gap-3 px-3 py-2 rounded-lg border transition-colors ${
      enabled ? 'border-border bg-card' : 'border-border/50 bg-card/50 opacity-60'
    }`}>
      <button
        onClick={() => onToggle(type, source.name)}
        className={`h-4 w-4 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors ${
          enabled ? 'bg-green-500 border-green-500' : 'border-muted-foreground/30'
        }`}
      >
        {enabled && <Check className="h-2.5 w-2.5 text-white" />}
      </button>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium">{source.name}</p>
        <p className="text-[10px] text-muted-foreground truncate font-mono">
          {source.url || source.subreddit || '—'}
        </p>
      </div>
      <div className="text-[10px] text-muted-foreground shrink-0">
        every {Math.round((source.interval || 600) / 60)}m
      </div>
      <button
        onClick={() => onDelete(type, source.name)}
        className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
      >
        <Trash2 className="h-3 w-3" />
      </button>
    </div>
  )
}
