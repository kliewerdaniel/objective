import { useState, useEffect } from 'react'
import { HashRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Broadcast from './pages/Broadcast'
import VoiceSwitcher from './pages/VoiceSwitcher'
import PromptEditor from './pages/PromptEditor'
import ModelManager from './pages/ModelManager'
import ConfigEditor from './pages/ConfigEditor'
import SourcesPage from './pages/SourcesPage'
import Wizard from './wizard/Wizard'
import ErrorBoundary from './components/ErrorBoundary'
import { Radio, Loader2, AlertCircle } from 'lucide-react'

type AppState = 'loading' | 'backend-error' | 'wizard' | 'ready'

function App() {
  const [state, setState] = useState<AppState>('loading')
  const [errorMsg, setErrorMsg] = useState<string>('')

  useEffect(() => {
    if (window.electronAPI) {
      window.electronAPI.onBackendReady((port) => {
        window.__BACKEND_PORT__ = port
        checkSetup()
      })

      window.electronAPI.onBackendError((error) => {
        setErrorMsg(error)
        setState('backend-error')
      })

      window.electronAPI.isBackendReady().then((ready) => {
        if (ready) {
          window.electronAPI!.getBackendPort().then((port) => {
            window.__BACKEND_PORT__ = port
            checkSetup()
          })
        }
      })
    } else {
      checkSetup()
    }

    function checkSetup() {
      const apiBase = window.__BACKEND_PORT__
        ? `http://127.0.0.1:${window.__BACKEND_PORT__}`
        : 'http://127.0.0.1:8510'

      fetch(`${apiBase}/api/wizard/status`)
        .then((res) => res.json())
        .then((data) => {
          if (data.setup_complete) {
            setState('ready')
          } else {
            setState('wizard')
          }
        })
        .catch(() => {
          setTimeout(checkSetup, 2000)
        })
    }
  }, [])

  // Loading state
  if (state === 'loading') {
    return (
      <div className="h-screen flex items-center justify-center bg-[#0a0a0a]">
        <div className="text-center">
          <Radio className="h-12 w-12 text-[#00ff88] mx-auto mb-4 animate-pulse" />
          <p className="text-sm text-gray-400">Starting objective03...</p>
          <div className="mt-4 flex items-center gap-2 text-xs text-gray-500">
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>Initializing backend</span>
          </div>
        </div>
      </div>
    )
  }

  // Backend error state
  if (state === 'backend-error') {
    return (
      <div className="h-screen flex items-center justify-center bg-[#0a0a0a]">
        <div className="text-center max-w-md">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-white mb-2">Failed to start backend</h2>
          <div className="bg-[#1a1a1a] rounded-lg p-3 mb-4 text-xs text-left">
            <p className="text-red-400 font-mono whitespace-pre-wrap">{errorMsg}</p>
          </div>
          <div className="rounded-lg bg-[#1a1a1a] p-4 text-xs text-gray-500 text-left font-mono">
            <p className="text-gray-400 mb-2">Make sure Python 3.11+ has all dependencies:</p>
            <p className="text-gray-300 mt-1">cd objective03</p>
            <p className="text-gray-300 mt-1">python3 -m venv .venv</p>
            <p className="text-gray-300 mt-1">source .venv/bin/activate</p>
            <p className="text-gray-300 mt-1">pip install -e .</p>
          </div>
        </div>
      </div>
    )
  }

  // Show wizard if setup not complete
  if (state === 'wizard') {
    return <Wizard onComplete={() => setState('ready')} />
  }

  // Normal app
  return (
    <ErrorBoundary>
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/broadcast" element={<Broadcast />} />
            <Route path="/sources" element={<SourcesPage />} />
            <Route path="/models" element={<ModelManager />} />
            <Route path="/voices" element={<VoiceSwitcher />} />
            <Route path="/prompts" element={<PromptEditor />} />
            <Route path="/prompts/:name" element={<PromptEditor />} />
            <Route path="/config" element={<ConfigEditor />} />
          </Route>
        </Routes>
      </HashRouter>
    </ErrorBoundary>
  )
}

export default App
