import React, { useState } from 'react'
import { Scale, Loader2, AlertCircle, Shield, Users, Zap } from 'lucide-react'
import { useAuth } from './AuthProvider'

const LoginPage: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { login } = useAuth()

  const handleAzureLogin = async () => {
    setIsLoading(true)
    setError(null)

    try {
      // In a real implementation, this would redirect to Azure AD
      // For now, we'll simulate the login process
      
      // This would typically be handled by Azure AD SDK
      // const token = await acquireTokenSilent() or acquireTokenPopup()
      
      // Simulate Azure AD login
      const mockToken = 'mock-azure-ad-token-' + Date.now()
      await login(mockToken)
      
    } catch (error: any) {
      setError(error.response?.data?.message || 'Login failed. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleGuestLogin = async () => {
    setIsLoading(true)
    setError(null)

    try {
      // Create a guest session
      const guestToken = 'guest-token-' + Date.now()
      await login(guestToken)
    } catch (error: any) {
      setError(error.response?.data?.message || 'Guest login failed. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="max-w-md w-full space-y-8">
        {/* Header */}
        <div className="text-center">
          <div className="mx-auto h-16 w-16 bg-blue-600 rounded-full flex items-center justify-center">
            <Scale className="h-8 w-8 text-white" />
          </div>
          <h2 className="mt-6 text-3xl font-bold text-gray-900">
            Indian Legal AI Assistant
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Your intelligent legal research companion
          </p>
        </div>

        {/* Features */}
        <div className="bg-white rounded-lg shadow-md p-6 space-y-4">
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
        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="space-y-4">
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

            {/* Azure AD Login */}
            <button
              onClick={handleAzureLogin}
              disabled={isLoading}
              className="w-full flex justify-center items-center px-4 py-3 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M11.4 24H0V12.6h11.4V24zM24 24H12.6V12.6H24V24zM11.4 11.4H0V0h11.4v11.4zM24 11.4H12.6V0H24v11.4z"/>
                </svg>
              )}
              Sign in with Microsoft
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
          </div>

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
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
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
        <div className="text-center text-xs text-gray-500">
          <p>© 2024 Indian Legal AI Assistant. All rights reserved.</p>
        </div>
      </div>
    </div>
  )
}

export default LoginPage