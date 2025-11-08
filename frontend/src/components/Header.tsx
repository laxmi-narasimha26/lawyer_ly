import React, { useState } from 'react'
import { Menu, Settings as SettingsIcon, User, LogOut, FileText, Plus } from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { useAuth } from './AuthProvider'
import Settings from './Settings'
import DocumentManager from './DocumentManager'

interface HeaderProps {
  onMenuClick: () => void
}

const Header: React.FC<HeaderProps> = ({ onMenuClick }) => {
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showDocuments, setShowDocuments] = useState(false)
  const { user, mode, createConversation } = useAppStore()
  const { logout } = useAuth()

  const handleLogout = async () => {
    try {
      await logout()
    } catch (error) {
      console.error('Logout failed:', error)
    }
  }

  const getModeLabel = () => {
    switch (mode) {
      case 'qa': return 'Q&A'
      case 'drafting': return 'Drafting'
      case 'summarization': return 'Summary'
      default: return 'Q&A'
    }
  }

  const getModeColor = () => {
    switch (mode) {
      case 'qa': return 'bg-blue-100 text-blue-800'
      case 'drafting': return 'bg-green-100 text-green-800'
      case 'summarization': return 'bg-purple-100 text-purple-800'
      default: return 'bg-blue-100 text-blue-800'
    }
  }

  return (
    <>
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Left side */}
          <div className="flex items-center space-x-4">
            <button
              onClick={onMenuClick}
              className="p-2 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 lg:hidden"
            >
              <Menu className="w-5 h-5" />
            </button>
            
            <div className="flex items-center space-x-3">
              <h1 className="text-xl font-semibold text-gray-900">
                Indian Legal AI
              </h1>
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${getModeColor()}`}>
                {getModeLabel()}
              </span>
            </div>
          </div>

          {/* Center - New Chat Button */}
          <div className="hidden md:flex">
            <button
              onClick={createConversation}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              <Plus className="w-4 h-4 mr-2" />
              New Chat
            </button>
          </div>

          {/* Right side */}
          <div className="flex items-center space-x-3">
            {/* Documents button */}
            <button
              onClick={() => setShowDocuments(true)}
              className="p-2 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100"
              title="Manage Documents"
            >
              <FileText className="w-5 h-5" />
            </button>

            {/* Settings button */}
            <button
              onClick={() => setShowSettings(true)}
              className="p-2 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100"
              title="Settings"
            >
              <SettingsIcon className="w-5 h-5" />
            </button>

            {/* User menu */}
            <div className="relative">
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center space-x-2 p-2 rounded-md text-gray-700 hover:bg-gray-100"
              >
                <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
                  <User className="w-4 h-4 text-white" />
                </div>
                <span className="hidden md:block text-sm font-medium">
                  {user?.name || 'Guest'}
                </span>
              </button>

              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 z-50 border border-gray-200">
                  <div className="px-4 py-2 border-b border-gray-100">
                    <p className="text-sm font-medium text-gray-900">
                      {user?.name || 'Guest User'}
                    </p>
                    <p className="text-xs text-gray-500">
                      {user?.email || 'Not signed in'}
                    </p>
                  </div>
                  
                  <button
                    onClick={() => {
                      setShowSettings(true)
                      setShowUserMenu(false)
                    }}
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                  >
                    <SettingsIcon className="w-4 h-4 mr-3" />
                    Settings
                  </button>
                  
                  <button
                    onClick={() => {
                      setShowDocuments(true)
                      setShowUserMenu(false)
                    }}
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                  >
                    <FileText className="w-4 h-4 mr-3" />
                    Documents
                  </button>
                  
                  <div className="border-t border-gray-100">
                    <button
                      onClick={() => {
                        handleLogout()
                        setShowUserMenu(false)
                      }}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                    >
                      <LogOut className="w-4 h-4 mr-3" />
                      Sign Out
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Mobile new chat button */}
        <div className="md:hidden mt-3">
          <button
            onClick={createConversation}
            className="w-full inline-flex items-center justify-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Chat
          </button>
        </div>
      </header>

      {/* Click outside to close user menu */}
      {showUserMenu && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setShowUserMenu(false)}
        />
      )}

      {/* Modals */}
      <Settings isOpen={showSettings} onClose={() => setShowSettings(false)} />
      <DocumentManager isOpen={showDocuments} onClose={() => setShowDocuments(false)} />
    </>
  )
}

export default Header