import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Broadcast from './pages/Broadcast'
import VoiceSwitcher from './pages/VoiceSwitcher'
import PromptEditor from './pages/PromptEditor'
import ModelManager from './pages/ModelManager'
import ConfigEditor from './pages/ConfigEditor'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/broadcast" element={<Broadcast />} />
          <Route path="/voices" element={<VoiceSwitcher />} />
          <Route path="/prompts" element={<PromptEditor />} />
          <Route path="/prompts/:name" element={<PromptEditor />} />
          <Route path="/models" element={<ModelManager />} />
          <Route path="/config" element={<ConfigEditor />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
