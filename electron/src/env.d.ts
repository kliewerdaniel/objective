interface ElectronAPI {
  platform: string
  openExternal: (url: string) => Promise<void>
  getBackendPort: () => Promise<number>
  isBackendReady: () => Promise<boolean>
  selectDirectory: (title: string) => Promise<string | null>
  onBackendReady: (callback: (port: number) => void) => void
  onBackendError: (callback: (error: string) => void) => void
  onBackendExited: (callback: (code: number | null) => void) => void
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
    __BACKEND_PORT__?: number
  }
}

export {}
