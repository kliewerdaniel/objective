import { app, BrowserWindow, shell } from 'electron'
import path from 'path'
import { fileURLToPath } from 'url'
import { spawn, ChildProcess } from 'child_process'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

let mainWindow: BrowserWindow | null = null
let backendProcess: ChildProcess | null = null

const BACKEND_PORT = 8510
const isDev = !app.isPackaged

function getProjectRoot(): string {
  if (isDev) {
    return path.join(__dirname, '..', '..')
  }
  return path.join(process.resourcesPath, '..')
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.mjs'),
    },
    titleBarStyle: 'hiddenInset',
    show: false,
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

function startBackend() {
  const projectRoot = getProjectRoot()
  console.log('[electron] Starting backend from:', projectRoot)

  backendProcess = spawn('python3', ['-m', 'uvicorn', 'backend.server:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)], {
    cwd: projectRoot,
    stdio: 'inherit',
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
  })

  backendProcess.on('error', (err) => {
    console.error('[electron] Failed to start backend:', err)
  })

  backendProcess.on('exit', (code) => {
    console.log(`[electron] Backend exited with code ${code}`)
    backendProcess = null
  })
}

function stopBackend() {
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }
}

app.whenReady().then(() => {
  startBackend()
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  stopBackend()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  stopBackend()
})
