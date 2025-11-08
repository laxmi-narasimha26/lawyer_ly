import { useState } from 'react'
import ChatInterface from './components/ChatInterface'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import LoginPage from './components/LoginPage'
import CitationViewer from './components/CitationViewer'
import { AuthProvider, useAuth } from './components/AuthProvider'
import { useAppStore } from './store/appStore'
import { Loader2 } from 'lucide-react'

function AppContent() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { isAuthenticated } = useAppStore()
  const { isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <LoginPage />
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      
      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <Header onMenuClick={() => setSidebarOpen(!sidebarOpen)} />
        
        {/* Chat Interface */}
        <main className="flex-1 overflow-hidden">
          <ChatInterface />
        </main>
        
        {/* Footer Disclaimer */}
        <footer className="bg-white border-t border-gray-200 px-6 py-3">
          <p className="text-xs text-gray-500 text-center">
            <strong>Disclaimer:</strong> This AI assistant provides information based on legal sources 
            but is not a substitute for qualified legal advice. Always consult a licensed lawyer for 
            legal matters.
          </p>
        </footer>
      </div>

      {/* Citation Viewer Modal */}
      <CitationViewer />
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

export default App
