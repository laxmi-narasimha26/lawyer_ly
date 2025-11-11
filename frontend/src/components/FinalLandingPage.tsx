import React, { useState } from 'react'
import { Loader2, AlertCircle, CheckCircle, Send } from 'lucide-react'
import { useAuth } from './AuthProvider'
import Galaxy from './Galaxy'

const FinalLandingPage: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [authMode, setAuthMode] = useState<'signin' | 'signup'>('signup')
  
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: ''
  })
  
  const { login } = useAuth()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)
    setSuccess(null)

    try {
      const { authApi } = await import('../services/api')
      
      if (authMode === 'signup') {
        if (!formData.username || !formData.email || !formData.password) {
          throw new Error('Please fill in all fields')
        }
        if (formData.password.length < 6) {
          throw new Error('Password must be at least 6 characters')
        }

        const response = await authApi.register(formData.username, formData.email, formData.password)
        localStorage.setItem('auth_token', response.access_token)
        localStorage.setItem('user_id', response.user.id)
        setSuccess('Account created!')
        
        setTimeout(async () => {
          await login(response.access_token)
        }, 500)
        
      } else {
        if (!formData.email || !formData.password) {
          throw new Error('Please enter email and password')
        }

        const response = await authApi.login(formData.email, formData.password)
        localStorage.setItem('auth_token', response.access_token)
        localStorage.setItem('user_id', response.user.id)
        setSuccess('Welcome back!')
        
        setTimeout(async () => {
          await login(response.access_token)
        }, 500)
      }
      
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Authentication failed'
      setError(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen relative overflow-hidden" style={{ background: '#0a0a1a' }}>
      {/* Galaxy Background */}
      <div className="absolute inset-0 overflow-hidden">
        <Galaxy
          mouseInteraction={true}
          mouseRepulsion={true}
          glowIntensity={0.5}
          saturation={1.5}
          hueShift={240}
          density={1.2}
          rotationSpeed={0.05}
          twinkleIntensity={0.5}
          transparent={false}
        />
      </div>

      {/* Gradient Overlay for readability */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-black/30 to-black/50"></div>

      {/* Header */}
      <header className="relative z-10 px-6 py-4 flex items-center justify-between backdrop-blur-sm bg-white/5">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 bg-orange-500 rounded-lg flex items-center justify-center">
            <span className="text-white text-lg font-bold">⚖</span>
          </div>
          <span className="text-xl font-bold text-white">Lawyer.ly</span>
        </div>
        
        <nav className="hidden md:flex items-center space-x-8">
          <button className="text-gray-200 hover:text-white font-medium">Product</button>
          <button className="text-gray-200 hover:text-white font-medium">Solutions</button>
          <button className="text-gray-200 hover:text-white font-medium">Pricing</button>
          <button className="text-gray-200 hover:text-white font-medium">Blog</button>
          <button className="text-gray-200 hover:text-white font-medium">Learn</button>
        </nav>

        <div className="flex items-center space-x-4">
          <button 
            onClick={() => { setShowAuthModal(true); setAuthMode('signin'); }}
            className="text-gray-200 hover:text-white font-medium"
          >
            Contact sales
          </button>
          <button 
            onClick={() => { setShowAuthModal(true); setAuthMode('signup'); }}
            className="bg-orange-500 text-white px-6 py-2 rounded-lg font-medium hover:bg-orange-600 transition-colors"
          >
            Try Lawyer.ly
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 py-20">
        <div className="flex flex-col lg:flex-row items-center justify-between gap-16">
          
          {/* Left Side */}
          <div className="flex-1 max-w-2xl">
            <h1 className="text-6xl font-bold text-white mb-6 leading-tight drop-shadow-lg">
              Meet your<br />thinking partner
            </h1>
            
            <p className="text-xl text-gray-200 mb-8 drop-shadow-md">
              Tackle any big, bold, bewildering challenge with Lawyer.ly
            </p>

            {/* Query Box */}
            <div className="bg-white/95 backdrop-blur-md rounded-2xl shadow-2xl p-6 mb-8 border border-white/20">
              <div className="flex items-center space-x-4">
                <input
                  type="text"
                  placeholder="How can I help you today?"
                  className="flex-1 text-lg outline-none bg-transparent"
                  onFocus={() => setShowAuthModal(true)}
                />
                <button 
                  onClick={() => setShowAuthModal(true)}
                  className="bg-orange-500 hover:bg-orange-600 text-white p-3 rounded-xl transition-colors shadow-lg"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
              
              <div className="flex items-center space-x-4 mt-4 pt-4 border-t border-gray-200">
                <button className="flex items-center space-x-2 text-sm text-gray-700 hover:text-gray-900">
                  <span>✍️</span>
                  <span>Write</span>
                </button>
                <button className="flex items-center space-x-2 text-sm text-gray-700 hover:text-gray-900">
                  <span>📚</span>
                  <span>Learn</span>
                </button>
                <button className="flex items-center space-x-2 text-sm text-gray-700 hover:text-gray-900">
                  <span>💻</span>
                  <span>Code</span>
                </button>
              </div>
            </div>

            {/* Features */}
            <div className="space-y-4">
              <div className="flex items-start space-x-3 bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/10">
                <div className="w-6 h-6 bg-orange-500 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-white text-sm">✓</span>
                </div>
                <div>
                  <h3 className="font-semibold text-white">AI-Powered Legal Research</h3>
                  <p className="text-gray-300">Access comprehensive Indian law database with intelligent search</p>
                </div>
              </div>
              
              <div className="flex items-start space-x-3 bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/10">
                <div className="w-6 h-6 bg-orange-500 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-white text-sm">✓</span>
                </div>
                <div>
                  <h3 className="font-semibold text-white">Document Analysis & Drafting</h3>
                  <p className="text-gray-300">Generate legal documents and analyze contracts efficiently</p>
                </div>
              </div>
              
              <div className="flex items-start space-x-3 bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/10">
                <div className="w-6 h-6 bg-orange-500 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-white text-sm">✓</span>
                </div>
                <div>
                  <h3 className="font-semibold text-white">Case Law & Precedents</h3>
                  <p className="text-gray-300">Instant access to relevant case law and legal precedents</p>
                </div>
              </div>
            </div>
          </div>

          {/* Right Side - Image */}
          <div className="flex-1 flex items-center justify-center">
            <img 
              src="/lawyer_ly_icon.png" 
              alt="Legal AI Illustration" 
              className="w-full max-w-2xl h-auto drop-shadow-2xl"
              style={{ maxHeight: '700px', objectFit: 'contain' }}
            />
          </div>
        </div>
      </main>

      {/* Auth Modal */}
      {showAuthModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-8 relative">
            <button
              onClick={() => setShowAuthModal(false)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>

            <h2 className="text-2xl font-bold text-gray-900 mb-6">
              {authMode === 'signup' ? 'Create your account' : 'Welcome back'}
            </h2>

            {error && (
              <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 flex items-start">
                <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 mr-2 flex-shrink-0" />
                <p className="text-sm text-red-800">{error}</p>
              </div>
            )}

            {success && (
              <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-3 flex items-start">
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5 mr-2 flex-shrink-0" />
                <p className="text-sm text-green-800">{success}</p>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {authMode === 'signup' && (
                <input
                  type="text"
                  placeholder="Username"
                  value={formData.username}
                  onChange={(e) => setFormData({...formData, username: e.target.value})}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none"
                  required={authMode === 'signup'}
                />
              )}

              <input
                type="email"
                placeholder="Email"
                value={formData.email}
                onChange={(e) => setFormData({...formData, email: e.target.value})}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none"
                required
              />

              <input
                type="password"
                placeholder="Password"
                value={formData.password}
                onChange={(e) => setFormData({...formData, password: e.target.value})}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none"
                required
              />

              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-orange-500 hover:bg-orange-600 text-white font-semibold py-3 px-4 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin mr-2" />
                    {authMode === 'signup' ? 'Creating account...' : 'Signing in...'}
                  </>
                ) : (
                  authMode === 'signup' ? 'Create Account' : 'Sign In'
                )}
              </button>

              <button
                type="button"
                onClick={() => {
                  setAuthMode(authMode === 'signup' ? 'signin' : 'signup')
                  setError(null)
                  setSuccess(null)
                }}
                className="w-full text-center text-sm text-gray-600 hover:text-gray-900"
              >
                {authMode === 'signup' ? 'Already have an account? Sign In' : "Don't have an account? Sign Up"}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default FinalLandingPage
