import { useState } from 'react'
import { Check, Globe, Plus, Trash2, MessageSquare } from 'lucide-react'
import sourcesData from '../data/default-sources.json'
import type { SourceCategory } from './types'

interface SourcesStep {
  selectedSources: Set<string>
  customRssUrls: string[]
  onNext: (sources: Set<string>, customUrls: string[]) => void
  onBack: () => void
}

export default function SourcesStep({
  selectedSources,
  customRssUrls,
  onNext,
  onBack,
}: SourcesStep) {
  const [sources, setSources] = useState<Set<string>>(selectedSources)
  const [customUrls, setCustomUrls] = useState<string[]>(customRssUrls)
  const [newUrl, setNewUrl] = useState('')
  const categories = sourcesData.categories as SourceCategory[]

  const toggleSource = (url: string) => {
    setSources((prev) => {
      const next = new Set(prev)
      if (next.has(url)) {
        next.delete(url)
      } else {
        next.add(url)
      }
      return next
    })
  }

  const addCustomUrl = () => {
    const url = newUrl.trim()
    if (url && !customUrls.includes(url)) {
      setCustomUrls((prev) => [...prev, url])
      setSources((prev) => new Set([...prev, url]))
      setNewUrl('')
    }
  }

  const removeCustomUrl = (url: string) => {
    setCustomUrls((prev) => prev.filter((u) => u !== url))
    setSources((prev) => {
      const next = new Set(prev)
      next.delete(url)
      return next
    })
  }

  return (
    <div className="flex flex-col h-full px-8 py-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold">News Sources</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Select which sources to monitor. At least one is required.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4">
        {categories.map((cat) => (
          <div key={cat.name}>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              {cat.name}
            </h3>
            <div className="space-y-1">
              {cat.sources.map((src) => {
                const isActive = sources.has(src.url)
                return (
                  <button
                    key={src.url}
                    onClick={() => toggleSource(src.url)}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded text-left transition-colors ${
                      isActive
                        ? 'bg-primary/10 text-foreground'
                        : 'hover:bg-accent/50 text-muted-foreground'
                    }`}
                  >
                    <div className={`h-4 w-4 rounded border flex items-center justify-center shrink-0 ${
                      isActive ? 'bg-primary border-primary' : 'border-muted-foreground/30'
                    }`}>
                      {isActive && <Check className="h-3 w-3 text-primary-foreground" />}
                    </div>
                    {src.type === 'reddit' ? (
                      <MessageSquare className="h-3 w-3 shrink-0" />
                    ) : (
                      <Globe className="h-3 w-3 shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <span className="text-xs font-medium">{src.name}</span>
                      {src.subreddit && (
                        <span className="text-[10px] text-muted-foreground ml-1">r/{src.subreddit}</span>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        ))}

        {/* Custom RSS URLs */}
        <div>
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Custom Sources
          </h3>
          <div className="flex gap-2">
            <input
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addCustomUrl()}
              placeholder="https://example.com/feed.xml"
              className="flex-1 text-xs bg-secondary border border-border rounded px-3 py-2 placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <button
              onClick={addCustomUrl}
              disabled={!newUrl.trim()}
              className="px-3 py-2 rounded bg-secondary hover:bg-secondary/80 disabled:opacity-50 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          </div>
          {customUrls.length > 0 && (
            <div className="mt-2 space-y-1">
              {customUrls.map((url) => (
                <div key={url} className="flex items-center gap-2 text-xs">
                  <Globe className="h-3 w-3 text-muted-foreground shrink-0" />
                  <span className="flex-1 truncate font-mono text-[10px]">{url}</span>
                  <button
                    onClick={() => removeCustomUrl(url)}
                    className="p-0.5 hover:text-destructive transition-colors"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Reddit OAuth (optional) */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-2">Reddit API (Optional)</h3>
          <p className="text-[10px] text-muted-foreground mb-3">
            To enable Reddit sources, create a Reddit API app at{' '}
            <span className="text-primary">reddit.com/prefs/apps</span>
          </p>
          <div className="grid grid-cols-2 gap-3">
            <input
              placeholder="Client ID"
              className="text-xs bg-secondary border border-border rounded px-3 py-2 placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <input
              placeholder="Client Secret"
              type="password"
              className="text-xs bg-secondary border border-border rounded px-3 py-2 placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        </div>

        {/* Selected count */}
        <div className="text-xs text-muted-foreground text-center py-2">
          {sources.size} source{sources.size !== 1 ? 's' : ''} selected
        </div>
      </div>

      {/* Navigation */}
      <div className="flex justify-between pt-4 border-t border-border">
        <button
          onClick={onBack}
          className="px-4 py-2 text-sm rounded-lg border border-border hover:bg-accent transition-colors"
        >
          Back
        </button>
        <button
          onClick={() => onNext(sources, customUrls)}
          disabled={sources.size === 0}
          className="px-6 py-2 text-sm rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  )
}
