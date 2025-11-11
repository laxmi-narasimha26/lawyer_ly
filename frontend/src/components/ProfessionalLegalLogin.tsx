import React, { useState } from 'react'
import { Scale, Loader2, AlertCircle, CheckCircle, BookOpen, Gavel, FileText } from 'lucide-react'
import { useAuth } from './AuthProvider'

const ProfessionalLegalLogin: React.FC = () => {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: ''
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
        // Validation
        if (formData.password !== formData.confirmPassword) {
          throw new Error('Passwords do not match')
        }
        if (formData.password.length < 6) {
          throw new Error('Password must be at least 6 characters')
        }
        if (!formData.username || !formData.email) {
          throw new Error('Please fill in all fields')
        }

        // Register
        const response = await authApi.register(formData.username, formData.email, formData.password)
        localStorage.setItem('auth_token', response.access_token)
        localStorage.setItem('user_id', response.user.id)
        setSuccess('Account created successfully! Logging you in...')
        
        setTimeout(async () => {
          await login(response.access_token)
        }, 1000)
        
      } else {
        // Login
        if (!formData.email || !formData.password) {
          throw new Error('Please enter email and password')
        }

        const response = await authApi.login(formData.email, formData.password)
        localStorage.setItem('auth_token', response.access_token)
        localStorage.setItem('user_id', response.user.id)
        setSuccess('Login successful! Redirecting...')
        
        setTimeout(async () => {
          await login(response.access_token)
        }, 1000)
      }
      
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Authentication failed. Please try again.'
      setError(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
    setError(null)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex">
      {/* Left Side - Branding & Features */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-indigo-900 via-blue-900 to-slate-900 p-12 flex-col justify-between relative overflow-hidden">
        {/* Background Pattern */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-0 left-0 w-full h-full" style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`
          }}></div>
        </div>

        {/* Content */}
        <div className="relative z-10">
          <div className="flex items-center space-x-3 mb-12">
            <div className="w-12 h-12 bg-white rounded-lg flex items-center justify-center">
              <Scale className="w-7 h-7 text-indigo-900" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Lawyer.ly</h1>
              <p className="text-sm text-indigo-200">Legal AI Assistant</p>
            </div>
          </div>

          <div className="space-y-8">
            <div>
              <h2 className="text-4xl font-bold text-white mb-4 leading-tight">
                Your Intelligent Legal Research Companion
              </h2>
              <p className="text-lg text-indigo-200">
                Powered by AI to help you navigate Indian law with confidence
              </p>
            </div>

            <div className="space-y-6">
              <div className="flex items-start space-x-4">
                <div className="w-10 h-10 bg-indigo-800 rounded-lg flex items-center justify-center flex-shrink-0">
                  <BookOpen className="w-5 h-5 text-indigo-200" />
                </div>
                <div>
                  <h3 className="text-white font-semibold mb-1">Comprehensive Legal Database</h3>
                  <p className="text-indigo-300 text-sm">Access IPC sections, case law, and legal precedents instantly</p>
                </div>
              </div>

              <div className="flex items-start space-x-4">
                <div className="w-10 h-10 bg-indigo-800 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Gavel className="w-5 h-5 text-indigo-200" />
                </div>
                <div>
                  <h3 className="text-white font-semibold mb-1">AI-Powered Analysis</h3>
                  <p className="text-indigo-300 text-sm">Get intelligent insights and legal interpretations</p>
                </div>
              </div>

              <div className="flex items-start space-x-4">
                <div className="w-10 h-10 bg-indigo-800 rounded-lg flex items-center justify-center flex-shrink-0">
                  <FileText className="w-5 h-5 text-indigo-200" />
                </div>
                <div>
                  <h3 className="text-white font-semibold mb-1">Document Drafting</h3>
                  <p className="text-indigo-300 text-sm">Generate legal documents and contracts efficiently</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="relative z-10">
          <p className="text-indigo-300 text-sm">
            Trusted by legal professionals across India
          </p>
        </div>
      </div>

      {/* Right Side - Auth Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center justify-center space-x-3 mb-8">
            <div className="w-10 h-10 bg-indigo-900 rounded-lg flex items-center justify-center">
              <Scale className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">Lawyer.ly</h1>
            </div>
          </div>

          {/* Mode Tabs */}
          <div className="flex space-x-2 mb-8 bg-gray-100 p-1 rounded-lg">
            <button
              onClick={() => {
                setMode('signin')
                setError(null)
                setSuccess(null)
              }}
              className={`flex-1 py-2.5 px-4 rounded-md font-medium transition-all ${
                mode === 'signin'
                  ? 'bg-white text-indigo-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => {
                setMode('signup')
                setError(null)
                setSuccess(null)
              }}
              className={`flex-1 py-2.5 px-4 rounded-md font-medium transition-all ${
                mode === 'signup'
                  ? 'bg-white text-indigo-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Sign Up
            </button>
          </div>

          {/* Welcome Text */}
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              {mode === 'signin' ? 'Welcome back' : 'Create your account'}
            </h2>
            <p className="text-gray-600">
              {mode === 'signin' 
                ? 'Sign in to access your legal research assistant' 
                : 'Join thousands of legal professionals using Lawyer.ly'}
            </p>
          </div>

          {/* Alerts */}
          {error && (
            <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
              <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 mr-3 flex-shrink-0" />
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          {success && (
            <div className="mb-6 bg-green-50 border border-green-200 rounded-lg p-4 flex items-start">
              <CheckCircle className="h-5 w-5 text-green-500 mt-0.5 mr-3 flex-shrink-0" />
              <p className="text-sm text-green-800">{success}</p>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {mode === 'signup' && (
              <div>
                <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-2">
                  Username
                </label>
                <input
                  type="text"
                  id="username"
                  name="username"
                  value={formData.username}
                  onChange={handleInputChange}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-all"
                  placeholder="Choose a username"
                  required={mode === 'signup'}
                />
              </div>
            )}

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                Email Address
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-all"
                placeholder="you@example.com"
                required
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                Password
              </label>
              <input
                type="password"
                id="password"
                name="password"
                value={formData.password}
                onChange={handleInputChange}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-all"
                placeholder={mode === 'signup' ? 'Create a strong password' : 'Enter your password'}
                required
              />
            </div>

            {mode === 'signup' && (
              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-2">
                  Confirm Password
                </label>
                <input
                  type="password"
                  id="confirmPassword"
                  name="confirmPassword"
                  value={formData.confirmPassword}
                  onChange={handleInputChange}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-all"
                  placeholder="Confirm your password"
                  required={mode === 'signup'}
                />
              </div>
            )}

            {mode === 'signin' && (
              <div className="flex items-center justify-between text-sm">
                <label className="flex items-center">
                  <input type="checkbox" className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" />
                  <span className="ml-2 text-gray-600">Remember me</span>
                </label>
                <a href="#" className="text-indigo-600 hover:text-indigo-700 font-medium">
                  Forgot password?
                </a>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-indigo-600 text-white py-3 px-4 rounded-lg font-semibold hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center shadow-lg shadow-indigo-500/30"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                  {mode === 'signin' ? 'Signing in...' : 'Creating account...'}
                </>
              ) : (
                mode === 'signin' ? 'Sign In' : 'Create Account'
              )}
            </button>
          </form>

          {/* Terms */}
          <p className="mt-6 text-xs text-gray-500 text-center">
            By continuing, you agree to our{' '}
            <a href="#" className="text-indigo-600 hover:text-indigo-700 font-medium">Terms of Service</a>
            {' '}and{' '}
            <a href="#" className="text-indigo-600 hover:text-indigo-700 font-medium">Privacy Policy</a>
          </p>

          {/* Security Badge */}
          <div className="mt-8 flex items-center justify-center space-x-2 text-sm text-gray-500">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
            </svg>
            <span>Secured with 256-bit encryption</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ProfessionalLegalLogin
