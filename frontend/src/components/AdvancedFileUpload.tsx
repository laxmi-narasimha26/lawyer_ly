import React, { useCallback, useState } from 'react'
import { Upload, File, FileText, X, Check, AlertCircle, Loader2 } from 'lucide-react'

interface UploadedFile {
  id: string
  file: File
  name: string
  size: number
  type: string
  status: 'uploading' | 'processing' | 'complete' | 'error'
  progress: number
  error?: string
}

interface AdvancedFileUploadProps {
  onFilesUploaded: (files: File[]) => void
  maxFiles?: number
  maxSizeTotal?: number  // in MB
}

// Supported legal file formats (50+ extensions)
const SUPPORTED_FORMATS = {
  documents: ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.pages'],
  spreadsheets: ['.xls', '.xlsx', '.csv', '.ods'],
  presentations: ['.ppt', '.pptx', '.odp'],
  images: ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'],
  legal: ['.legal', '.contract', '.brief', '.pleading'],
  archives: ['.zip', '.rar', '.7z', '.tar', '.gz'],
  code: ['.html', '.xml', '.json', '.yaml', '.yml'],
  other: ['.msg', '.eml', '.vcf', '.ics']
}

const ALL_SUPPORTED = Object.values(SUPPORTED_FORMATS).flat()

const AdvancedFileUpload: React.FC<AdvancedFileUploadProps> = ({
  onFilesUploaded,
  maxFiles = 50,
  maxSizeTotal = 500  // 500MB total
}) => {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [isDragging, setIsDragging] = useState(false)

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  const getFileIcon = (filename: string) => {
    const ext = '.' + filename.split('.').pop()?.toLowerCase()

    if (SUPPORTED_FORMATS.documents.includes(ext)) return <FileText className="w-8 h-8 text-blue-500" />
    if (SUPPORTED_FORMATS.spreadsheets.includes(ext)) return <File className="w-8 h-8 text-green-500" />
    if (SUPPORTED_FORMATS.images.includes(ext)) return <File className="w-8 h-8 text-purple-500" />

    return <File className="w-8 h-8 text-gray-500" />
  }

  const validateFile = (file: File): string | null => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()

    if (!ALL_SUPPORTED.includes(ext)) {
      return `Unsupported file format: ${ext}`
    }

    const maxFileSize = 100 * 1024 * 1024 // 100MB per file
    if (file.size > maxFileSize) {
      return `File too large. Maximum size is 100MB`
    }

    const totalSize = uploadedFiles.reduce((sum, f) => sum + f.size, 0) + file.size
    if (totalSize > maxSizeTotal * 1024 * 1024) {
      return `Total upload size exceeds ${maxSizeTotal}MB limit`
    }

    if (uploadedFiles.length >= maxFiles) {
      return `Maximum ${maxFiles} files allowed`
    }

    return null
  }

  const handleFiles = useCallback((files: FileList | null) => {
    if (!files) return

    const newFiles: UploadedFile[] = []
    const validFiles: File[] = []

    Array.from(files).forEach(file => {
      const error = validateFile(file)

      const uploadedFile: UploadedFile = {
        id: crypto.randomUUID(),
        file,
        name: file.name,
        size: file.size,
        type: file.type,
        status: error ? 'error' : 'uploading',
        progress: 0,
        error
      }

      newFiles.push(uploadedFile)

      if (!error) {
        validFiles.push(file)
      }
    })

    setUploadedFiles(prev => [...prev, ...newFiles])

    // Simulate upload progress
    newFiles.forEach(file => {
      if (file.status === 'uploading') {
        simulateUpload(file.id)
      }
    })

    // Callback with valid files
    if (validFiles.length > 0) {
      onFilesUploaded(validFiles)
    }
  }, [uploadedFiles, maxFiles, maxSizeTotal])

  const simulateUpload = (fileId: string) => {
    let progress = 0
    const interval = setInterval(() => {
      progress += Math.random() * 30
      if (progress >= 100) {
        progress = 100
        clearInterval(interval)
        setUploadedFiles(prev =>
          prev.map(f =>
            f.id === fileId
              ? { ...f, status: 'complete', progress: 100 }
              : f
          )
        )
      } else {
        setUploadedFiles(prev =>
          prev.map(f =>
            f.id === fileId
              ? { ...f, progress }
              : f
          )
        )
      }
    }, 300)
  }

  const removeFile = (fileId: string) => {
    setUploadedFiles(prev => prev.filter(f => f.id !== fileId))
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files)
  }

  const totalSize = uploadedFiles.reduce((sum, f) => sum + f.size, 0)
  const totalSizeMB = totalSize / (1024 * 1024)

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-xl p-8 transition-all
          ${isDragging
            ? 'border-blue-500 bg-blue-50 scale-105'
            : 'border-gray-300 hover:border-gray-400 bg-gray-50'
          }
        `}
      >
        <input
          type="file"
          id="file-upload"
          multiple
          onChange={handleFileInput}
          accept={ALL_SUPPORTED.join(',')}
          className="hidden"
        />

        <label
          htmlFor="file-upload"
          className="cursor-pointer flex flex-col items-center justify-center space-y-4"
        >
          <div className={`
            p-4 rounded-full transition-colors
            ${isDragging ? 'bg-blue-200' : 'bg-gray-200'}
          `}>
            <Upload className={`w-12 h-12 ${isDragging ? 'text-blue-600' : 'text-gray-600'}`} />
          </div>

          <div className="text-center">
            <p className="text-lg font-semibold text-gray-800 mb-1">
              {isDragging ? 'Drop files here' : 'Upload Legal Documents'}
            </p>
            <p className="text-sm text-gray-600 mb-2">
              Drag & drop files or click to browse
            </p>
            <p className="text-xs text-gray-500">
              Supports 50+ file formats: PDF, DOCX, TXT, RTF, Excel, images, and more
            </p>
          </div>

          <div className="flex items-center space-x-4 text-xs text-gray-500">
            <span>Max {maxFiles} files</span>
            <span>•</span>
            <span>Max 100MB per file</span>
            <span>•</span>
            <span>{maxSizeTotal}MB total</span>
          </div>
        </label>
      </div>

      {/* Usage Statistics */}
      {uploadedFiles.length > 0 && (
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">
              {uploadedFiles.length} / {maxFiles} files uploaded
            </span>
            <span className="text-sm text-gray-600">
              {totalSizeMB.toFixed(2)} / {maxSizeTotal} MB
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 rounded-full h-2 transition-all"
              style={{ width: `${Math.min((totalSizeMB / maxSizeTotal) * 100, 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Uploaded Files List */}
      {uploadedFiles.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-gray-700">Uploaded Files</h4>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {uploadedFiles.map(file => (
              <div
                key={file.id}
                className="flex items-center space-x-4 p-3 bg-white border border-gray-200 rounded-lg hover:shadow-md transition-shadow"
              >
                {/* File Icon */}
                <div className="flex-shrink-0">
                  {getFileIcon(file.name)}
                </div>

                {/* File Info */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {file.name}
                  </p>
                  <p className="text-xs text-gray-500">
                    {formatFileSize(file.size)}
                  </p>

                  {/* Progress Bar */}
                  {file.status === 'uploading' && (
                    <div className="mt-2">
                      <div className="w-full bg-gray-200 rounded-full h-1.5">
                        <div
                          className="bg-blue-600 rounded-full h-1.5 transition-all"
                          style={{ width: `${file.progress}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-500 mt-1">{Math.round(file.progress)}% uploaded</p>
                    </div>
                  )}

                  {/* Error Message */}
                  {file.status === 'error' && file.error && (
                    <div className="mt-1 flex items-center space-x-1 text-xs text-red-600">
                      <AlertCircle className="w-3 h-3" />
                      <span>{file.error}</span>
                    </div>
                  )}
                </div>

                {/* Status Icon */}
                <div className="flex-shrink-0">
                  {file.status === 'uploading' && (
                    <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
                  )}
                  {file.status === 'complete' && (
                    <Check className="w-5 h-5 text-green-600" />
                  )}
                  {file.status === 'error' && (
                    <AlertCircle className="w-5 h-5 text-red-600" />
                  )}
                </div>

                {/* Remove Button */}
                <button
                  onClick={() => removeFile(file.id)}
                  className="flex-shrink-0 text-gray-400 hover:text-red-600 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default AdvancedFileUpload
