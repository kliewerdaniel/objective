import { useState } from 'react'
import { Download, Check, Star, Cpu } from 'lucide-react'
import catalogData from '../data/model-catalog.json'
import type { ModelTier } from './types'

interface ModelsStep {
  selectedTier: string | null
  onNext: (tierId: string) => void
  onBack: () => void
}

function getRecommendedTier(): string {
  // Detect available RAM (rough heuristic from navigator)
  const ram_gb = (performance as any).deviceMemory || 16
  if (ram_gb <= 8) return 'minimal'
  if (ram_gb <= 16) return 'balanced'
  return 'full'
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(0)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

export default function ModelsStep({ selectedTier, onNext, onBack }: ModelsStep) {
  const [tier, setTier] = useState<string | null>(selectedTier)
  const recommended = getRecommendedTier()
  const tiers = catalogData.tiers as ModelTier[]

  return (
    <div className="flex flex-col h-full px-8 py-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold">Model Selection</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Choose how many models to download. More models = better quality.
        </p>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto">
        {tiers.map((t) => {
          const isSelected = tier === t.id
          const isRecommended = t.id === recommended
          return (
            <button
              key={t.id}
              onClick={() => setTier(t.id)}
              className={`w-full text-left rounded-lg border p-4 transition-all ${
                isSelected
                  ? 'border-primary bg-primary/5 ring-1 ring-primary'
                  : 'border-border bg-card hover:border-border/80 hover:bg-accent/30'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold">{t.name}</h3>
                    {isRecommended && (
                      <span className="px-2 py-0.5 text-[10px] rounded-full bg-primary/10 text-primary font-medium">
                        Recommended for your Mac
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{t.description}</p>
                </div>
                <div className={`h-5 w-5 rounded-full border-2 flex items-center justify-center shrink-0 ml-3 ${
                  isSelected ? 'border-primary bg-primary' : 'border-muted-foreground/30'
                }`}>
                  {isSelected && <Check className="h-3 w-3 text-primary-foreground" />}
                </div>
              </div>

              <div className="flex items-center gap-4 mt-3 text-[10px] text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Download className="h-3 w-3" />
                  {t.total_size_gb.toFixed(1)} GB download
                </span>
                <span className="flex items-center gap-1">
                  <Cpu className="h-3 w-3" />
                  {t.min_ram_gb} GB RAM min
                </span>
                <span className="flex items-center gap-1">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Star
                      key={i}
                      className={`h-3 w-3 ${i < t.quality_stars ? 'fill-primary text-primary' : 'text-muted-foreground/30'}`}
                    />
                  ))}
                </span>
                <span>~{t.estimated_broadcast_minutes}min broadcasts</span>
              </div>

              {/* Model list */}
              <div className="mt-3 pt-3 border-t border-border/50">
                <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                  {t.models.map((m, i) => (
                    <div key={i} className="flex justify-between text-[10px]">
                      <span className="text-muted-foreground">
                        {m.slot.join(', ')}
                      </span>
                      <span className="font-mono">{m.name.split(' ').slice(0, 2).join(' ')} ({formatSize(m.size_bytes)})</span>
                    </div>
                  ))}
                </div>
              </div>
            </button>
          )
        })}
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
          onClick={() => tier && onNext(tier)}
          disabled={!tier}
          className="px-6 py-2 text-sm rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  )
}
