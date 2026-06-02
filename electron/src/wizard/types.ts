export interface ModelTier {
  id: string
  name: string
  description: string
  total_size_gb: number
  min_ram_gb: number
  quality_stars: number
  estimated_broadcast_minutes: number
  recommended?: boolean
  models: ModelSlot[]
}

export interface ModelSlot {
  slot: string[]
  name: string
  filename: string
  hf_repo: string
  hf_file: string
  size_bytes: number
  context: number
  gpu_layers: number
}

export interface SourceCategory {
  name: string
  sources: SourceItem[]
}

export interface SourceItem {
  name: string
  url: string
  type: 'rss' | 'reddit' | 'youtube'
  subreddit?: string
  channel_id?: string
}

export interface WizardState {
  step: number
  storagePath: string
  modelsPath: string
  selectedTier: string | null
  selectedVoice: string
  customVoiceFile: File | null
  selectedSources: Set<string>
  customRssUrls: string[]
  redditClientId: string
  redditClientSecret: string
  downloads: DownloadState[]
  setupComplete: boolean
}

export interface DownloadState {
  filename: string
  name: string
  status: 'queued' | 'downloading' | 'done' | 'error'
  progress: number
  size_bytes: number
  downloaded_bytes: number
  speed: number
  error?: string
}

export const WIZARD_STEPS = [
  'welcome',
  'storage',
  'models',
  'voice',
  'sources',
  'download',
  'complete',
] as const

export type WizardStep = (typeof WIZARD_STEPS)[number]
