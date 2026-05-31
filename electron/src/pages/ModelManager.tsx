import { useEffect, useState } from 'react'
import { getModels, scanModels, getAssignedModels, assignModel, type Model, type ModelAssignment } from '@/lib/api'
import { Folder, Check } from 'lucide-react'

const TASKS = ['extraction', 'entity', 'reasoning', 'broadcast', 'contradiction', 'classification', 'embedding']

export default function ModelManager() {
  const [folder, setFolder] = useState<string>('')
  const [models, setModels] = useState<Model[]>([])
  const [assigned, setAssigned] = useState<Record<string, ModelAssignment>>({})
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [assigning, setAssigning] = useState<string | null>(null)

  useEffect(() => {
    getModels().then((r) => {
      setModels(r.models)
      setFolder(r.folder)
    }).catch(() => {})

    getAssignedModels().then((r) => setAssigned(r.assigned)).catch(() => {})
  }, [])

  const handleScan = async () => {
    if (!folder) return
    setScanning(true)
    setError(null)
    try {
      const r = await scanModels(folder)
      setModels(r.models)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Scan failed')
    } finally {
      setScanning(false)
    }
  }

  const handleAssign = async (task: string, modelPath: string) => {
    setAssigning(`${task}-${modelPath}`)
    try {
      await assignModel(task, modelPath)
      const r = await getAssignedModels()
      setAssigned(r.assigned)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Assign failed')
    } finally {
      setAssigning(null)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Model Manager</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Browse for .gguf model files and assign them to pipeline tasks.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive-foreground">
          {error}
        </div>
      )}

      {/* Folder scanner */}
      <div className="flex items-center gap-2">
        <div className="flex-1 flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2">
          <Folder className="h-4 w-4 text-muted-foreground shrink-0" />
          <input
            value={folder}
            onChange={(e) => setFolder(e.target.value)}
            placeholder="Models folder path"
            className="flex-1 bg-transparent text-sm focus:outline-none"
          />
        </div>
        <button
          onClick={handleScan}
          disabled={scanning || !folder}
          className="px-4 py-2 rounded-lg text-sm bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {scanning ? 'Scanning...' : 'Scan'}
        </button>
      </div>

      {/* Models list */}
      <div className="rounded-lg border border-border bg-card">
        <div className="p-3 border-b border-border">
          <h3 className="text-sm font-semibold">Available Models ({models.length})</h3>
        </div>
        <div className="divide-y divide-border">
          {models.map((m) => (
            <div key={m.path} className="flex items-center gap-4 p-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{m.name}</p>
                <p className="text-xs text-muted-foreground truncate">{m.path}</p>
              </div>
              <span className="text-xs text-muted-foreground shrink-0">{m.size_gb} GB</span>
              <div className="flex gap-1 shrink-0">
                {TASKS.map((task) => {
                  const isAssigned = assigned[task]?.path === m.path
                  const key = `${task}-${m.path}`
                  return (
                    <button
                      key={task}
                      onClick={() => handleAssign(task, m.path)}
                      disabled={assigning === key}
                      title={`Assign to ${task}`}
                      className={`px-2 py-1 rounded text-xs transition-colors ${
                        isAssigned
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                      } ${assigning === key ? 'opacity-50' : ''}`}
                    >
                      {isAssigned && <Check className="inline h-3 w-3 mr-0.5" />}
                      {task.slice(0, 4)}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
          {models.length === 0 && !scanning && (
            <p className="p-4 text-sm text-muted-foreground">No models found. Scan a folder containing .gguf files.</p>
          )}
        </div>
      </div>

      {/* Current assignments */}
      <div className="rounded-lg border border-border bg-card">
        <div className="p-3 border-b border-border">
          <h3 className="text-sm font-semibold">Current Assignments</h3>
        </div>
        <div className="divide-y divide-border">
          {TASKS.map((task) => {
            const cfg = assigned[task]
            return (
              <div key={task} className="flex items-center gap-4 p-3">
                <span className="text-sm font-medium w-32 shrink-0">{task}</span>
                <span className="text-sm truncate">
                  {cfg ? (cfg.name || cfg.path.split('/').pop()) : 'Not assigned'}
                </span>
                {cfg && (
                  <span className="text-xs text-muted-foreground shrink-0">
                    ctx={cfg.context} gpu={cfg.gpu_layers}
                  </span>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
