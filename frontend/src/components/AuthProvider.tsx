import React, { createContext, useContext, useEffect, useState } from 'react'
import { useAppStore } from '../store/appStore'
import { authApi } from '../services/api'

interface AuthContextType {
  isLoading: boolean
  login: (token: string) => Promise<void>
  logout: () => Promise<void>
  refreshToken: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

interface AuthProviderProps {
  children: React.ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [isLoading, setIsLoading] = useState(true)
  const { setUser } = useAppStore()

  useEffect(() => {
    // Check for existing token on app start
    const token = localStorage.getItem('auth_token')
    if (token) {
      validateToken()
    } else {
      setIsLoading(false)
    }
  }, [])

  const validateToken = async () => {
    try {
      const response = await authApi.getProfile()
      setUser(response.user)
    } catch (error) {
      console.error('Token validation failed:', error)
      localStorage.removeItem('auth_token')
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (token: string) => {
    try {
      setIsLoading(true)
      localStorage.setItem('auth_token', token)
      // Token is already set, just validate and get user info
      const response = await authApi.getProfile()
      setUser(response.user)
      // Store user_id for API calls
      localStorage.setItem('user_id', response.user?.id || 'demo_user')
    } catch (error) {
      localStorage.removeItem('auth_token')
      setUser(null)
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const logout = async () => {
    try {
      await authApi.logout()
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      localStorage.removeItem('auth_token')
      setUser(null)
    }
  }

  const refreshToken = async () => {
    try {
      const response = await authApi.getProfile()
      setUser(response.user)
    } catch (error) {
      console.error('Token refresh failed:', error)
      await logout()
    }
  }

  const value: AuthContextType = {
    isLoading,
    login,
    logout,
    refreshToken
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}