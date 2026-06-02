import { useState } from 'react'
import { Upload, Play, Volume2 } from 'lucide-react'

interface VoiceStep {
  selectedVoice: string
  onNext: (voice: string) => void
  onBack: () => void
}

const BUNDLED_VOICES = [
  {
    id: 'atlas',
    name: 'Atlas',
    description: 'Deep, slow, authoritative',
    preview: 'Across fourteen independent sources, confidence in the official narrative has declined.',
  },
  {
    id: 'meridian',
    name: 'Meridian',
    description: 'Mid-range, neutral, flat',
    preview: 'Breaking developments indicate a shift in regional power dynamics.',
  },
  {
    id: 'cipher',
    name: 'Cipher',
    description: 'Slightly higher, clipped, synthetic',
    preview: 'The data contradicts previous assumptions about supply chain stability.',
  },
]

export default function VoiceStep({ selectedVoice, onNext, onBack }: VoiceStep) {
  const [voice, setVoice] = useState(selectedVoice)
  const [playing, setPlaying] = useState<string | null>(null)

  const handlePreview = (voiceId: string) => {
    if (playing === voiceId) {
      setPlaying(null)
      return
    }
    setPlaying(voiceId)
    // In production, this would play a pre-rendered audio clip
    // For now, simulate with a timeout
    setTimeout(() => setPlaying(null), 3000)
  }

  return (
    <div className="flex flex-col h-full px-8 py-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold">Voice Selection</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Choose the voice for your broadcasts. You can change this later.
        </p>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto">
        {BUNDLED_VOICES.map((v) => {
          const isSelected = voice === v.id
          const isPlaying = playing === v.id
          return (
            <div
              key={v.id}
              onClick={() => setVoice(v.id)}
              className={`rounded-lg border p-4 cursor-pointer transition-all ${
                isSelected
                  ? 'border-primary bg-primary/5 ring-1 ring-primary'
                  : 'border-border bg-card hover:border-border/80'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold">{v.name}</h3>
                    {isSelected && (
                      <span className="text-[10px] text-primary font-medium">Active</span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">{v.description}</p>
                  <p className="text-[10px] text-muted-foreground/60 mt-2 italic max-w-lg">
                    "{v.preview}"
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handlePreview(v.id)
                  }}
                  className="h-10 w-10 rounded-full bg-secondary flex items-center justify-center hover:bg-secondary/80 transition-colors shrink-0 ml-4"
                  title="Preview voice"
                >
                  {isPlaying ? (
                    <Volume2 className="h-4 w-4 text-primary animate-pulse" />
                  ) : (
                    <Play className="h-4 w-4 ml-0.5" />
                  )}
                </button>
              </div>
            </div>
          )
        })}

        {/* Import custom voice */}
        <div className="rounded-lg border border-dashed border-border p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-secondary flex items-center justify-center">
              <Upload className="h-4 w-4 text-muted-foreground" />
            </div>
            <div>
              <p className="text-sm font-medium">Import Custom Voice</p>
              <p className="text-[10px] text-muted-foreground">
                Drop a .wav file (minimum 10 seconds of clear speech) for voice cloning
              </p>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <input
              type="file"
              accept=".wav,.mp3,.flac"
              className="text-xs text-muted-foreground file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:bg-secondary file:text-secondary-foreground hover:file:bg-secondary/80"
              onChange={(e) => {
                // Handle file upload
                const file = e.target.files?.[0]
                if (file) {
                  console.log('Voice file selected:', file.name)
                }
              }}
            />
          </div>
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
          onClick={() => onNext(voice)}
          className="px-6 py-2 text-sm rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  )
}
