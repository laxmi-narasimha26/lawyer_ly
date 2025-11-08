import React from 'react'
import { X, MessageSquare, Clock, Trash2, Search } from 'lucide-react'
import { useAppStore } from '../store/appStore'

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { 
    conversations, 
    currentConversation, 
    setCurrentConversation,
    createConversation 
  } = useAppStore()

  const formatDate = (date: Date) => {
    const now = new Date()
    const diffInHours = Math.abs(now.getTime() - date.getTime()) / (1000 * 60 * 60)
    
    if (diffInHours < 24) {
      return new Intl.DateTimeFormat('en-IN', {
        hour: '2-digit',
        minute: '2-digit'
      }).format(date)
    } else if (diffInHours < 24 * 7) {
      return new Intl.DateTimeFormat('en-IN', {
        weekday: 'short'
      }).format(date)
    } else {
      return new Intl.DateTimeFormat('en-IN', {
        month: 'short',
        day: 'numeric'
      }).format(date)
    }
  }

  const getConversationTitle = (conversation: any) => {
    if (conversation.messages.length === 0) {
      return 'New Conversation'
    }
    
    const firstUserMessage = conversation.messages.find((msg: any) => msg.type === 'user')
    if (firstUserMessage) {
      return firstUserMessage.content.length > 50 
        ? firstUserMessage.content.substring(0, 50) + '...'
        : firstUserMessage.content
    }
    
    return conversation.title || 'Untitled Conversation'
  }

  const handleConversationClick = (conversation: any) => {
    setCurrentConversation(conversation)
    onClose() // Close sidebar on mobile after selection
  }

  const handleNewChat = () => {
    createConversation()
    onClose()
  }

  return (
    <>
      {/* Overlay for mobile */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <div className={`fixed inset-y-0 left-0 z-50 w-80 bg-white border-r border-gray-200 transform transition-transform duration-300 ease-in-out lg:translate-x-0 lg:static lg:inset-0 ${
        isOpen ? 'translate-x-0' : '-translate-x-full'
      }`}>
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Conversations</h2>
            <button
              onClick={onClose}
              className="p-1 rounded-md text-gray-400 hover:text-gray-600 lg:hidden"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* New Chat Button */}
          <div className="p-4 border-b border-gray-200">
            <button
              onClick={handleNewChat}
              className="w-full flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              <MessageSquare className="w-4 h-4 mr-2" />
              New Chat
            </button>
          </div>

          {/* Search */}
          <div className="p-4 border-b border-gray-200">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                type="text"
                placeholder="Search conversations..."
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Conversations List */}
          <div className="flex-1 overflow-y-auto">
            {conversations.length === 0 ? (
              <div className="p-4 text-center text-gray-500">
                <MessageSquare className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                <p className="text-sm">No conversations yet</p>
                <p className="text-xs text-gray-400 mt-1">
                  Start a new chat to begin
                </p>
              </div>
            ) : (
              <div className="p-2 space-y-1">
                {conversations.map((conversation) => (
                  <div
                    key={conversation.id}
                    onClick={() => handleConversationClick(conversation)}
                    className={`w-full text-left p-3 rounded-lg transition-colors group cursor-pointer ${
                      currentConversation?.id === conversation.id
                        ? 'bg-blue-50 border border-blue-200'
                        : 'hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <h3 className={`text-sm font-medium truncate ${
                          currentConversation?.id === conversation.id
                            ? 'text-blue-900'
                            : 'text-gray-900'
                        }`}>
                          {getConversationTitle(conversation)}
                        </h3>
                        <div className="flex items-center mt-1 space-x-2">
                          <Clock className="w-3 h-3 text-gray-400" />
                          <span className="text-xs text-gray-500">
                            {formatDate(conversation.updatedAt)}
                          </span>
                          <span className="text-xs text-gray-400">
                            • {conversation.messages.length} messages
                          </span>
                        </div>
                      </div>

                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          // TODO: Implement delete conversation
                          console.log('Delete conversation:', conversation.id)
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-600 transition-all"
                        title="Delete conversation"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-gray-200 bg-gray-50">
            <div className="text-xs text-gray-500 text-center">
              <p>Conversations are saved locally</p>
              <p className="mt-1">
                {conversations.length} conversation{conversations.length !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

export default Sidebar