import React from 'react'
import { Zap, Scale, Microscope, Target, BookOpen, Clock, Check } from 'lucide-react'

interface ChatMode {
  id: string
  name: string
  icon: React.ReactNode
  description: string
  features: string[]
  estimatedTime: string
  bestFor: string
  color: string
  gradient: string
}

const CHAT_MODES: ChatMode[] = [
  {
    id: 'quick_response',
    name: '⚡ Quick Response',
    icon: <Zap className="w-6 h-6" />,
    description: 'Fast answers for straightforward legal questions. Perfect for quick clarifications and simple queries.',
    features: [
      'Minimal context for speed',
      'Single AI model (fastest)',
      'No web search',
      'Direct answers with basic citations'
    ],
    estimatedTime: '< 5 seconds',
    bestFor: 'Quick definitions, simple procedural questions, statute lookups',
    color: 'cyan',
    gradient: 'from-cyan-400 to-cyan-600'
  },
  {
    id: 'balanced',
    name: '⚖️ Balanced',
    icon: <Scale className="w-6 h-6" />,
    description: 'Default mode balancing speed, accuracy, and depth. Best for most legal queries.',
    features: [
      'Moderate conversation context',
      'Smart web search when needed',
      'Document analysis included',
      'Structured responses with citations'
    ],
    estimatedTime: '< 15 seconds',
    bestFor: 'Contract analysis, legal strategy, case law research, compliance questions',
    color: 'blue',
    gradient: 'from-blue-500 to-blue-700'
  },
  {
    id: 'deep_research',
    name: '🔬 Deep Research',
    icon: <Microscope className="w-6 h-6" />,
    description: 'Comprehensive legal research with extensive web search and multiple sources. For complex matters.',
    features: [
      'Extensive legal database search',
      'Multiple web sources verification',
      'Cross-reference case law',
      'Multi-model consensus (GPT-4 + Claude)',
      'Comprehensive citation analysis'
    ],
    estimatedTime: '< 45 seconds',
    bestFor: 'Complex litigation strategy, novel legal issues, comprehensive research',
    color: 'purple',
    gradient: 'from-purple-500 to-purple-700'
  },
  {
    id: 'multi_query_analysis',
    name: '🎯 Multi-Query Analysis',
    icon: <Target className="w-6 h-6" />,
    description: 'Analyzes current query in context of past 5-10 queries. Perfect for iterative analysis.',
    features: [
      'Analyzes patterns across queries',
      'Tracks evolving positions',
      'Identifies contradictions',
      'Builds comprehensive timeline',
      'Synthesizes multi-query insights'
    ],
    estimatedTime: '< 25 seconds',
    bestFor: 'Iterative contract negotiation, evolving case strategy, progressive research',
    color: 'orange',
    gradient: 'from-orange-500 to-orange-700'
  },
  {
    id: 'full_context_review',
    name: '📚 Full Context Review',
    icon: <BookOpen className="w-6 h-6" />,
    description: 'Comprehensive mode using entire conversation history and all documents. For final reviews.',
    features: [
      'Entire conversation context',
      'All document analysis',
      'Comprehensive web research',
      'Multi-model verification',
      'Cross-reference all discussions',
      'Quality assurance checks'
    ],
    estimatedTime: '< 60 seconds',
    bestFor: 'Final legal opinions, comprehensive case review, due diligence summaries',
    color: 'green',
    gradient: 'from-green-500 to-green-700'
  },
]

interface ChatModeSelectorProps {
  selectedMode: string
  onSelectMode: (modeId: string) => void
  onClose: () => void
}

const ChatModeSelector: React.FC<ChatModeSelectorProps> = ({
  selectedMode,
  onSelectMode,
  onClose
}) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 px-8 py-6 text-white">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-3xl font-bold">Select Chat Mode</h2>
            <button
              onClick={onClose}
              className="text-white hover:bg-white hover:bg-opacity-20 rounded-full p-2 transition-all"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <p className="text-indigo-100">Choose the analysis depth and research intensity that best fits your needs</p>
        </div>

        {/* Modes Grid */}
        <div className="p-8 overflow-y-auto max-h-[calc(90vh-180px)]">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {CHAT_MODES.map((mode) => {
              const isSelected = selectedMode === mode.id

              return (
                <div
                  key={mode.id}
                  onClick={() => onSelectMode(mode.id)}
                  className={`
                    relative group cursor-pointer rounded-xl overflow-hidden
                    transition-all duration-300 border-2
                    ${isSelected
                      ? 'border-blue-500 shadow-2xl scale-105'
                      : 'border-gray-200 hover:border-gray-300 hover:shadow-xl'
                    }
                  `}
                >
                  {/* Header with Gradient */}
                  <div className={`bg-gradient-to-r ${mode.gradient} px-6 py-4`}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-3">
                        <div className="bg-white bg-opacity-20 backdrop-blur-md rounded-lg p-2 text-white">
                          {mode.icon}
                        </div>
                        <h3 className="text-xl font-bold text-white">{mode.name}</h3>
                      </div>
                      {isSelected && (
                        <div className="bg-white text-blue-600 rounded-full p-1">
                          <Check className="w-5 h-5" />
                        </div>
                      )}
                    </div>
                    <div className="flex items-center space-x-2 text-white text-opacity-90">
                      <Clock className="w-4 h-4" />
                      <span className="text-sm font-medium">{mode.estimatedTime}</span>
                    </div>
                  </div>

                  {/* Content */}
                  <div className="p-6 bg-white">
                    {/* Description */}
                    <p className="text-gray-700 mb-4 leading-relaxed">{mode.description}</p>

                    {/* Best For */}
                    <div className="mb-4 p-3 bg-gray-50 rounded-lg">
                      <p className="text-sm font-semibold text-gray-700 mb-1">Best For:</p>
                      <p className="text-sm text-gray-600">{mode.bestFor}</p>
                    </div>

                    {/* Features */}
                    <div>
                      <p className="text-sm font-semibold text-gray-700 mb-2">Features:</p>
                      <ul className="space-y-2">
                        {mode.features.map((feature, idx) => (
                          <li key={idx} className="flex items-start space-x-2 text-sm text-gray-600">
                            <svg className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                            <span>{feature}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  {/* Selection Overlay */}
                  {isSelected && (
                    <div className="absolute inset-0 border-4 border-blue-500 rounded-xl pointer-events-none" />
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-8 py-4 border-t border-gray-200 flex items-center justify-between">
          <div className="text-sm text-gray-600">
            <span className="font-medium">Current Mode:</span>{' '}
            <span className="text-gray-800 font-semibold">
              {CHAT_MODES.find(m => m.id === selectedMode)?.name || 'Balanced'}
            </span>
          </div>
          <button
            onClick={onClose}
            className="px-6 py-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-lg font-medium transition-all shadow-md hover:shadow-lg"
          >
            Confirm Selection
          </button>
        </div>
      </div>
    </div>
  )
}

export default ChatModeSelector
