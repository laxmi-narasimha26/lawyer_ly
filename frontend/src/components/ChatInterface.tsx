import React, { useState, useRef, useEffect } from 'react'
import { Send, Loader2, AlertCircle } from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { chatApi } from '../services/api'
import MessageList from './MessageList'
import { useMutation } from '@tanstack/react-query'

const ChatInterface: React.FC = () => {
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  const {
    currentConversation,
    mode,
    selectedDocument,
    addMessage,
    updateMessage,
    createConversation
  } = useAppStore()

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [currentConversation?.messages])

  const sendQueryMutation = useMutation({
    mutationFn: async (query: string) => {
      // Add user message immediately
      addMessage({
        type: 'user',
        content: query
      })

      // Add loading assistant message
      const assistantMessageId = crypto.randomUUID()
      addMessage({
        type: 'assistant',
        content: '',
        isLoading: true
      })

      try {
        const response = await chatApi.sendQuery({
          query,
          mode,
          conversationId: currentConversation?.id,
          documentId: selectedDocument?.id
        })

        // Update assistant message with response
        updateMessage(assistantMessageId, {
          content: response.answer,
          citations: response.citations,
          isLoading: false
        })

        return response
      } catch (error) {
        // Update assistant message with error
        updateMessage(assistantMessageId, {
          content: 'I apologize, but I encountered an error while processing your request. Please try again.',
          isLoading: false
        })
        throw error
      }
    },
    onError: (error: any) => {
      setError(error.response?.data?.message || 'Failed to send message. Please try again.')
    }
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!input.trim() || sendQueryMutation.isPending) return

    const query = input.trim()
    setInput('')
    setError(null)

    // Create conversation if none exists
    if (!currentConversation) {
      createConversation()
    }

    try {
      await sendQueryMutation.mutateAsync(query)
    } catch (error) {
      // Error is handled in mutation
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    
    // Auto-resize textarea
    const textarea = e.target
    textarea.style.height = 'auto'
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px'
  }

  const getModeLabel = () => {
    switch (mode) {
      case 'qa': return 'Q&A Mode'
      case 'drafting': return 'Drafting Mode'
      case 'summarization': return 'Summarization Mode'
      default: return 'Q&A Mode'
    }
  }

  const getPlaceholder = () => {
    switch (mode) {
      case 'qa':
        return selectedDocument 
          ? `Ask a question about ${selectedDocument.filename}...`
          : 'Ask a legal question...'
      case 'drafting':
        return 'Describe the legal document you want to draft...'
      case 'summarization':
        return selectedDocument
          ? `Ask for a summary of ${selectedDocument.filename}...`
          : 'Upload a document to summarize...'
      default:
        return 'Type your message...'
    }
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Mode indicator */}
      <div className="flex-shrink-0 bg-blue-50 border-b border-blue-200 px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
            <span className="text-sm font-medium text-blue-700">{getModeLabel()}</span>
            {selectedDocument && (
              <>
                <span className="text-blue-400">•</span>
                <span className="text-sm text-blue-600">
                  Analyzing: {selectedDocument.filename}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        {currentConversation?.messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center max-w-md mx-auto px-6">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Welcome to Indian Legal AI Assistant
              </h3>
              <p className="text-gray-600 mb-4">
                {mode === 'qa' && 'Ask me any question about Indian law, and I\'ll provide accurate answers with citations.'}
                {mode === 'drafting' && 'Describe the legal document you need, and I\'ll help you draft it.'}
                {mode === 'summarization' && selectedDocument 
                  ? 'Ask me to summarize your uploaded document or specific sections.'
                  : 'Upload a document first, then ask me to summarize it.'
                }
              </p>
              <p className="text-sm text-gray-500">
                Start by typing your question below.
              </p>
            </div>
          </div>
        ) : (
          <MessageList messages={currentConversation?.messages || []} />
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Error display */}
      {error && (
        <div className="flex-shrink-0 bg-red-50 border-t border-red-200 px-6 py-3">
          <div className="flex items-center space-x-2 text-red-700">
            <AlertCircle className="w-4 h-4" />
            <span className="text-sm">{error}</span>
            <button
              onClick={() => setError(null)}
              className="ml-auto text-red-500 hover:text-red-700"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="flex-shrink-0 bg-white border-t border-gray-200 px-6 py-4">
        <form onSubmit={handleSubmit} className="flex items-end space-x-3">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder={getPlaceholder()}
              disabled={sendQueryMutation.isPending}
              className="w-full resize-none rounded-lg border border-gray-300 px-4 py-3 pr-12 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
              style={{ minHeight: '52px', maxHeight: '120px' }}
              rows={1}
            />
            <div className="absolute right-3 bottom-3 text-xs text-gray-400">
              {input.length}/2000
            </div>
          </div>
          <button
            type="submit"
            disabled={!input.trim() || sendQueryMutation.isPending}
            className="flex-shrink-0 bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {sendQueryMutation.isPending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </form>
        
        <div className="mt-2 text-xs text-gray-500 text-center">
          Press Enter to send, Shift+Enter for new line
        </div>
      </div>
    </div>
  )
}

export default ChatInterface