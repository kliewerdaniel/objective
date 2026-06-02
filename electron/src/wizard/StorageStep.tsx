import { useState } from 'react'
import { Folder, HardDrive, FolderOpen } from 'lucide-react'

interface StorageStep {
  storagePath: string
  modelsPath: string
  onNext: (storagePath: string, modelsPath: string) => void
  onBack: () => void
}

export default function StorageStep({ storagePath, modelsPath, onNext, onBack }: StorageStep) {
  const [selectedModelsPath, setSelectedModelsPath] = useState(modelsPath)

  const handleBrowseData = async () => {
    if (window.electronAPI) {
      const dir = await window.electronAPI.selectDirectory('Choose objective03 data directory')
      if (dir) {
        setSelectedModelsPath(dir + '/models')
      }
    }
  }

  const handleBrowseModels = async () => {
    if (window.electronAPI) {
      const dir = await window.electronAPI.selectDirectory('Choose existing models directory')
      if (dir) {
        setSelectedModelsPath(dir)
      }
    }
  }

  const tiers = [
    { label: 'Minimum', size: '~4 GB', desc: 'Single model' },
    { label: 'Recommended', size: '~12 GB', desc: 'Balanced tier' },
    { label: 'Full Suite', size: '~25 GB', desc: 'All models' },
  ]

  return (
    <div className="flex flex-col h-full px-8 py-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold">Storage Location</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Choose where objective03 stores its data and models. You can point to an existing models directory to skip download.
        </p>
      </div>

      <div className="flex-1 space-y-6">
        {/* Data directory */}
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center gap-2 mb-3">
            <HardDrive className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold">Application Data</h3>
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs bg-secondary px-3 py-2 rounded font-mono truncate">
              {storagePath}
            </code>
            <button
              onClick={handleBrowseData}
              className="px-3 py-2 text-xs rounded bg-secondary hover:bg-secondary/80 transition-colors shrink-0 flex items-center gap-1"
            >
              <Folder className="h-3 w-3" /> Change
            </button>
          </div>
          <p className="text-[10px] text-muted-foreground mt-2">
            Graph database, metadata, audio cache, and logs.
          </p>
        </div>

        {/* Models directory */}
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center gap-2 mb-3">
            <FolderOpen className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold">Models Directory</h3>
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs bg-secondary px-3 py-2 rounded font-mono truncate">
              {selectedModelsPath}
            </code>
            <button
              onClick={handleBrowseModels}
              className="px-3 py-2 text-xs rounded bg-secondary hover:bg-secondary/80 transition-colors shrink-0 flex items-center gap-1"
            >
              <FolderOpen className="h-3 w-3" /> Browse
            </button>
          </div>
          <p className="text-[10px] text-muted-foreground mt-2">
            Point to an existing directory with model files to skip download, or use the default to download fresh models (4-25 GB total).
          </p>
        </div>

        {/* Disk usage estimates */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3">Estimated Disk Usage</h3>
          <div className="grid grid-cols-3 gap-3">
            {tiers.map((tier) => (
              <div key={tier.label} className="text-center">
                <p className="text-lg font-bold">{tier.size}</p>
                <p className="text-xs text-muted-foreground">{tier.label}</p>
                <p className="text-[10px] text-muted-foreground/60">{tier.desc}</p>
              </div>
            ))}
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
          onClick={() => onNext(storagePath, selectedModelsPath)}
          className="px-6 py-2 text-sm rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  )
}
