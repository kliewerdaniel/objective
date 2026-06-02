import { app, BrowserWindow, shell, ipcMain, dialog } from 'electron'
import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'
import { spawn, execSync, ChildProcess } from 'child_process'
import net from 'net'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

let mainWindow: BrowserWindow | null = null
let backendProcess: ChildProcess | null = null
let backendPort: number = 0
let backendReady: boolean = false

const isDev = !app.isPackaged

function getResourcesPath(): string {
  if (isDev) {
    return path.join(__dirname, '..', '..')
  }
  return process.resourcesPath
}

function getDataDir(): string {
  if (process.platform === 'darwin') {
    return path.join(app.getPath('home'), 'Library', 'Application Support', 'objective03')
  }
  return path.join(app.getPath('home'), '.objective03')
}

function findAvailablePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.listen(0, '127.0.0.1', () => {
      const addr = server.address()
      if (addr && typeof addr === 'object') {
        const port = addr.port
        server.close(() => resolve(port))
      } else {
        server.close(() => reject(new Error('Failed to get port')))
      }
    })
    server.on('error', reject)
  })
}

function waitForBackend(port: number, timeoutMs: number = 30000): Promise<boolean> {
  return new Promise((resolve) => {
    const start = Date.now()
    const check = () => {
      const req = import('http').then(http => {
        const request = http.default.get(`http://127.0.0.1:${port}/api/status`, (res) => {
          if (res.statusCode === 200) {
            resolve(true)
          } else {
            retry()
          }
        })
        request.on('error', () => retry())
        request.setTimeout(2000, () => {
          request.destroy()
          retry()
        })
      })
    }
    const retry = () => {
      if (Date.now() - start > timeoutMs) {
        resolve(false)
      } else {
        setTimeout(check, 1000)
      }
    }
    check()
  })
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
    titleBarStyle: 'hidden',
    trafficLightPosition: { x: 12, y: 12 },
    show: false,
    backgroundColor: '#0a0a0a',
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

function findPython(): string {
  const candidates: string[] = []

  // Check for .venv in dev project root
  const projectRoot = getResourcesPath()
  const venvPath = path.join(projectRoot, '.venv', 'bin', 'python3')
  if (fs.existsSync(venvPath)) {
    candidates.push(venvPath)
  }

  // Homebrew paths
  candidates.push(
    '/opt/homebrew/bin/python3',
    '/opt/homebrew/bin/python3.11',
    '/opt/homebrew/bin/python3.12',
    '/opt/homebrew/bin/python3.13',
    '/opt/homebrew/bin/python3.14',
    '/usr/local/bin/python3',
    'python3',
  )

  const testCmd = `-c "import uvicorn; import fastapi; import python_multipart; import structlog; import yaml"`
  for (const py of candidates) {
    try {
      execSync(`"${py}" ${testCmd}`, { encoding: 'utf-8', timeout: 5000, stdio: 'pipe' })
      console.log('[electron] Found Python:', py)
      return py
    } catch {
      continue
    }
  }
  return 'python3'
}

function startBackend() {
  const resourcesPath = getResourcesPath()
  const dataDir = getDataDir()

  // In production, backend files are in Resources/backend/
  // In dev, they're at the project root
  const backendDir = isDev
    ? resourcesPath
    : path.join(resourcesPath, 'backend')

  console.log('[electron] isDev:', isDev)
  console.log('[electron] resourcesPath:', resourcesPath)
  console.log('[electron] backendDir:', backendDir)
  console.log('[electron] dataDir:', dataDir)

  // Ensure data dir exists
  try {
    fs.mkdirSync(dataDir, { recursive: true })
  } catch (e) {
    console.warn('[electron] Failed to create data dir:', e)
  }

  findAvailablePort().then((port) => {
    backendPort = port
    console.log('[electron] Using port:', port)

    // Set PYTHONPATH so the backend can find its modules
    const pythonPath = isDev
      ? resourcesPath
      : path.join(resourcesPath, 'backend')

    const env = {
      ...process.env,
      PYTHONUNBUFFERED: '1',
      PYTHONPATH: pythonPath,
      OBJECTIVE03_DATA_DIR: dataDir,
      OBJECTIVE03_PORT: String(port),
    }

    console.log('[electron] PYTHONPATH:', pythonPath)

    const pythonCmd = findPython()

    backendProcess = spawn(pythonCmd, [
      '-m', 'uvicorn',
      'backend.server:app',
      '--host', '127.0.0.1',
      '--port', String(port),
    ], {
      cwd: backendDir,
      stdio: 'pipe',
      env,
    })

    // Log backend output
    backendProcess.stdout?.on('data', (data) => {
      console.log('[backend]', data.toString().trim())
    })

    let stderrBuf = ''
    backendProcess.stderr?.on('data', (data) => {
      const text = data.toString().trim()
      console.error('[backend]', text)
      stderrBuf += text + '\n'
      // Keep last 1KB
      if (stderrBuf.length > 1024) stderrBuf = stderrBuf.slice(-1024)
    })

    // Write port to file
    const portFile = path.join(dataDir, 'backend-port')
    try {
      fs.mkdirSync(path.dirname(portFile), { recursive: true })
      fs.writeFileSync(portFile, String(port), 'utf-8')
    } catch (e) {
      console.warn('[electron] Failed to write port file:', e)
    }

    let backendExited = false

    backendProcess.on('error', (err) => {
      console.error('[electron] Failed to start backend:', err)
      mainWindow?.webContents.send('backend-error', err.message)
    })

    backendProcess.on('exit', (code) => {
      console.log(`[electron] Backend exited with code ${code}`)
      backendExited = true
      backendProcess = null
      backendReady = false
      if (code !== 0 && code !== null) {
        const stderrLines = stderrBuf.split('\n').filter(l => l).slice(-5).join('\n')
        const msg = stderrLines || `Python process exited with code ${code}`
        mainWindow?.webContents.send('backend-error', msg)
      } else {
        mainWindow?.webContents.send('backend-exited', code)
      }
    })

    // Wait for backend to be ready, then notify renderer
    waitForBackend(port).then((ready) => {
      if (backendExited) return
      if (ready) {
        backendReady = true
        console.log('[electron] Backend is ready')
        mainWindow?.webContents.send('backend-ready', port)
      } else {
        console.error('[electron] Backend failed to start within timeout')
        mainWindow?.webContents.send('backend-error', 'Backend failed to start within timeout')
      }
    })
  })
}

function stopBackend() {
  if (backendProcess) {
    backendProcess.kill('SIGTERM')
    backendProcess = null
    backendReady = false
  }
}

app.whenReady().then(() => {
  // IPC handlers
  ipcMain.handle('get-backend-port', () => backendPort)
  ipcMain.handle('is-backend-ready', () => backendReady)
  ipcMain.handle('select-directory', async (_event, title: string) => {
    const result = await dialog.showOpenDialog({
      title,
      properties: ['openDirectory'],
    })
    return result.canceled ? null : result.filePaths[0]
  })

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
