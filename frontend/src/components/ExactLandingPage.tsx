import React, { useState } from 'react'
import { Loader2, AlertCircle, CheckCircle } from 'lucide-react'
import { useAuth } from './AuthProvider'

const ExactLandingPage: React.FC = () => {
  const [mode, setMode] = useState<'signin' | 'signup'>('signup')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  
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
      
      if (mode === 'signup') {
        if (!formData.username || !formData.email || !formData.password) {
          throw new Error('Please fill in all fields')
        }
        if (formData.password.length < 6) {
          throw new Error('Password must be at least 6 characters')
        }

        const response = await authApi.register(formData.username, formData.email, formData.password)
        localStorage.setItem('auth_token', response.access_token)
        localStorage.setItem('user_id', response.user.id)
        setSuccess('Account created! Logging you in...')
        
        setTimeout(async () => {
          await login(response.access_token)
        }, 800)
        
      } else {
        if (!formData.email || !formData.password) {
          throw new Error('Please enter email and password')
        }

        const response = await authApi.login(formData.email, formData.password)
        localStorage.setItem('auth_token', response.access_token)
        localStorage.setItem('user_id', response.user.id)
        setSuccess('Login successful!')
        
        setTimeout(async () => {
          await login(response.access_token)
        }, 800)
      }
      
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Authentication failed'
      setError(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-amber-50 to-orange-100 flex items-center justify-center p-4">
      <div className="w-full max-w-6xl flex flex-col lg:flex-row items-center justify-between gap-12">
        
        {/* Left Side - Content */}
        <div className="flex-1 max-w-xl">
          {/* Logo */}
          <div className="flex items-center space-x-2 mb-8">
            <div className="w-8 h-8 bg-orange-500 rounded-full flex items-center justify-center">
              <span className="text-white text-xl">⚖</span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Lawyer.ly</h1>
          </div>

          {/* Main Heading */}
          <h2 className="text-5xl font-bold text-gray-900 mb-4 leading-tight">
            Your Legal<br />Intelligence Partner
          </h2>
          
          <p className="text-lg text-gray-600 mb-8">
            Trusted insights for Indian law practice
          </p>

          {/* Form */}
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-md">
            {error && (
              <div className="mb-4 bg-red-50 border border-red-200 rounded-md p-3 flex items-start">
                <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 mr-2 flex-shrink-0" />
                <p className="text-sm text-red-800">{error}</p>
              </div>
            )}

            {success && (
              <div className="mb-4 bg-green-50 border border-green-200 rounded-md p-3 flex items-start">
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5 mr-2 flex-shrink-0" />
                <p className="text-sm text-green-800">{success}</p>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === 'signup' && (
                <div>
                  <input
                    type="text"
                    placeholder="Username"
                    value={formData.username}
                    onChange={(e) => setFormData({...formData, username: e.target.value})}
                    className="w-full px-4 py-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none"
                    required={mode === 'signup'}
                  />
                </div>
              )}

              <div>
                <input
                  type="email"
                  placeholder="Email"
                  value={formData.email}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                  className="w-full px-4 py-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none"
                  required
                />
              </div>

              <div>
                <input
                  type="password"
                  placeholder="Password"
                  value={formData.password}
                  onChange={(e) => setFormData({...formData, password: e.target.value})}
                  className="w-full px-4 py-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-orange-500 hover:bg-orange-600 text-white font-semibold py-3 px-4 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin mr-2" />
                    {mode === 'signup' ? 'Signing up...' : 'Logging in...'}
                  </>
                ) : (
                  mode === 'signup' ? 'Sign Up' : 'Log In'
                )}
              </button>

              <div className="text-center">
                <button
                  type="button"
                  onClick={() => {
                    setMode(mode === 'signup' ? 'signin' : 'signup')
                    setError(null)
                    setSuccess(null)
                  }}
                  className="text-sm text-gray-600 hover:text-gray-900"
                >
                  {mode === 'signup' ? 'Already have an account? Log In' : "Don't have an account? Sign Up"}
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* Right Side - Illustration */}
        <div className="flex-1 flex items-center justify-center">
          <img 
            src="/lawyer_ly_icon.png" 
            alt="Legal AI Illustration" 
            className="w-full max-w-lg h-auto"
            style={{ maxHeight: '600px', objectFit: 'contain' }}
          />
        </div>
      </div>
    </div>
  )
}

export default ExactLandingPage
