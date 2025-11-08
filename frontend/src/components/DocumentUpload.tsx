import React, { useCallback, useState } from 'react'
import { Upload, File, X, AlertCircle, CheckCircle, Loader2 } from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { documentApi } from '../services/api'
import { useMutation } from '@tanstack/react-query'

interface FileWithProgress {
  file: File
  progress: number
  status: 'uploading' | 'processing' | 'completed' | 'error'
  error?: string
  documentId?: string
}

const DocumentUpload: React.FC = () => {
  const [dragActive, setDragActive] = useState(false)
  const [uploadingFiles, setUploadingFiles] = useState<FileWithProgress[]>([])
  const { addDocument, updateDocument } = useAppStore()

  const uploadMutation = useMutation({
    mutationFn: async ({ file, onProgress }: { file: File; onProgress: (progress: number) => void }) => {
      return await documentApi.uploadDocument(file, onProgress)
    }
  })

  const validateFile = (file: File): string | null => {
    const maxSize = 50 * 1024 * 1024 // 50MB
    const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
    
    if (file.size > maxSize) {
      return 'File size must be less than 50MB'
    }
    
    if (!allowedTypes.includes(file.type)) {
      return 'Only PDF, DOCX, and TXT files are supported'
    }
    
    return null
  }

  const processFiles = useCallback(async (files: FileList) => {
    const validFiles: File[] = []
    const errors: string[] = []

    Array.from(files).forEach(file => {
      const error = validateFile(file)
      if (error) {
        errors.push(`${file.name}: ${error}`)
      } else {
        validFiles.push(file)
      }
    })

    if (errors.length > 0) {
      alert('Some files could not be uploaded:\n' + errors.join('\n'))
    }

    // Process valid files
    for (const file of validFiles) {
      const fileWithProgress: FileWithProgress = {
        file,
        progress: 0,
        status: 'uploading'
      }

      setUploadingFiles(prev => [...prev, fileWithProgress])

      try {
        const response = await uploadMutation.mutateAsync({
          file,
          onProgress: (progress) => {
            setUploadingFiles(prev => 
              prev.map(f => 
                f.file === file ? { ...f, progress } : f
              )
            )
          }
        })

        // Update file status to processing
        setUploadingFiles(prev => 
          prev.map(f => 
            f.file === file 
              ? { ...f, status: 'processing', documentId: response.documentId, progress: 100 }
              : f
          )
        )

        // Add document to store
        const document = {
          id: response.documentId,
          filename: file.name,
          fileType: file.type,
          fileSize: file.size,
          uploadDate: new Date(),
          processingStatus: 'processing' as const,
          progress: 0
        }
        addDocument(document)

        // Poll for processing status
        pollDocumentStatus(response.documentId)

      } catch (error: any) {
        setUploadingFiles(prev => 
          prev.map(f => 
            f.file === file 
              ? { ...f, status: 'error', error: error.response?.data?.message || 'Upload failed' }
              : f
          )
        )
      }
    }
  }, [uploadMutation, addDocument])

  const pollDocumentStatus = async (documentId: string) => {
    const maxAttempts = 60 // 5 minutes with 5-second intervals
    let attempts = 0

    const poll = async () => {
      try {
        const status = await documentApi.getDocumentStatus(documentId)
        
        updateDocument(documentId, {
          processingStatus: status.status,
          progress: status.progress,
          chunkCount: status.chunkCount,
          error: status.error
        })

        if (status.status === 'completed') {
          setUploadingFiles(prev => 
            prev.map(f => 
              f.documentId === documentId 
                ? { ...f, status: 'completed' }
                : f
            )
          )
          
          // Remove from uploading files after 3 seconds
          setTimeout(() => {
            setUploadingFiles(prev => prev.filter(f => f.documentId !== documentId))
          }, 3000)
          
        } else if (status.status === 'failed') {
          setUploadingFiles(prev => 
            prev.map(f => 
              f.documentId === documentId 
                ? { ...f, status: 'error', error: status.error || 'Processing failed' }
                : f
            )
          )
        } else if (attempts < maxAttempts) {
          attempts++
          setTimeout(poll, 5000) // Poll every 5 seconds
        } else {
          // Timeout
          setUploadingFiles(prev => 
            prev.map(f => 
              f.documentId === documentId 
                ? { ...f, status: 'error', error: 'Processing timeout' }
                : f
            )
          )
        }
      } catch (error) {
        console.error('Error polling document status:', error)
        if (attempts < maxAttempts) {
          attempts++
          setTimeout(poll, 5000)
        }
      }
    }

    poll()
  }

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFiles(e.dataTransfer.files)
    }
  }, [processFiles])

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processFiles(e.target.files)
      e.target.value = '' // Reset input
    }
  }, [processFiles])

  const removeUploadingFile = (file: File) => {
    setUploadingFiles(prev => prev.filter(f => f.file !== file))
  }

  const getStatusIcon = (status: FileWithProgress['status']) => {
    switch (status) {
      case 'uploading':
      case 'processing':
        return <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />
    }
  }

  const getStatusText = (fileWithProgress: FileWithProgress) => {
    switch (fileWithProgress.status) {
      case 'uploading':
        return `Uploading... ${fileWithProgress.progress}%`
      case 'processing':
        return 'Processing document...'
      case 'completed':
        return 'Upload complete!'
      case 'error':
        return fileWithProgress.error || 'Upload failed'
    }
  }

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          dragActive
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          multiple
          accept=".pdf,.docx,.txt"
          onChange={handleFileInput}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
        
        <div className="space-y-4">
          <div className="mx-auto w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center">
            <Upload className="w-6 h-6 text-gray-600" />
          </div>
          
          <div>
            <p className="text-lg font-medium text-gray-900">
              Drop files here or click to browse
            </p>
            <p className="text-sm text-gray-500 mt-1">
              Supports PDF, DOCX, and TXT files up to 50MB
            </p>
          </div>
          
          <button
            type="button"
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <Upload className="w-4 h-4 mr-2" />
            Choose Files
          </button>
        </div>
      </div>

      {/* Upload progress */}
      {uploadingFiles.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-900">Uploading Files</h4>
          {uploadingFiles.map((fileWithProgress, index) => (
            <div
              key={`${fileWithProgress.file.name}-${index}`}
              className="bg-white border border-gray-200 rounded-lg p-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3 flex-1 min-w-0">
                  <File className="w-5 h-5 text-gray-400 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {fileWithProgress.file.name}
                    </p>
                    <div className="flex items-center space-x-2 mt-1">
                      {getStatusIcon(fileWithProgress.status)}
                      <p className="text-xs text-gray-500">
                        {getStatusText(fileWithProgress)}
                      </p>
                    </div>
                  </div>
                </div>
                
                {fileWithProgress.status === 'error' && (
                  <button
                    onClick={() => removeUploadingFile(fileWithProgress.file)}
                    className="ml-3 text-gray-400 hover:text-gray-600"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
              
              {/* Progress bar */}
              {(fileWithProgress.status === 'uploading' || fileWithProgress.status === 'processing') && (
                <div className="mt-3">
                  <div className="bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                      style={{ 
                        width: fileWithProgress.status === 'processing' 
                          ? '100%' 
                          : `${fileWithProgress.progress}%` 
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default DocumentUpload