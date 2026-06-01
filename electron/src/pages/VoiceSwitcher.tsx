import { useEffect, useRef, useState } from 'react'
import { getVoices, setVoice, uploadVoice, type Voice } from '@/lib/api'
import { Check, Upload } from 'lucide-react'

export default function VoiceSwitcher() {
  const [voices, setVoices] = useState<Voice[]>([])
  const [active, setActive] = useState<string>('')
  const [saving, setSaving] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () => {
    getVoices()
      .then((r) => {
        setVoices(r.voices)
        setActive(r.active)
      })
      .catch((e) => setError(e.message))
  }

  useEffect(() => { load() }, [])

  const handleSelect = async (name: string) => {
    if (name === active) return
    setSaving(name)
    try {
      await setVoice(name)
      setActive(name)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to switch voice')
    } finally {
      setSaving(null)
    }
  }

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true)
    setError(null)
    try {
      for (const file of Array.from(files)) {
        await uploadVoice(file)
      }
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    handleUpload(e.dataTransfer.files)
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Voice Switcher</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Select the voice used for TTS broadcast synthesis. Upload .wav files to add new voices.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive-foreground">
          {error}
        </div>
      )}

      {/* Upload area */}
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
        className="flex items-center gap-3 p-4 rounded-lg border border-dashed border-border hover:border-primary/50 cursor-pointer transition-colors"
      >
        <Upload className="h-5 w-5 text-muted-foreground" />
        <div className="flex-1">
          <p className="text-sm font-medium">
            {uploading ? 'Uploading...' : 'Drop voice files here or click to browse'}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">.wav, .mp3, .flac, .ogg</p>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept=".wav,.mp3,.flac,.ogg,audio/*"
          multiple
          className="hidden"
          onChange={(e) => handleUpload(e.target.files)}
        />
      </div>

      <div className="grid grid-cols-3 gap-3">
        {voices.map((v) => {
          const isActive = v.name === active
          const isSaving = saving === v.name
          return (
            <button
              key={v.name}
              onClick={() => handleSelect(v.name)}
              disabled={isSaving}
              className={`relative flex flex-col items-start p-4 rounded-lg border text-left transition-colors ${
                isActive
                  ? 'border-primary bg-accent'
                  : 'border-border hover:border-primary/50 hover:bg-accent/50'
              } ${isSaving ? 'opacity-60' : ''}`}
            >
              <div className="flex items-center gap-2 w-full">
                <span className="font-medium">{v.name}</span>
                {isActive && <Check className="h-4 w-4 text-primary ml-auto" />}
              </div>
              <span className="text-xs text-muted-foreground mt-1">
                {v.format.toUpperCase()}
              </span>
              <span className="text-xs text-muted-foreground truncate w-full mt-0.5" title={v.path}>
                {v.path.split('/').pop()}
              </span>
            </button>
          )
        })}
      </div>

      {voices.length === 0 && !error && (
        <p className="text-sm text-muted-foreground">Loading voices...</p>
      )}
    </div>
  )
}
