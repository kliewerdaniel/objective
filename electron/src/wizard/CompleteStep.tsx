import { Rocket, Radio } from 'lucide-react'
import catalogData from '../data/model-catalog.json'
import type { ModelTier } from './types'

interface CompleteStep {
  selectedTier: string
  selectedVoice: string
  selectedSources: Set<string>
  modelsPath: string
  onLaunch: () => void
}

export default function CompleteStep({
  selectedTier,
  selectedVoice,
  selectedSources,
  modelsPath,
  onLaunch,
}: CompleteStep) {
  const tier = (catalogData.tiers as ModelTier[]).find((t) => t.id === selectedTier)

  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-8">
      <div className="mb-8">
        <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-6">
          <Radio className="h-8 w-8 text-primary" />
        </div>
        <h2 className="text-2xl font-bold mb-2">Setup Complete</h2>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">
          objective03 is configured and ready. Your first broadcast will generate
          in approximately 3-5 minutes after ingestion begins.
        </p>
      </div>

      <div className="w-full max-w-sm space-y-4 mb-8">
        {/* Configuration summary */}
        <div className="rounded-lg border border-border bg-card p-4 text-left space-y-3">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Configuration Summary
          </h3>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Model tier</span>
              <span className="font-medium">{tier?.name || selectedTier}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Voice</span>
              <span className="font-medium capitalize">{selectedVoice}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Sources</span>
              <span className="font-medium">{selectedSources.size} active</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Models dir</span>
              <span className="font-mono text-[10px] truncate ml-2 max-w-[180px] text-right">{modelsPath}</span>
            </div>
          </div>
        </div>

        {/* What happens next */}
        <div className="rounded-lg border border-border bg-card p-4 text-left">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            What Happens Next
          </h3>
          <ul className="space-y-1.5 text-xs text-muted-foreground">
            <li className="flex items-start gap-2">
              <span className="text-primary mt-0.5">1.</span>
              The system begins ingesting news from your selected sources
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary mt-0.5">2.</span>
              Claims, entities, and contradictions are extracted
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary mt-0.5">3.</span>
              A broadcast script is generated and synthesized
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary mt-0.5">4.</span>
              You'll hear your first broadcast in ~3-5 minutes
            </li>
          </ul>
        </div>
      </div>

      <button
        onClick={onLaunch}
        className="px-8 py-3 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors flex items-center gap-2"
      >
        <Rocket className="h-4 w-4" />
        Launch objective03
      </button>

      <p className="text-[10px] text-muted-foreground/60 mt-6">
        You can access settings, sources, and models from the sidebar at any time.
      </p>
    </div>
  )
}
