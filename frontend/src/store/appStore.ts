import { create } from 'zustand'
import { devtools } from 'zustand/middleware'

export type QueryMode = 'qa' | 'drafting' | 'summarization'

export interface Message {
  id: string
  type: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  timestamp: Date
  isLoading?: boolean
}

export interface Citation {
  id: string
  text: string
  source: string
  page?: number
  confidence: number
  chunkId: string
}

export interface Conversation {
  id: string
  title: string
  messages: Message[]
  createdAt: Date
  updatedAt: Date
}

export interface Document {
  id: string
  filename: string
  fileType: string
  fileSize: number
  uploadDate: Date
  processingStatus: 'pending' | 'processing' | 'completed' | 'failed'
  progress?: number
  chunkCount?: number
  error?: string
}

export interface User {
  id: string
  email: string
  name: string
  role: string
}

interface AppState {
  // User state
  user: User | null
  isAuthenticated: boolean
  
  // UI state
  mode: QueryMode
  sidebarOpen: boolean
  
  // Chat state
  currentConversation: Conversation | null
  conversations: Conversation[]
  isLoading: boolean
  
  // Document state
  documents: Document[]
  selectedDocument: Document | null
  
  // Citation state
  selectedCitation: Citation | null
  citationModalOpen: boolean
  
  // Actions
  setUser: (user: User | null) => void
  setMode: (mode: QueryMode) => void
  setSidebarOpen: (open: boolean) => void
  
  // Chat actions
  createConversation: () => void
  setCurrentConversation: (conversation: Conversation | null) => void
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void
  updateMessage: (messageId: string, updates: Partial<Message>) => void
  clearConversation: () => void
  
  // Document actions
  addDocument: (document: Document) => void
  updateDocument: (documentId: string, updates: Partial<Document>) => void
  removeDocument: (documentId: string) => void
  setSelectedDocument: (document: Document | null) => void
  
  // Citation actions
  setSelectedCitation: (citation: Citation | null) => void
  setCitationModalOpen: (open: boolean) => void
}

export const useAppStore = create<AppState>()(
  devtools(
    (set) => ({
      // Initial state
      user: null,
      isAuthenticated: false,
      mode: 'qa',
      sidebarOpen: true,
      currentConversation: null,
      conversations: [],
      isLoading: false,
      documents: [],
      selectedDocument: null,
      selectedCitation: null,
      citationModalOpen: false,
      
      // User actions
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      
      // UI actions
      setMode: (mode) => set({ mode }),
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
      
      // Chat actions
      createConversation: () => {
        const newConversation: Conversation = {
          id: `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          title: 'New Conversation',
          messages: [],
          createdAt: new Date(),
          updatedAt: new Date()
        }
        set((state) => ({
          currentConversation: newConversation,
          conversations: [newConversation, ...state.conversations]
        }))
      },
      
      setCurrentConversation: (conversation) => set({ currentConversation: conversation }),
      
      addMessage: (messageData) => {
        const message: Message = {
          ...messageData,
          id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          timestamp: new Date()
        }
        
        set((state) => {
          if (!state.currentConversation) {
            // Create new conversation if none exists
            const newConversation: Conversation = {
              id: `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              title: messageData.type === 'user' ? messageData.content.slice(0, 50) + '...' : 'New Conversation',
              messages: [message],
              createdAt: new Date(),
              updatedAt: new Date()
            }
            return {
              currentConversation: newConversation,
              conversations: [newConversation, ...state.conversations]
            }
          }
          
          const updatedConversation = {
            ...state.currentConversation,
            messages: [...state.currentConversation.messages, message],
            updatedAt: new Date()
          }
          
          return {
            currentConversation: updatedConversation,
            conversations: state.conversations.map(conv => 
              conv.id === updatedConversation.id ? updatedConversation : conv
            )
          }
        })
      },
      
      updateMessage: (messageId, updates) => {
        set((state) => {
          if (!state.currentConversation) return state
          
          const updatedConversation = {
            ...state.currentConversation,
            messages: state.currentConversation.messages.map(msg =>
              msg.id === messageId ? { ...msg, ...updates } : msg
            ),
            updatedAt: new Date()
          }
          
          return {
            currentConversation: updatedConversation,
            conversations: state.conversations.map(conv =>
              conv.id === updatedConversation.id ? updatedConversation : conv
            )
          }
        })
      },
      
      clearConversation: () => {
        set((state) => ({
          currentConversation: state.currentConversation ? {
            ...state.currentConversation,
            messages: [],
            updatedAt: new Date()
          } : null
        }))
      },
      
      // Document actions
      addDocument: (document) => {
        set((state) => ({
          documents: [document, ...state.documents]
        }))
      },
      
      updateDocument: (documentId, updates) => {
        set((state) => ({
          documents: state.documents.map(doc =>
            doc.id === documentId ? { ...doc, ...updates } : doc
          )
        }))
      },
      
      removeDocument: (documentId) => {
        set((state) => ({
          documents: state.documents.filter(doc => doc.id !== documentId),
          selectedDocument: state.selectedDocument?.id === documentId ? null : state.selectedDocument
        }))
      },
      
      setSelectedDocument: (document) => set({ selectedDocument: document }),
      
      // Citation actions
      setSelectedCitation: (citation) => set({ selectedCitation: citation }),
      setCitationModalOpen: (open) => set({ citationModalOpen: open })
    }),
    {
      name: 'indian-legal-ai-store'
    }
  )
)