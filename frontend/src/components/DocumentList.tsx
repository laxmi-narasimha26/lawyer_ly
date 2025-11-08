import React, { useEffect } from 'react'
import { File, Trash2, Eye, Clock, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { documentApi } from '../services/api'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

const DocumentList: React.FC = () => {
  const { 
    documents, 
    selectedDocument, 
    setSelectedDocument, 
    updateDocument,
    removeDocument 
  } = useAppStore()
  
  const queryClient = useQueryClient()

  // Fetch documents from API
  const { data: fetchedDocuments, isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: documentApi.getDocuments,
    refetchInterval: 5000, // Refetch every 5 seconds to update processing status
  })

  // Update store when documents are fetched
  useEffect(() => {
    if (fetchedDocuments) {
      // Update existing documents or add new ones
      fetchedDocuments.forEach(doc => {
        const existingDoc = documents.find(d => d.id === doc.id)
        if (existingDoc) {
          updateDocument(doc.id, doc)
        } else {
          // This would be handled by the store's addDocument, but we need to sync
          // For now, we'll rely on the fetched data being the source of truth
        }
      })
    }
  }, [fetchedDocuments, documents, updateDocument])

  const deleteMutation = useMutation({
    mutationFn: documentApi.deleteDocument,
    onSuccess: (_, documentId) => {
      removeDocument(documentId)
      if (selectedDocument?.id === documentId) {
        setSelectedDocument(null)
      }
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (error: any) => {
      alert(error.response?.data?.message || 'Failed to delete document')
    }
  })

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const formatDate = (date: Date): string => {
    return new Intl.DateTimeFormat('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(new Date(date))
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
      case 'processing':
        return <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />
      default:
        return <Clock className="w-4 h-4 text-gray-400" />
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'pending':
        return 'Pending'
      case 'processing':
        return 'Processing'
      case 'completed':
        return 'Ready'
      case 'failed':
        return 'Failed'
      default:
        return 'Unknown'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
      case 'processing':
        return 'text-blue-600 bg-blue-50'
      case 'completed':
        return 'text-green-600 bg-green-50'
      case 'failed':
        return 'text-red-600 bg-red-50'
      default:
        return 'text-gray-600 bg-gray-50'
    }
  }

  const handleSelectDocument = (document: any) => {
    if (document.processingStatus === 'completed') {
      setSelectedDocument(selectedDocument?.id === document.id ? null : document)
    }
  }

  const handleDeleteDocument = (document: any, e: React.MouseEvent) => {
    e.stopPropagation()
    if (confirm(`Are you sure you want to delete "${document.filename}"?`)) {
      deleteMutation.mutate(document.id)
    }
  }

  const displayDocuments = fetchedDocuments || documents

  if (isLoading && documents.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
        <span className="ml-2 text-gray-500">Loading documents...</span>
      </div>
    )
  }

  if (displayDocuments.length === 0) {
    return (
      <div className="text-center py-8">
        <File className="w-12 h-12 text-gray-300 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">No documents uploaded</h3>
        <p className="text-gray-500">
          Upload your first document to start analyzing legal content.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-gray-900">
          Your Documents ({displayDocuments.length})
        </h3>
        {selectedDocument && (
          <div className="text-sm text-blue-600">
            Selected: {selectedDocument.filename}
          </div>
        )}
      </div>

      <div className="space-y-2">
        {displayDocuments.map((document) => (
          <div
            key={document.id}
            className={`border rounded-lg p-4 cursor-pointer transition-all hover:shadow-md ${
              selectedDocument?.id === document.id
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 bg-white hover:border-gray-300'
            } ${
              document.processingStatus !== 'completed' 
                ? 'opacity-75 cursor-not-allowed' 
                : ''
            }`}
            onClick={() => handleSelectDocument(document)}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-start space-x-3 flex-1 min-w-0">
                <File className="w-5 h-5 text-gray-400 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <h4 className="text-sm font-medium text-gray-900 truncate">
                      {document.filename}
                    </h4>
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(document.processingStatus)}`}>
                      {getStatusIcon(document.processingStatus)}
                      <span className="ml-1">{getStatusText(document.processingStatus)}</span>
                    </span>
                  </div>
                  
                  <div className="mt-1 flex items-center space-x-4 text-xs text-gray-500">
                    <span>{formatFileSize(document.fileSize)}</span>
                    <span>•</span>
                    <span>{formatDate(document.uploadDate)}</span>
                    {document.chunkCount && (
                      <>
                        <span>•</span>
                        <span>{document.chunkCount} chunks</span>
                      </>
                    )}
                  </div>

                  {document.processingStatus === 'processing' && document.progress !== undefined && (
                    <div className="mt-2">
                      <div className="bg-gray-200 rounded-full h-1.5">
                        <div
                          className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                          style={{ width: `${document.progress}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {document.processingStatus === 'failed' && document.error && (
                    <div className="mt-2 text-xs text-red-600">
                      Error: {document.error}
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-center space-x-2 ml-3">
                {document.processingStatus === 'completed' && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      // TODO: Implement document preview
                      alert('Document preview coming soon!')
                    }}
                    className="p-1 text-gray-400 hover:text-gray-600 rounded"
                    title="Preview document"
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                )}
                
                <button
                  onClick={(e) => handleDeleteDocument(document, e)}
                  disabled={deleteMutation.isPending}
                  className="p-1 text-gray-400 hover:text-red-600 rounded disabled:opacity-50"
                  title="Delete document"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {selectedDocument && selectedDocument.processingStatus === 'completed' && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="flex items-center space-x-2">
            <CheckCircle className="w-4 h-4 text-blue-600" />
            <span className="text-sm text-blue-800">
              <strong>{selectedDocument.filename}</strong> is selected for analysis. 
              Your questions will be answered using this document.
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

export default DocumentList