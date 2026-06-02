import { useState, useCallback } from 'react'
import { Radio } from 'lucide-react'
import WelcomeStep from './WelcomeStep'
import StorageStep from './StorageStep'
import ModelsStep from './ModelsStep'
import VoiceStep from './VoiceStep'
import SourcesStep from './SourcesStep'
import DownloadStep from './DownloadStep'
import CompleteStep from './CompleteStep'
import { WIZARD_STEPS } from './types'

interface WizardProps {
  onComplete: () => void
}

const DATA_DIR = '~/Library/Application Support/objective03'

export default function Wizard({ onComplete }: WizardProps) {
  const [step, setStep] = useState<number>(0)
  const [storagePath] = useState(DATA_DIR)
  const [modelsPath, setModelsPath] = useState(DATA_DIR + '/models')
  const [selectedTier, setSelectedTier] = useState<string | null>(null)
  const [selectedVoice, setSelectedVoice] = useState('atlas')
  const [selectedSources, setSelectedSources] = useState<Set<string>>(new Set())
  const [customRssUrls, setCustomRssUrls] = useState<string[]>([])

  const currentStep = WIZARD_STEPS[step]

  const goNext = useCallback(() => {
    setStep((s) => Math.min(s + 1, WIZARD_STEPS.length - 1))
  }, [])

  const goBack = useCallback(() => {
    setStep((s) => Math.max(s - 1, 0))
  }, [])

  const handleStorageNext = (_storage: string, models: string) => {
    setModelsPath(models)
    goNext()
  }

  const handleModelsNext = (tierId: string) => {
    setSelectedTier(tierId)
    goNext()
  }

  const handleVoiceNext = (voice: string) => {
    setSelectedVoice(voice)
    goNext()
  }

  const handleSourcesNext = (sources: Set<string>, customUrls: string[]) => {
    setSelectedSources(sources)
    setCustomRssUrls(customUrls)
    goNext()
  }

  const handleLaunch = async () => {
    // Detect if user pointed to a custom models directory (not the default)
    const defaultModelsPath = DATA_DIR + '/models'
    const useExistingModels = modelsPath !== defaultModelsPath

    try {
      await fetch(`http://127.0.0.1:${window.__BACKEND_PORT__ || 8510}/api/wizard/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          storage_path: storagePath,
          models_path: modelsPath,
          tier: selectedTier,
          voice: selectedVoice,
          sources: Array.from(selectedSources),
          custom_rss_urls: customRssUrls,
          use_existing_models: useExistingModels,
        }),
      })
    } catch {
      // Backend might not be ready yet, continue anyway
    }
    onComplete()
  }

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <div className="h-12 flex items-center px-4 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <Radio className="h-4 w-4 text-primary" />
          <span className="text-sm font-bold tracking-tight">objective03</span>
        </div>
        <div className="flex-1 flex justify-center">
          <div className="flex items-center gap-1">
            {WIZARD_STEPS.map((s, i) => (
              <div
                key={s}
                className={`h-1.5 rounded-full transition-all ${
                  i === step
                    ? 'w-6 bg-primary'
                    : i < step
                    ? 'w-1.5 bg-primary/60'
                    : 'w-1.5 bg-muted-foreground/20'
                }`}
              />
            ))}
          </div>
        </div>
        <div className="text-[10px] text-muted-foreground">
          {step + 1} / {WIZARD_STEPS.length}
        </div>
      </div>

      {/* Step content */}
      <div className="flex-1 overflow-hidden">
        {currentStep === 'welcome' && <WelcomeStep onNext={goNext} />}
        {currentStep === 'storage' && (
          <StorageStep
            storagePath={storagePath}
            modelsPath={modelsPath}
            onNext={handleStorageNext}
            onBack={goBack}
          />
        )}
        {currentStep === 'models' && (
          <ModelsStep
            selectedTier={selectedTier}
            onNext={handleModelsNext}
            onBack={goBack}
          />
        )}
        {currentStep === 'voice' && (
          <VoiceStep
            selectedVoice={selectedVoice}
            onNext={handleVoiceNext}
            onBack={goBack}
          />
        )}
        {currentStep === 'sources' && (
          <SourcesStep
            selectedSources={selectedSources}
            customRssUrls={customRssUrls}
            onNext={handleSourcesNext}
            onBack={goBack}
          />
        )}
        {currentStep === 'download' && selectedTier && (
          <DownloadStep
            selectedTier={selectedTier}
            modelsPath={modelsPath}
            onNext={goNext}
            onBack={goBack}
          />
        )}
        {currentStep === 'complete' && (
          <CompleteStep
            selectedTier={selectedTier || 'balanced'}
            selectedVoice={selectedVoice}
            selectedSources={selectedSources}
            modelsPath={modelsPath}
            onLaunch={handleLaunch}
          />
        )}
      </div>
    </div>
  )
}
