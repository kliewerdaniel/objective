import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getPrompts, getPrompt, updatePrompt, type Prompt } from '@/lib/api'
import { FileText, Save } from 'lucide-react'

export default function PromptEditor() {
  const { name } = useParams<{ name: string }>()
  const navigate = useNavigate()
  const [prompts, setPrompts] = useState<Prompt[]>([])
  const [activeName, setActiveName] = useState<string>(name || '')
  const [content, setContent] = useState<string>('')
  const [originalContent, setOriginalContent] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getPrompts().then((r) => setPrompts(r.prompts)).catch(() => {})
  }, [])

  useEffect(() => {
    if (name && name !== activeName) {
      setActiveName(name)
    }
  }, [name])

  useEffect(() => {
    if (!activeName) return
    setLoading(true)
    setError(null)
    getPrompt(activeName)
      .then((r) => {
        setContent(r.content)
        setOriginalContent(r.content)
        setSaved(false)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [activeName])

  const handleSave = async () => {
    if (!activeName || content === originalContent) return
    setSaving(true)
    try {
      await updatePrompt(activeName, content)
      setOriginalContent(content)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleSelect = (promptName: string) => {
    setActiveName(promptName)
    navigate(`/prompts/${promptName}`)
  }

  const isDirty = content !== originalContent

  return (
    <div className="flex h-full gap-4">
      {/* File list */}
      <div className="w-56 shrink-0 space-y-2">
        <h2 className="text-2xl font-bold mb-4">Prompts</h2>
        {prompts.map((p) => (
          <button
            key={p.name}
            onClick={() => handleSelect(p.name)}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-left transition-colors ${
              activeName === p.name
                ? 'bg-accent text-accent-foreground'
                : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
            }`}
          >
            <FileText className="h-4 w-4 shrink-0" />
            <span className="truncate">{p.name}</span>
          </button>
        ))}
      </div>

      {/* Editor */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center gap-3 mb-3">
          <h3 className="font-semibold">{activeName || 'Select a prompt'}</h3>
          {isDirty && (
            <span className="text-xs text-yellow-500">Unsaved changes</span>
          )}
          {saved && (
            <span className="text-xs text-green-500">Saved</span>
          )}
          <button
            onClick={handleSave}
            disabled={!activeName || !isDirty || saving}
            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm bg-primary text-primary-foreground disabled:opacity-50 hover:bg-primary/90 transition-colors"
          >
            <Save className="h-3.5 w-3.5" />
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>

        {error && (
          <div className="mb-3 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive-foreground">
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : activeName ? (
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            className="flex-1 w-full rounded-lg border border-border bg-card p-4 font-mono text-sm resize-none focus:outline-none focus:ring-1 focus:ring-ring"
            spellCheck={false}
          />
        ) : (
          <p className="text-sm text-muted-foreground">Select a prompt file to edit</p>
        )}
      </div>
    </div>
  )
}
