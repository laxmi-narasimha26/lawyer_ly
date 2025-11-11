import React, { useState } from 'react'
import { Loader2, AlertCircle } from 'lucide-react'
import { useAuth } from './AuthProvider'

const ClaudeStyleLogin: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { login } = useAuth()

  const handleContinue = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      const { authApi } = await import('../services/api')
      
      // Try to login first, if fails, register
      try {
        const response = await authApi.login(email, password)
        localStorage.setItem('auth_token', response.access_token)
        localStorage.setItem('user_id', response.user.id)
        await login(response.access_token)
      } catch (loginError: any) {
        // If login fails, try to register
        if (loginError.response?.status === 401) {
          const username = email.split('@')[0]
          const response = await authApi.register(username, email, password)
          localStorage.setItem('auth_token', response.access_token)
          localStorage.setItem('user_id', response.user.id)
          await login(response.access_token)
        } else {
          throw loginError
        }
      }
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Authentication failed. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-amber-50 to-orange-100 flex">
      {/* Left side - Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Logo/Title */}
          <div className="mb-12">
            <h1 className="text-5xl font-bold text-gray-900 mb-3" style={{ fontFamily: 'system-ui, -apple-system, sans-serif' }}>
              Impossible?
            </h1>
            <h1 className="text-5xl font-bold text-gray-900 mb-4" style={{ fontFamily: 'system-ui, -apple-system, sans-serif' }}>
              Possible.
            </h1>
            <p className="text-lg text-gray-600" style={{ fontFamily: 'system-ui, -apple-system, sans-serif' }}>
              The AI for problem solvers
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleContinue} className="space-y-4">
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
                <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 mr-3 flex-shrink-0" />
                <p className="text-sm text-red-800">{error}</p>
              </div>
            )}

            {/* Google Sign In Button */}
            <button
              type="button"
              className="w-full flex items-center justify-center px-4 py-3 border border-gray-300 rounded-lg shadow-sm bg-white hover:bg-gray-50 transition-colors"
            >
              <svg className="w-5 h-5 mr-3" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              <span className="text-sm font-medium text-gray-700">Continue with Google</span>
            </button>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-gradient-to-br from-orange-50 via-amber-50 to-orange-100 text-gray-500">OR</span>
              </div>
            </div>

            {/* Email Input */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                Enter your email
              </label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition-all"
                placeholder="name@example.com"
                required
              />
            </div>

            {/* Password Input */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                Password
              </label>
              <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition-all"
                placeholder="Enter your password"
                required
              />
            </div>

            {/* Continue Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-black text-white py-3 px-4 rounded-lg font-medium hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                  Continuing...
                </>
              ) : (
                'Continue with email'
              )}
            </button>
          </form>

          {/* Terms */}
          <p className="mt-6 text-xs text-gray-500 text-center">
            By continuing, you agree to Lawyer.ly's{' '}
            <a href="#" className="underline hover:text-gray-700">Consumer Terms</a> and{' '}
            <a href="#" className="underline hover:text-gray-700">Usage Policy</a>, and acknowledge their{' '}
            <a href="#" className="underline hover:text-gray-700">Privacy Policy</a>.
          </p>
        </div>
      </div>

      {/* Right side - Illustration */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-orange-400 via-orange-500 to-orange-600 items-center justify-center p-12 relative overflow-hidden">
        {/* Decorative elements */}
        <div className="absolute top-10 right-10 w-32 h-32 bg-orange-300 rounded-full opacity-20 blur-3xl"></div>
        <div className="absolute bottom-10 left-10 w-40 h-40 bg-orange-700 rounded-full opacity-20 blur-3xl"></div>
        
        {/* Illustration placeholder - Lady sitting on steps */}
        <div className="relative z-10 text-center">
          <div className="w-96 h-96 mx-auto mb-8 relative">
            {/* Simple illustration representation */}
            <div className="absolute inset-0 flex items-end justify-center">
              {/* Steps */}
              <div className="relative w-full h-3/4">
                <div className="absolute bottom-0 left-1/4 w-1/2 h-16 bg-orange-300 rounded-t-lg"></div>
                <div className="absolute bottom-16 left-1/3 w-1/3 h-16 bg-orange-200 rounded-t-lg"></div>
                <div className="absolute bottom-32 left-1/3 w-1/3 h-16 bg-orange-100 rounded-t-lg"></div>
                
                {/* Person sitting */}
                <div className="absolute bottom-32 left-1/2 transform -translate-x-1/2">
                  <div className="w-20 h-20 bg-amber-100 rounded-full mb-2"></div>
                  <div className="w-24 h-32 bg-green-600 rounded-lg"></div>
                </div>
              </div>
            </div>
            
            {/* Decorative dots */}
            <div className="absolute top-0 right-0">
              {[...Array(15)].map((_, i) => (
                <div
                  key={i}
                  className="inline-block w-2 h-2 bg-orange-300 rounded-full m-1 opacity-60"
                  style={{
                    transform: `translate(${(i % 5) * 12}px, ${Math.floor(i / 5) * 12}px)`
                  }}
                ></div>
              ))}
            </div>
          </div>
          
          <div className="text-white">
            <h2 className="text-3xl font-bold mb-4">Legal AI Assistant</h2>
            <p className="text-lg opacity-90">Your intelligent companion for Indian law</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ClaudeStyleLogin
