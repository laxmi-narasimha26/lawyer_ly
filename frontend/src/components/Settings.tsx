import React, { useState } from 'react'
import { Settings as SettingsIcon, X, User, Shield, HelpCircle, Trash2, Download } from 'lucide-react'
import { useAppStore } from '../store/appStore'
import ModeSelector from './ModeSelector'

interface SettingsProps {
  isOpen: boolean
  onClose: () => void
}

const Settings: React.FC<SettingsProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'general' | 'privacy' | 'help'>('general')
  const { user, conversations, clearConversation } = useAppStore()

  if (!isOpen) return null

  const tabs = [
    { id: 'general', name: 'General', icon: SettingsIcon },
    { id: 'privacy', name: 'Privacy & Data', icon: Shield },
    { id: 'help', name: 'Help & Support', icon: HelpCircle }
  ]

  const handleClearAllConversations = () => {
    if (confirm('Are you sure you want to clear all conversation history? This action cannot be undone.')) {
      // Clear all conversations
      conversations.forEach(() => clearConversation())
      alert('All conversations have been cleared.')
    }
  }

  const handleExportData = () => {
    const data = {
      conversations: conversations.map(conv => ({
        id: conv.id,
        title: conv.title,
        createdAt: conv.createdAt,
        messageCount: conv.messages.length
      })),
      exportDate: new Date().toISOString()
    }
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `legal-ai-data-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Settings</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar */}
          <div className="w-64 bg-gray-50 border-r border-gray-200 p-4">
            <nav className="space-y-2">
              {tabs.map((tab) => {
                const Icon = tab.icon
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-left transition-colors ${
                      activeTab === tab.id
                        ? 'bg-blue-100 text-blue-700'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="font-medium">{tab.name}</span>
                  </button>
                )
              })}
            </nav>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeTab === 'general' && (
              <div className="space-y-8">
                {/* User Profile */}
                <div>
                  <h3 className="text-lg font-medium text-gray-900 mb-4">User Profile</h3>
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="flex items-center space-x-4">
                      <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center">
                        <User className="w-6 h-6 text-white" />
                      </div>
                      <div>
                        <h4 className="font-medium text-gray-900">
                          {user?.name || 'Guest User'}
                        </h4>
                        <p className="text-sm text-gray-600">
                          {user?.email || 'Not signed in'}
                        </p>
                        <p className="text-xs text-gray-500 capitalize">
                          {user?.role || 'user'}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Mode Selection */}
                <div>
                  <h3 className="text-lg font-medium text-gray-900 mb-4">AI Assistant Mode</h3>
                  <ModeSelector />
                </div>

                {/* Conversation Management */}
                <div>
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Conversation Management</h3>
                  <div className="space-y-4">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="font-medium text-gray-900">Conversation History</h4>
                          <p className="text-sm text-gray-600">
                            You have {conversations.length} saved conversations
                          </p>
                        </div>
                        <button
                          onClick={handleClearAllConversations}
                          className="inline-flex items-center px-3 py-2 border border-red-300 rounded-md text-sm font-medium text-red-700 bg-white hover:bg-red-50"
                        >
                          <Trash2 className="w-4 h-4 mr-2" />
                          Clear All
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'privacy' && (
              <div className="space-y-8">
                <div>
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Privacy & Data Protection</h3>
                  <div className="space-y-6">
                    {/* Data Usage */}
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <div className="flex">
                        <div className="flex-shrink-0">
                          <Shield className="h-5 w-5 text-blue-400" />
                        </div>
                        <div className="ml-3">
                          <h3 className="text-sm font-medium text-blue-800">
                            Your Data is Protected
                          </h3>
                          <div className="mt-2 text-sm text-blue-700">
                            <ul className="list-disc list-inside space-y-1">
                              <li>All data is encrypted in transit and at rest</li>
                              <li>Your documents and conversations are private to you</li>
                              <li>We don't use your data to train AI models</li>
                              <li>Data is stored in India to comply with local regulations</li>
                            </ul>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Data Export */}
                    <div className="bg-white border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="font-medium text-gray-900">Export Your Data</h4>
                          <p className="text-sm text-gray-600">
                            Download a copy of your conversation history and metadata
                          </p>
                        </div>
                        <button
                          onClick={handleExportData}
                          className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                        >
                          <Download className="w-4 h-4 mr-2" />
                          Export Data
                        </button>
                      </div>
                    </div>

                    {/* Data Retention */}
                    <div className="bg-white border border-gray-200 rounded-lg p-4">
                      <h4 className="font-medium text-gray-900 mb-2">Data Retention Policy</h4>
                      <div className="text-sm text-gray-600 space-y-2">
                        <p>• Conversations are stored until you delete them</p>
                        <p>• Uploaded documents are stored until you remove them</p>
                        <p>• System logs are retained for 90 days for security purposes</p>
                        <p>• You can request complete data deletion by contacting support</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'help' && (
              <div className="space-y-8">
                <div>
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Help & Support</h3>
                  <div className="space-y-6">
                    {/* Quick Help */}
                    <div className="bg-white border border-gray-200 rounded-lg p-4">
                      <h4 className="font-medium text-gray-900 mb-3">Quick Start Guide</h4>
                      <div className="space-y-3 text-sm text-gray-600">
                        <div className="flex items-start space-x-3">
                          <div className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-medium">1</div>
                          <div>
                            <p className="font-medium text-gray-900">Choose Your Mode</p>
                            <p>Select Q&A for questions, Drafting for documents, or Summarization for analysis</p>
                          </div>
                        </div>
                        <div className="flex items-start space-x-3">
                          <div className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-medium">2</div>
                          <div>
                            <p className="font-medium text-gray-900">Upload Documents (Optional)</p>
                            <p>Upload legal documents to get specific answers about your content</p>
                          </div>
                        </div>
                        <div className="flex items-start space-x-3">
                          <div className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-medium">3</div>
                          <div>
                            <p className="font-medium text-gray-900">Ask Questions</p>
                            <p>Type your legal questions and get answers with citations to sources</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* FAQ */}
                    <div className="bg-white border border-gray-200 rounded-lg p-4">
                      <h4 className="font-medium text-gray-900 mb-3">Frequently Asked Questions</h4>
                      <div className="space-y-4 text-sm">
                        <div>
                          <p className="font-medium text-gray-900">What types of legal questions can I ask?</p>
                          <p className="text-gray-600 mt-1">You can ask about Indian law, including constitutional law, criminal law, civil law, corporate law, and more. The AI has knowledge of major statutes and case law.</p>
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">How accurate are the AI responses?</p>
                          <p className="text-gray-600 mt-1">The AI provides responses based on legal sources and includes citations. However, always verify important information and consult a qualified lawyer for legal advice.</p>
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">What file formats can I upload?</p>
                          <p className="text-gray-600 mt-1">You can upload PDF, DOCX, and TXT files up to 50MB each. The system will extract text and make it searchable.</p>
                        </div>
                      </div>
                    </div>

                    {/* Contact */}
                    <div className="bg-white border border-gray-200 rounded-lg p-4">
                      <h4 className="font-medium text-gray-900 mb-3">Need More Help?</h4>
                      <div className="space-y-3 text-sm text-gray-600">
                        <p>If you need additional assistance or have feedback:</p>
                        <div className="space-y-2">
                          <p>• Email: support@indianlegalai.com</p>
                          <p>• Documentation: Available in the knowledge base</p>
                          <p>• Response time: Within 24 hours during business days</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 px-6 py-4 bg-gray-50">
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-500">
              Indian Legal AI Assistant v1.0.0
            </div>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Settings