import axios from 'axios'
import { QueryMode, Message, Citation, Document } from '../store/appStore'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export interface QueryRequest {
  query: string
  mode: QueryMode
  conversationId?: string
  documentId?: string
}

export interface QueryResponse {
  answer: string
  citations: Citation[]
  queryId: string
  processingTime: number
}

export interface DocumentUploadResponse {
  documentId: string
  status: string
  message: string
}

export interface DocumentStatusResponse {
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  chunkCount?: number
  error?: string
}

export interface CitationDetailsResponse {
  sourceText: string
  metadata: Record<string, any>
  context: string
}

// Chat API
export const chatApi = {
  async sendQuery(request: QueryRequest): Promise<QueryResponse> {
    const payload = {
      message: request.query,
      conversation_id: request.conversationId,
      mode: request.mode,
      user_id: localStorage.getItem('user_id') || 'demo_user',
      include_context: true,
      max_context_messages: 10
    }
    
    const response = await api.post('/chat/query', payload)
    
    // Transform response to match expected format
    return {
      answer: response.data.response,
      citations: response.data.citations || [],
      queryId: response.data.message_id,
      processingTime: response.data.processing_time
    }
  },

  async getConversationHistory(conversationId: string): Promise<Message[]> {
    const response = await api.get(`/chat/conversations/${conversationId}/history`)
    return response.data.messages
  },

  async getConversations(userId: string = 'demo_user', limit: number = 20): Promise<any> {
    const response = await api.get(`/chat/conversations?user_id=${userId}&limit=${limit}`)
    return response.data
  },

  async createConversation(userId: string = 'demo_user', title?: string): Promise<any> {
    const response = await api.post('/chat/conversations/new', { user_id: userId, title })
    return response.data
  },

  async deleteConversation(conversationId: string): Promise<void> {
    await api.delete(`/chat/conversations/${conversationId}`)
  }
}

// Document API
export const documentApi = {
  async uploadDocument(file: File, onProgress?: (progress: number) => void): Promise<DocumentUploadResponse> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await api.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(progress)
        }
      }
    })

    return response.data
  },

  async getDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
    const response = await api.get(`/documents/${documentId}/status`)
    return response.data
  },

  async queryDocument(documentId: string, query: string): Promise<QueryResponse> {
    const response = await api.post(`/documents/${documentId}/query`, { query })
    return response.data
  },

  async getDocuments(): Promise<Document[]> {
    const response = await api.get('/documents')
    return response.data.documents
  },

  async deleteDocument(documentId: string): Promise<void> {
    await api.delete(`/documents/${documentId}`)
  }
}

// Citation API
export const citationApi = {
  async getCitationDetails(citationId: string): Promise<CitationDetailsResponse> {
    const response = await api.get(`/citations/${citationId}`)
    return response.data
  }
}

// Auth API
export const authApi = {
  async login(token: string): Promise<{ user: any }> {
    const response = await api.post('/auth/login', { token })
    return response.data
  },

  async logout(): Promise<void> {
    await api.post('/auth/logout')
    localStorage.removeItem('auth_token')
  },

  async getProfile(): Promise<{ user: any }> {
    const response = await api.get('/auth/profile')
    return response.data
  }
}

export default api