import { useEffect, useState } from 'react'
import { getConfig, updateConfig } from '@/lib/api'
import { Save } from 'lucide-react'

export default function ConfigEditor() {
  const [content, setContent] = useState<string>('')
  const [originalContent, setOriginalContent] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getConfig()
      .then((data) => {
        const yaml = Object.entries(data)
          .map(([k, v]) => `${k}:\n${yamlBlock(v, 2)}`)
          .join('\n')
        setContent(yaml)
        setOriginalContent(yaml)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await updateConfig(content)
      setOriginalContent(content)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const isDirty = content !== originalContent

  return (
    <div className="flex flex-col h-full space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-2xl font-bold">Config Editor</h2>
        {isDirty && <span className="text-xs text-yellow-500">Unsaved changes</span>}
        {saved && <span className="text-xs text-green-500">Saved</span>}
        <button
          onClick={handleSave}
          disabled={!isDirty || saving}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm bg-primary text-primary-foreground disabled:opacity-50 hover:bg-primary/90 transition-colors"
        >
          <Save className="h-3.5 w-3.5" />
          {saving ? 'Saving...' : 'Save'}
        </button>
      </div>

      <p className="text-sm text-muted-foreground">
        Edit config.yaml directly. Changes are saved to disk and apply on next daemon restart.
      </p>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive-foreground">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading config...</p>
      ) : (
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="flex-1 w-full rounded-lg border border-border bg-card p-4 font-mono text-sm resize-none focus:outline-none focus:ring-1 focus:ring-ring"
          spellCheck={false}
        />
      )}
    </div>
  )
}

function yamlBlock(value: unknown, indent: number): string {
  const pad = ' '.repeat(indent)
  if (value === null || value === undefined) return `${pad}null`
  if (typeof value === 'string') return `${pad}${value}`
  if (typeof value === 'number' || typeof value === 'boolean') return `${pad}${value}`
  if (Array.isArray(value)) {
    if (value.length === 0) return `${pad}[]`
    return value.map((item) => {
      if (typeof item === 'object' && item !== null) {
        const inner = Object.entries(item as Record<string, unknown>)
          .map(([k, v]) => `${pad}  ${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`)
          .join('\n')
        return `${pad}-\n${inner}`
      }
      return `${pad}- ${item}`
    }).join('\n')
  }
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => {
        if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
          return `${pad}${k}:\n${yamlBlock(v, indent + 2)}`
        }
        return `${pad}${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`
      })
      .join('\n')
  }
  return `${pad}${String(value)}`
}
