import React, { useState } from 'react'
import { Loader2, AlertCircle, CheckCircle, Send } from 'lucide-react'
import { useAuth } from './AuthProvider'
import Beams from './Beams'

const FinalLandingPage: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [authMode, setAuthMode] = useState<'signin' | 'signup'>('signup')
  const [showEmailSuggestions, setShowEmailSuggestions] = useState(false)
  
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: ''
  })
  
  const { login } = useAuth()
  
  const emailDomains = ['gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com', 'icloud.com']
  
  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setFormData({ ...formData, email: value })
    
    // Show suggestions if @ is typed
    if (value.includes('@')) {
      const parts = value.split('@')
      if (parts[0].length > 0) {
        setShowEmailSuggestions(true)
      } else {
        setShowEmailSuggestions(false)
      }
    } else {
      setShowEmailSuggestions(false)
    }
  }
  
  const getFilteredDomains = () => {
    if (!formData.email.includes('@')) return emailDomains
    
    const afterAt = formData.email.split('@')[1] || ''
    if (afterAt.length === 0) return emailDomains
    
    return emailDomains.filter(domain => 
      domain.toLowerCase().startsWith(afterAt.toLowerCase())
    )
  }
  
  const selectEmailDomain = (domain: string) => {
    const emailPrefix = formData.email.split('@')[0]
    setFormData({ ...formData, email: `${emailPrefix}@${domain}` })
    setShowEmailSuggestions(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)
    setSuccess(null)

    console.log('[FinalLandingPage] ========== LOGIN ATTEMPT START ==========')
    console.log('[FinalLandingPage] Mode:', authMode)
    console.log('[FinalLandingPage] Email:', formData.email)
    console.log('[FinalLandingPage] Username:', formData.username)

    try {
      const { authApi } = await import('../services/api')
      const { useAppStore } = await import('../store/appStore')
      
      if (authMode === 'signup') {
        console.log('[FinalLandingPage] Attempting signup...')
        
        if (!formData.username || !formData.email || !formData.password) {
          throw new Error('Please fill in all fields')
        }
        if (formData.password.length < 6) {
          throw new Error('Password must be at least 6 characters')
        }

        console.log('[FinalLandingPage] Calling authApi.register...')
        const response = await authApi.register(formData.username, formData.email, formData.password)
        console.log('[FinalLandingPage] Register response:', response)
        
        // Store ALL user info in localStorage
        localStorage.setItem('auth_token', response.access_token)
        localStorage.setItem('user_id', response.user.id)
        localStorage.setItem('user_email', response.user.email)
        localStorage.setItem('user_name', response.user.username)
        
        console.log('[FinalLandingPage] ✅ User registered successfully:', response.user)
        
        // Update store with user info
        useAppStore.getState().setUser({
          id: response.user.id,
          email: response.user.email,
          name: response.user.username,
          role: 'user'
        })
        
        setSuccess('Account created! Logging you in...')
        
        console.log('[FinalLandingPage] Calling login() with token...')
        setTimeout(async () => {
          try {
            await login(response.access_token)
            console.log('[FinalLandingPage] ✅ Login successful!')
          } catch (loginError: any) {
            console.error('[FinalLandingPage] ❌ Login failed:', loginError)
            setError('Login failed after signup: ' + (loginError.message || 'Unknown error'))
          }
        }, 500)
        
      } else {
        console.log('[FinalLandingPage] Attempting login...')
        
        if (!formData.email || !formData.password) {
          throw new Error('Please enter email and password')
        }

        console.log('[FinalLandingPage] Calling authApi.login...')
        const response = await authApi.login(formData.email, formData.password)
        console.log('[FinalLandingPage] Login response:', response)
        
        // Store ALL user info in localStorage
        localStorage.setItem('auth_token', response.access_token)
        localStorage.setItem('user_id', response.user.id)
        localStorage.setItem('user_email', response.user.email)
        localStorage.setItem('user_name', response.user.username)
        
        console.log('[FinalLandingPage] ✅ User logged in successfully:', response.user)
        
        // Update store with user info
        useAppStore.getState().setUser({
          id: response.user.id,
          email: response.user.email,
          name: response.user.username,
          role: 'user'
        })
        
        setSuccess('Welcome back! Logging you in...')
        
        console.log('[FinalLandingPage] Calling login() with token...')
        setTimeout(async () => {
          try {
            await login(response.access_token)
            console.log('[FinalLandingPage] ✅ Login successful!')
          } catch (loginError: any) {
            console.error('[FinalLandingPage] ❌ Login failed:', loginError)
            setError('Login failed: ' + (loginError.message || 'Unknown error'))
          }
        }, 500)
      }
      
    } catch (error: any) {
      console.error('[FinalLandingPage] ❌ ERROR CAUGHT:', error)
      console.error('[FinalLandingPage] Error type:', error.constructor.name)
      console.error('[FinalLandingPage] Error message:', error.message)
      console.error('[FinalLandingPage] Error response:', error.response)
      console.error('[FinalLandingPage] Error response data:', error.response?.data)
      console.error('[FinalLandingPage] Error response status:', error.response?.status)
      console.error('[FinalLandingPage] Full error object:', JSON.stringify(error, null, 2))
      
      const errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || 'Authentication failed. Please try again.'
      console.error('[FinalLandingPage] Setting error message:', errorMessage)
      setError(errorMessage)
      
      // Keep error visible - don't auto-clear
    } finally {
      setIsLoading(false)
      console.log('[FinalLandingPage] ========== LOGIN ATTEMPT END ==========')
    }
  }

  return (
    <div className="min-h-screen relative overflow-hidden bg-black">
      {/* Beams Background */}
      <div className="absolute inset-0 overflow-hidden">
        <Beams
          beamWidth={1.8}
          beamHeight={25}
          beamNumber={32}
          lightColor="#ffffff"
          speed={8.8}
          noiseIntensity={2.6}
          scale={0.13}
          rotation={13}
        />
      </div>

      {/* Gradient Overlay for readability */}
      <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-black/60 to-black/80"></div>

      {/* Header */}
      <header className="relative z-10 px-6 py-4 flex items-center justify-between backdrop-blur-sm bg-white/5">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
            <span className="text-black text-lg font-bold">⚖</span>
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
            className="bg-white text-black px-6 py-2 rounded-lg font-medium hover:bg-gray-200 transition-colors"
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
                  className="flex-1 text-lg outline-none bg-transparent text-black"
                  onFocus={() => setShowAuthModal(true)}
                />
                <button
                  onClick={() => setShowAuthModal(true)}
                  className="bg-black hover:bg-gray-800 text-white p-3 rounded-xl transition-colors shadow-lg"
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
                <div className="w-6 h-6 bg-white rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-black text-sm">✓</span>
                </div>
                <div>
                  <h3 className="font-semibold text-white">AI-Powered Legal Research</h3>
                  <p className="text-gray-300">Access comprehensive Indian law database with intelligent search</p>
                </div>
              </div>

              <div className="flex items-start space-x-3 bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/10">
                <div className="w-6 h-6 bg-white rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-black text-sm">✓</span>
                </div>
                <div>
                  <h3 className="font-semibold text-white">Document Analysis & Drafting</h3>
                  <p className="text-gray-300">Generate legal documents and analyze contracts efficiently</p>
                </div>
              </div>

              <div className="flex items-start space-x-3 bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/10">
                <div className="w-6 h-6 bg-white rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-black text-sm">✓</span>
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

            {/* OAuth Buttons */}
            <div className="space-y-3 mb-6">
              <button
                type="button"
                onClick={() => alert('Google OAuth coming soon! Use email/password for now.')}
                className="w-full flex justify-center items-center px-4 py-3 border border-gray-300 rounded-lg shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-all"
              >
                <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Continue with Google
              </button>
              
              <button
                type="button"
                onClick={() => alert('Microsoft OAuth coming soon! Use email/password for now.')}
                className="w-full flex justify-center items-center px-4 py-3 border border-gray-300 rounded-lg shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-all"
              >
                <svg className="w-5 h-5 mr-2" viewBox="0 0 23 23">
                  <path fill="#f3f3f3" d="M0 0h23v23H0z"/>
                  <path fill="#f35325" d="M1 1h10v10H1z"/>
                  <path fill="#81bc06" d="M12 1h10v10H12z"/>
                  <path fill="#05a6f0" d="M1 12h10v10H1z"/>
                  <path fill="#ffba08" d="M12 12h10v10H12z"/>
                </svg>
                Continue with Microsoft
              </button>
            </div>

            <div className="relative mb-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-gray-500">Or continue with email</span>
              </div>
            </div>

            {error && (
              <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-start">
                  <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 mr-2 flex-shrink-0" />
                  <div className="flex-1">
                    <p className="text-sm text-red-800 mb-2">{error}</p>
                    {authMode === 'signin' && error.includes('Invalid credentials') && (
                      <div className="mt-2">
                        <p className="text-sm text-red-700">
                          Don't have an account?{' '}
                          <button
                            type="button"
                            onClick={() => {
                              setAuthMode('signup')
                              setError(null)
                            }}
                            className="font-semibold text-blue-600 hover:text-blue-800 underline"
                          >
                            Sign up here
                          </button>
                        </p>
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setError(null)}
                    className="ml-3 flex-shrink-0 text-red-400 hover:text-red-600"
                  >
                    <span className="text-xl">×</span>
                  </button>
                </div>
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
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-black focus:border-transparent outline-none"
                  required={authMode === 'signup'}
                />
              )}

              <div className="relative">
                <input
                  type="email"
                  placeholder="Email"
                  value={formData.email}
                  onChange={handleEmailChange}
                  onBlur={() => setTimeout(() => setShowEmailSuggestions(false), 200)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-black focus:border-transparent outline-none"
                  required
                  autoComplete="email"
                />
                {showEmailSuggestions && getFilteredDomains().length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {getFilteredDomains().map((domain) => (
                      <button
                        key={domain}
                        type="button"
                        onClick={() => selectEmailDomain(domain)}
                        className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm rounded-full border border-gray-300 transition-colors"
                      >
                        {domain}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <input
                type="password"
                placeholder="Password"
                value={formData.password}
                onChange={(e) => setFormData({...formData, password: e.target.value})}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-black focus:border-transparent outline-none"
                required
              />

              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-black hover:bg-gray-800 text-white font-semibold py-3 px-4 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
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
