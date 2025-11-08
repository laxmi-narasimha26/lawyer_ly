import React, { useState, useEffect } from 'react'
import { X, ExternalLink, BookOpen, Scale, FileText, ChevronLeft, ChevronRight, Copy, Check } from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { citationApi } from '../services/api'
import { useQuery } from '@tanstack/react-query'

const CitationViewer: React.FC = () => {
  const { 
    selectedCitation, 
    citationModalOpen, 
    setCitationModalOpen, 
    setSelectedCitation,
    currentConversation 
  } = useAppStore()
  
  const [currentCitationIndex, setCurrentCitationIndex] = useState(0)
  const [copiedText, setCopiedText] = useState<string | null>(null)

  // Get all citations from the current conversation
  const allCitations = currentConversation?.messages
    .filter(msg => msg.type === 'assistant' && msg.citations)
    .flatMap(msg => msg.citations || []) || []

  // Find current citation index
  useEffect(() => {
    if (selectedCitation && allCitations.length > 0) {
      const index = allCitations.findIndex(c => c.id === selectedCitation.id)
      if (index !== -1) {
        setCurrentCitationIndex(index)
      }
    }
  }, [selectedCitation, allCitations])

  // Fetch citation details
  const { data: citationDetails, isLoading, error } = useQuery({
    queryKey: ['citation', selectedCitation?.id],
    queryFn: () => citationApi.getCitationDetails(selectedCitation!.id),
    enabled: !!selectedCitation?.id,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  const handleClose = () => {
    setCitationModalOpen(false)
    setSelectedCitation(null)
  }

  const handlePrevious = () => {
    if (currentCitationIndex > 0) {
      const prevCitation = allCitations[currentCitationIndex - 1]
      setSelectedCitation(prevCitation)
      setCurrentCitationIndex(currentCitationIndex - 1)
    }
  }

  const handleNext = () => {
    if (currentCitationIndex < allCitations.length - 1) {
      const nextCitation = allCitations[currentCitationIndex + 1]
      setSelectedCitation(nextCitation)
      setCurrentCitationIndex(currentCitationIndex + 1)
    }
  }

  const handleCopyText = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedText(label)
      setTimeout(() => setCopiedText(null), 2000)
    } catch (error) {
      console.error('Failed to copy text:', error)
    }
  }

  const formatCitation = (citation: any) => {
    // Format according to Indian legal citation conventions
    let formatted = citation.source
    
    if (citation.page) {
      formatted += `, p. ${citation.page}`
    }
    
    // Add confidence indicator
    const confidenceText = citation.confidence > 0.8 ? 'High confidence' : 
                          citation.confidence > 0.6 ? 'Medium confidence' : 'Low confidence'
    
    return { formatted, confidenceText }
  }

  const getCitationType = (source: string) => {
    if (source.includes('Supreme Court') || source.includes('High Court')) {
      return { type: 'case', icon: Scale, color: 'text-purple-600 bg-purple-100' }
    } else if (source.includes('Act') || source.includes('Code') || source.includes('Constitution')) {
      return { type: 'statute', icon: BookOpen, color: 'text-blue-600 bg-blue-100' }
    } else {
      return { type: 'document', icon: FileText, color: 'text-green-600 bg-green-100' }
    }
  }

  if (!citationModalOpen || !selectedCitation) return null

  const { formatted: formattedCitation, confidenceText } = formatCitation(selectedCitation)
  const { type, icon: TypeIcon, color } = getCitationType(selectedCitation.source)

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-lg ${color}`}>
              <TypeIcon className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Legal Citation</h2>
              <p className="text-sm text-gray-500 capitalize">{type} • {confidenceText}</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            {/* Navigation */}
            {allCitations.length > 1 && (
              <div className="flex items-center space-x-1 mr-4">
                <button
                  onClick={handlePrevious}
                  disabled={currentCitationIndex === 0}
                  className="p-1 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Previous citation"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-sm text-gray-500 px-2">
                  {currentCitationIndex + 1} of {allCitations.length}
                </span>
                <button
                  onClick={handleNext}
                  disabled={currentCitationIndex === allCitations.length - 1}
                  className="p-1 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Next citation"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
            
            <button
              onClick={handleClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Citation Info */}
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="font-medium text-gray-900 mb-2">Source</h3>
                <p className="text-gray-700">{formattedCitation}</p>
                {selectedCitation.text && (
                  <div className="mt-3">
                    <h4 className="text-sm font-medium text-gray-900 mb-1">Referenced Text</h4>
                    <p className="text-sm text-gray-600 italic">"{selectedCitation.text}"</p>
                  </div>
                )}
              </div>
              <button
                onClick={() => handleCopyText(formattedCitation, 'citation')}
                className="ml-4 p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
                title="Copy citation"
              >
                {copiedText === 'citation' ? (
                  <Check className="w-4 h-4 text-green-500" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          {/* Source Text */}
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <span className="ml-3 text-gray-500">Loading source text...</span>
            </div>
          ) : error ? (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <X className="h-5 w-5 text-red-400" />
                </div>
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-red-800">
                    Unable to load source text
                  </h3>
                  <div className="mt-2 text-sm text-red-700">
                    <p>The full source text could not be retrieved. Please try again later.</p>
                  </div>
                </div>
              </div>
            </div>
          ) : citationDetails ? (
            <div className="space-y-4">
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-start justify-between mb-3">
                  <h3 className="font-medium text-gray-900">Full Source Text</h3>
                  <button
                    onClick={() => handleCopyText(citationDetails.sourceText, 'source')}
                    className="p-1 text-gray-400 hover:text-gray-600 rounded hover:bg-gray-100"
                    title="Copy source text"
                  >
                    {copiedText === 'source' ? (
                      <Check className="w-4 h-4 text-green-500" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </button>
                </div>
                <div className="prose prose-sm max-w-none">
                  <div className="bg-gray-50 rounded-md p-4 border-l-4 border-blue-500">
                    <p className="text-gray-800 leading-relaxed whitespace-pre-wrap">
                      {citationDetails.sourceText}
                    </p>
                  </div>
                </div>
              </div>

              {citationDetails.context && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h4 className="font-medium text-blue-900 mb-2">Additional Context</h4>
                  <p className="text-blue-800 text-sm leading-relaxed">
                    {citationDetails.context}
                  </p>
                </div>
              )}

              {citationDetails.metadata && Object.keys(citationDetails.metadata).length > 0 && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <h4 className="font-medium text-gray-900 mb-3">Document Metadata</h4>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    {Object.entries(citationDetails.metadata).map(([key, value]) => (
                      <div key={key}>
                        <dt className="font-medium text-gray-600 capitalize">
                          {key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}
                        </dt>
                        <dd className="text-gray-900 mt-1">{String(value)}</dd>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 px-6 py-4 bg-gray-50">
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-500">
              <span className="font-medium">Confidence Score:</span> {Math.round(selectedCitation.confidence * 100)}%
            </div>
            <div className="flex space-x-3">
              <button
                onClick={() => window.open(`https://www.google.com/search?q="${encodeURIComponent(selectedCitation.source)}"`, '_blank')}
                className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                <ExternalLink className="w-4 h-4 mr-2" />
                Search Online
              </button>
              <button
                onClick={handleClose}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default CitationViewer