import React from 'react'
import { MessageCircle, PenTool, FileText, Check } from 'lucide-react'
import { useAppStore, QueryMode } from '../store/appStore'

const ModeSelector: React.FC = () => {
  const { mode, setMode } = useAppStore()

  const modes = [
    {
      id: 'qa' as QueryMode,
      name: 'Q&A Mode',
      description: 'Ask legal questions and get accurate answers with citations',
      icon: MessageCircle,
      color: 'blue',
      features: [
        'Factual legal answers',
        'Source citations',
        'Indian law focus',
        'Quick responses'
      ]
    },
    {
      id: 'drafting' as QueryMode,
      name: 'Drafting Mode',
      description: 'Get help drafting legal documents and clauses',
      icon: PenTool,
      color: 'green',
      features: [
        'Document drafting',
        'Legal language',
        'Template generation',
        'Clause suggestions'
      ]
    },
    {
      id: 'summarization' as QueryMode,
      name: 'Summarization Mode',
      description: 'Summarize uploaded documents and extract key points',
      icon: FileText,
      color: 'purple',
      features: [
        'Document summaries',
        'Key point extraction',
        'Section analysis',
        'Quick insights'
      ]
    }
  ]

  const getColorClasses = (color: string, isSelected: boolean) => {
    const colors = {
      blue: {
        border: isSelected ? 'border-blue-500' : 'border-gray-200 hover:border-blue-300',
        bg: isSelected ? 'bg-blue-50' : 'bg-white hover:bg-blue-50',
        icon: isSelected ? 'text-blue-600' : 'text-gray-400',
        text: isSelected ? 'text-blue-900' : 'text-gray-900',
        description: isSelected ? 'text-blue-700' : 'text-gray-600',
        feature: isSelected ? 'text-blue-600' : 'text-gray-500'
      },
      green: {
        border: isSelected ? 'border-green-500' : 'border-gray-200 hover:border-green-300',
        bg: isSelected ? 'bg-green-50' : 'bg-white hover:bg-green-50',
        icon: isSelected ? 'text-green-600' : 'text-gray-400',
        text: isSelected ? 'text-green-900' : 'text-gray-900',
        description: isSelected ? 'text-green-700' : 'text-gray-600',
        feature: isSelected ? 'text-green-600' : 'text-gray-500'
      },
      purple: {
        border: isSelected ? 'border-purple-500' : 'border-gray-200 hover:border-purple-300',
        bg: isSelected ? 'bg-purple-50' : 'bg-white hover:bg-purple-50',
        icon: isSelected ? 'text-purple-600' : 'text-gray-400',
        text: isSelected ? 'text-purple-900' : 'text-gray-900',
        description: isSelected ? 'text-purple-700' : 'text-gray-600',
        feature: isSelected ? 'text-purple-600' : 'text-gray-500'
      }
    }
    return colors[color as keyof typeof colors]
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">Select Mode</h3>
        <p className="text-sm text-gray-600">
          Choose how you want to interact with the AI assistant
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {modes.map((modeOption) => {
          const isSelected = mode === modeOption.id
          const colors = getColorClasses(modeOption.color, isSelected)
          const Icon = modeOption.icon

          return (
            <button
              key={modeOption.id}
              onClick={() => setMode(modeOption.id)}
              className={`relative p-6 rounded-lg border-2 text-left transition-all duration-200 ${colors.border} ${colors.bg}`}
            >
              {/* Selection indicator */}
              {isSelected && (
                <div className="absolute top-4 right-4">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
                    modeOption.color === 'blue' ? 'bg-blue-600' :
                    modeOption.color === 'green' ? 'bg-green-600' : 'bg-purple-600'
                  }`}>
                    <Check className="w-4 h-4 text-white" />
                  </div>
                </div>
              )}

              {/* Icon */}
              <div className="mb-4">
                <Icon className={`w-8 h-8 ${colors.icon}`} />
              </div>

              {/* Title and description */}
              <div className="mb-4">
                <h4 className={`text-lg font-semibold mb-2 ${colors.text}`}>
                  {modeOption.name}
                </h4>
                <p className={`text-sm ${colors.description}`}>
                  {modeOption.description}
                </p>
              </div>

              {/* Features */}
              <div className="space-y-2">
                {modeOption.features.map((feature, index) => (
                  <div key={index} className="flex items-center space-x-2">
                    <div className={`w-1.5 h-1.5 rounded-full ${
                      modeOption.color === 'blue' ? 'bg-blue-400' :
                      modeOption.color === 'green' ? 'bg-green-400' : 'bg-purple-400'
                    }`} />
                    <span className={`text-xs ${colors.feature}`}>
                      {feature}
                    </span>
                  </div>
                ))}
              </div>
            </button>
          )
        })}
      </div>

      {/* Current mode info */}
      <div className="bg-gray-50 rounded-lg p-4">
        <div className="flex items-center space-x-2 mb-2">
          <div className="w-2 h-2 bg-green-500 rounded-full"></div>
          <span className="text-sm font-medium text-gray-900">
            Current Mode: {modes.find(m => m.id === mode)?.name}
          </span>
        </div>
        <p className="text-sm text-gray-600">
          {modes.find(m => m.id === mode)?.description}
        </p>
      </div>
    </div>
  )
}

export default ModeSelector