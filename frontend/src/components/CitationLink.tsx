import React from 'react'
import { Citation } from '../store/appStore'

interface CitationLinkProps {
  citation: Citation
  onClick: () => void
  children: React.ReactNode
}

const CitationLink: React.FC<CitationLinkProps> = ({ citation, onClick, children }) => {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center text-blue-600 hover:text-blue-800 underline decoration-dotted underline-offset-2 cursor-pointer transition-colors"
      title={`View source: ${citation.source}${citation.page ? ` (page ${citation.page})` : ''}`}
    >
      {children}
      <sup className="ml-0.5 text-xs font-medium">
        [{citation.confidence > 0.8 ? '✓' : '?'}]
      </sup>
    </button>
  )
}

export default CitationLink