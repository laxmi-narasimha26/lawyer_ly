import React, { useState } from 'react'
import { Scale, Loader2, AlertCircle, Shield, Users, Zap } from 'lucide-react'
import { useAuth } from './AuthProvider'
import Galaxy from './Galaxy'

const LoginPage: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isSignup, setIsSignup] = useState(false)
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

    try {
      const { authApi } = await import('../services/api')
      
      if (isSignup) {
        // Register new user
        const response = await authApi.register(formData.username, formData.email, formData.password)
        localStorage.setItem('auth_token', response.access_token)
        localStorage.setItem('user_id', response.user.id)
        await login(response.access_token)
      } else {
        // Login existing user
        const response = await authApi.login(formData.email, formData.password)
        localStorage.setItem('auth_token', response.access_token)
        localStorage.setItem('user_id', response.user.id)
        await login(response.access_token)
      }
      
    } catch (error: any) {
      setError(error.response?.data?.detail || (isSignup ? 'Signup failed. Please try again.' : 'Login failed. Please check your credentials.'))
    } finally {
      setIsLoading(false)
    }
  }

  const handleGuestLogin = async () => {
    setIsLoading(true)
    setError(null)

    try {
      // Use demo credentials
      const { authApi } = await import('../services/api')
      const response = await authApi.register('guest_' + Date.now(), 'guest_' + Date.now() + '@lawyer.ly', 'guest123')
      localStorage.setItem('auth_token', response.access_token)
      localStorage.setItem('user_id', response.user.id)
      await login(response.access_token)
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Guest login failed. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen relative flex items-center justify-center p-4">
      {/* Galaxy Background */}
      <div className="absolute inset-0 z-0">
        <Galaxy
          mouseRepulsion={true}
          mouseInteraction={true}
          density={1.5}
          glowIntensity={0.5}
          saturation={0.6}
          hueShift={240}
          twinkleIntensity={0.4}
          rotationSpeed={0.05}
          transparent={false}
        />
      </div>
      
      {/* Content */}
      <div className="max-w-md w-full space-y-8 relative z-10">
        {/* Header */}
        <div className="text-center">
          <div className="mx-auto h-16 w-16 bg-blue-600 rounded-full flex items-center justify-center shadow-lg">
            <Scale className="h-8 w-8 text-white" />
          </div>
          <h2 className="mt-6 text-3xl font-bold text-white drop-shadow-lg">
            Indian Legal AI Assistant
          </h2>
          <p className="mt-2 text-sm text-gray-200 drop-shadow">
            Your intelligent legal research companion
          </p>
        </div>

        {/* Features */}
        <div className="bg-white/90 backdrop-blur-md rounded-lg shadow-xl p-6 space-y-4 border border-white/20">
          <h3 className="text-lg font-semibold text-gray-900 text-center mb-4">
            What you can do:
          </h3>
          <div className="space-y-3">
            <div className="flex items-center space-x-3">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                <Zap className="w-4 h-4 text-blue-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Ask Legal Questions</p>
                <p className="text-xs text-gray-600">Get accurate answers with citations to Indian law</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <div className="flex-shrink-0 w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                <Users className="w-4 h-4 text-green-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Draft Legal Documents</p>
                <p className="text-xs text-gray-600">Get help with contracts, notices, and legal writing</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <div className="flex-shrink-0 w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center">
                <Shield className="w-4 h-4 text-purple-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Analyze Documents</p>
                <p className="text-xs text-gray-600">Upload and get summaries of legal documents</p>
              </div>
            </div>
          </div>
        </div>

        {/* Login Form */}
        <div className="bg-white/90 backdrop-blur-md rounded-lg shadow-xl p-6 border border-white/20">
          <div className="mb-4 flex justify-center space-x-4">
            <button
              onClick={() => setIsSignup(false)}
              className={`px-4 py-2 text-sm font-medium rounded-md ${!isSignup ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'}`}
            >
              Login
            </button>
            <button
              onClick={() => setIsSignup(true)}
              className={`px-4 py-2 text-sm font-medium rounded-md ${isSignup ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'}`}
            >
              Sign Up
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-md p-3">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 text-red-400" />
                  <div className="ml-3">
                    <p className="text-sm text-red-800">{error}</p>
                  </div>
                </div>
              </div>
            )}

            {isSignup && (
              <div>
                <label htmlFor="username" className="block text-sm font-medium text-gray-700">
                  Username
                </label>
                <input
                  type="text"
                  id="username"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  required={isSignup}
                />
              </div>
            )}

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                type="email"
                id="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                required
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Password
              </label>
              <input
                type="password"
                id="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                required
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex justify-center items-center px-4 py-3 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : null}
              {isSignup ? 'Create Account' : 'Sign In'}
            </button>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-gray-500">Or</span>
              </div>
            </div>

            {/* Guest Login */}
            <button
              type="button"
              onClick={handleGuestLogin}
              disabled={isLoading}
              className="w-full flex justify-center items-center px-4 py-3 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Users className="w-4 h-4 mr-2" />
              )}
              Continue as Guest
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-xs text-gray-500">
              By signing in, you agree to our{' '}
              <a href="#" className="text-blue-600 hover:text-blue-500">
                Terms of Service
              </a>{' '}
              and{' '}
              <a href="#" className="text-blue-600 hover:text-blue-500">
                Privacy Policy
              </a>
            </p>
          </div>
        </div>

        {/* Security Notice */}
        <div className="bg-green-50/90 backdrop-blur-md border border-green-200 rounded-lg p-4 shadow-lg">
          <div className="flex">
            <Shield className="h-5 w-5 text-green-400" />
            <div className="ml-3">
              <h3 className="text-sm font-medium text-green-800">
                Secure & Private
              </h3>
              <div className="mt-2 text-sm text-green-700">
                <p>
                  Your data is encrypted and stored securely in India. We don't use your information to train AI models.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center text-xs text-gray-200 drop-shadow">
          <p>© 2024 Indian Legal AI Assistant. All rights reserved.</p>
        </div>
      </div>
    </div>
  )
}

export default LoginPage