import React from 'react'
import ReactMarkdown from 'react-markdown'
import { User, Bot, Loader2, ExternalLink } from 'lucide-react'
import { Message } from '../store/appStore'
import { useAppStore } from '../store/appStore'
import CitationLink from './CitationLink'

interface MessageListProps {
  messages: Message[]
}

const MessageList: React.FC<MessageListProps> = ({ messages }) => {
  const { setSelectedCitation, setCitationModalOpen } = useAppStore()

  const handleCitationClick = (citation: any) => {
    setSelectedCitation(citation)
    setCitationModalOpen(true)
  }

  const formatTimestamp = (timestamp: Date) => {
    return new Intl.DateTimeFormat('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    }).format(timestamp)
  }

  const renderMessage = (message: Message) => {
    const isUser = message.type === 'user'
    
    return (
      <div
        key={message.id}
        className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-6`}
      >
        <div className={`flex max-w-4xl ${isUser ? 'flex-row-reverse' : 'flex-row'} items-start space-x-3`}>
          {/* Avatar */}
          <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
            isUser ? 'bg-blue-600 ml-3' : 'bg-gray-600 mr-3'
          }`}>
            {isUser ? (
              <User className="w-4 h-4 text-white" />
            ) : (
              <Bot className="w-4 h-4 text-white" />
            )}
          </div>

          {/* Message content */}
          <div className={`flex-1 ${isUser ? 'text-right' : 'text-left'}`}>
            <div className={`inline-block max-w-full rounded-lg px-4 py-3 ${
              isUser 
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-100 text-gray-900 border border-gray-200'
            }`}>
              {message.isLoading ? (
                <div className="flex items-center space-x-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">Thinking...</span>
                </div>
              ) : isUser ? (
                <div className="whitespace-pre-wrap break-words">
                  {message.content}
                </div>
              ) : (
                <div className="prose prose-sm max-w-none">
                  <ReactMarkdown
                    components={{
                      // Custom link renderer for citations
                      a: ({ href, children, ...props }) => {
                        if (href?.startsWith('#citation-')) {
                          const citationId = href.replace('#citation-', '')
                          const citation = message.citations?.find(c => c.id === citationId)
                          if (citation) {
                            return (
                              <CitationLink
                                citation={citation}
                                onClick={() => handleCitationClick(citation)}
                              >
                                {children}
                              </CitationLink>
                            )
                          }
                        }
                        return (
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 underline inline-flex items-center"
                            {...props}
                          >
                            {children}
                            <ExternalLink className="w-3 h-3 ml-1" />
                          </a>
                        )
                      },
                      // Style other markdown elements
                      p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                      ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                      li: ({ children }) => <li className="text-sm">{children}</li>,
                      strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                      em: ({ children }) => <em className="italic">{children}</em>,
                      code: ({ children }) => (
                        <code className="bg-gray-200 text-gray-800 px-1 py-0.5 rounded text-xs font-mono">
                          {children}
                        </code>
                      ),
                      pre: ({ children }) => (
                        <pre className="bg-gray-200 text-gray-800 p-3 rounded-md overflow-x-auto text-xs font-mono mb-2">
                          {children}
                        </pre>
                      )
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                </div>
              )}
            </div>

            {/* Citations */}
            {!message.isLoading && message.citations && message.citations.length > 0 && (
              <div className="mt-3 space-y-2">
                <div className="text-xs font-medium text-gray-600 uppercase tracking-wide">
                  Sources ({message.citations.length})
                </div>
                <div className="flex flex-wrap gap-2">
                  {message.citations.map((citation, index) => (
                    <button
                      key={citation.id}
                      onClick={() => handleCitationClick(citation)}
                      className="inline-flex items-center px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded-md hover:bg-blue-100 transition-colors border border-blue-200"
                    >
                      <span className="font-medium">[{index + 1}]</span>
                      <span className="ml-1 truncate max-w-32">
                        {citation.source}
                      </span>
                      {citation.page && (
                        <span className="ml-1 text-blue-500">
                          p.{citation.page}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Timestamp */}
            <div className={`mt-2 text-xs text-gray-500 ${isUser ? 'text-right' : 'text-left'}`}>
              {formatTimestamp(message.timestamp)}
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="px-6 py-4 space-y-4">
      {messages.map(renderMessage)}
    </div>
  )
}

export default MessageList