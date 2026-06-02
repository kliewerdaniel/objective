import { Radio } from 'lucide-react'

interface WelcomeStep {
  onNext: () => void
}

export default function WelcomeStep({ onNext }: WelcomeStep) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-8">
      <div className="mb-8">
        <Radio className="h-16 w-16 text-primary mx-auto mb-6" />
        <h1 className="text-4xl font-bold tracking-tight mb-3">objective03</h1>
        <p className="text-muted-foreground text-lg max-w-md mx-auto leading-relaxed">
          A synthetic epistemology engine masquerading as an infinite radio station.
        </p>
      </div>

      <div className="space-y-4 max-w-sm w-full">
        <p className="text-sm text-muted-foreground">
          This wizard will guide you through the initial setup. It takes about 5 minutes
          (plus model download time).
        </p>

        <button
          onClick={onNext}
          className="w-full py-3 px-6 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
        >
          Begin Setup
        </button>

        <p className="text-[10px] text-muted-foreground/60 mt-4">
          All processing happens locally on your Mac. No data leaves your machine.
        </p>
      </div>
    </div>
  )
}
