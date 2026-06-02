import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  openExternal: (url: string) => ipcRenderer.invoke('open-external', url),
  getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
  isBackendReady: () => ipcRenderer.invoke('is-backend-ready'),
  selectDirectory: (title: string) => ipcRenderer.invoke('select-directory', title),
  onBackendReady: (callback: (port: number) => void) => {
    ipcRenderer.on('backend-ready', (_event, port) => callback(port))
  },
  onBackendError: (callback: (error: string) => void) => {
    ipcRenderer.on('backend-error', (_event, error) => callback(error))
  },
  onBackendExited: (callback: (code: number | null) => void) => {
    ipcRenderer.on('backend-exited', (_event, code) => callback(code))
  },
})
