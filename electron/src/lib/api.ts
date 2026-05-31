const API_BASE = 'http://127.0.0.1:8510'

export interface Voice {
  name: string
  path: string
  format: string
  directory: string
}

export interface Model {
  name: string
  path: string
  size_bytes: number
  size_gb: number
}

export interface Prompt {
  name: string
  path: string
  size_bytes: number
}

export interface ModelAssignment {
  path: string
  context: number
  gpu_layers: number
  name: string
  chat_format: string
}

export interface Broadcast {
  id: string
  filename: string
  path: string
  duration: number
  sample_rate: number
  subdir: string
  size_bytes: number
  created_at: number
}

export interface PipelineStage {
  id: string
  label: string
  icon: string
}

export interface PipelineState {
  stages: PipelineStage[]
  current_stage: string | null
  completed_stages: string[]
  failed_stage: string | null
  broadcast_id: string | null
  generating: boolean
  script_preview: string | null
  segments_total: number
  segments_done: number
  current_segment_text: string | null
  is_playing: boolean
  now_playing: { path: string; filename: string; duration: number } | null
  playback_position: number
  playback_duration: number
  generation_error: string | null
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// Status
export const getStatus = () => request<{ system_name: string; config_path: string; prompts_dir: string; voices_dir: string; models_dir: string; audio_dir: string }>('/api/status')
export const getDaemonStatus = () => request<{ daemon_running: boolean; pid: string | null; uptime: string | null; launchd_managed: boolean; scheduler_intervals: Record<string, number> }>('/api/daemon')

// Config
export const getConfig = () => request<Record<string, unknown>>('/api/config')
export const updateConfig = (content: string) =>
  request<{ ok: boolean }>('/api/config', { method: 'PUT', body: JSON.stringify({ content }) })

// Voices
export const getVoices = () => request<{ voices: Voice[]; active: string }>('/api/voices')
export const setVoice = (voice: string) =>
  request<{ ok: boolean }>('/api/voice', { method: 'PUT', body: JSON.stringify({ voice }) })

// Models
export const getModels = () => request<{ models: Model[]; folder: string }>('/api/models')
export const scanModels = (folder: string) =>
  request<{ models: Model[]; folder: string }>(`/api/models/scan?folder=${encodeURIComponent(folder)}`)
export const getAssignedModels = () => request<{ assigned: Record<string, ModelAssignment> }>('/api/models/assigned')
export const assignModel = (task: string, path: string, opts?: { context?: number; gpu_layers?: number; name?: string; chat_format?: string }) =>
  request<{ ok: boolean }>('/api/models/assign', {
    method: 'PUT',
    body: JSON.stringify({ task, path, ...opts }),
  })

// Prompts
export const getPrompts = () => request<{ prompts: Prompt[]; directory: string }>('/api/prompts')
export const getPrompt = (name: string) => request<{ name: string; content: string; path: string }>(`/api/prompts/${name}`)
export const updatePrompt = (name: string, content: string) =>
  request<{ ok: boolean }>(`/api/prompts/${name}`, { method: 'PUT', body: JSON.stringify({ content }) })

// Pipeline
export const getPipeline = () => request<PipelineState>('/api/pipeline')
export const resetPipeline = () => request<{ ok: boolean }>('/api/pipeline/reset', { method: 'POST' })
export const startNewBroadcast = () =>
  request<{ ok: boolean; message: string }>('/api/broadcast/new', { method: 'POST' })

// Broadcasts
export const getBroadcasts = () => request<{ broadcasts: Broadcast[] }>('/api/broadcasts')
export const getNowPlaying = () => request<{ is_playing: boolean; now_playing: { path: string; filename: string; duration: number } | null; playback_position: number; playback_duration: number }>('/api/broadcasts/now-playing')
export const playBroadcast = (audioPath: string) =>
  request<{ ok: boolean; duration: number }>('/api/broadcasts/play', {
    method: 'POST',
    body: JSON.stringify({ audio_path: audioPath }),
  })
export const stopBroadcast = () =>
  request<{ ok: boolean }>('/api/broadcasts/stop', { method: 'POST' })
export const deleteBroadcast = (id: string) =>
  request<{ ok: boolean; deleted: string }>(`/api/broadcasts/${id}`, { method: 'DELETE' })
export const clearBroadcasts = () =>
  request<{ ok: boolean; deleted: number }>('/api/broadcasts', { method: 'DELETE' })
export const renameBroadcast = (id: string, name: string) =>
  request<{ ok: boolean; filename: string }>(`/api/broadcasts/${id}/rename`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
export const downloadBroadcastUrl = (id: string) => `${API_BASE}/api/broadcasts/${id}/download`

// SSE
export function subscribeEvents(onEvent: (event: { type: string; data: Record<string, unknown>; timestamp: string }) => void) {
  const source = new EventSource(`${API_BASE}/api/events`)
  source.onmessage = (e) => {
    try {
      onEvent(JSON.parse(e.data))
    } catch { /* ignore parse errors */ }
  }
  source.onerror = () => {
    console.warn('SSE connection lost, reconnecting...')
  }
  return () => source.close()
}
