import React, { useState } from 'react'
import { Upload, List, X } from 'lucide-react'
import DocumentUpload from './DocumentUpload'
import DocumentList from './DocumentList'

interface DocumentManagerProps {
  isOpen: boolean
  onClose: () => void
}

const DocumentManager: React.FC<DocumentManagerProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'upload' | 'list'>('list')

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Document Manager</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => setActiveTab('list')}
            className={`flex items-center space-x-2 px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'list'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <List className="w-4 h-4" />
            <span>My Documents</span>
          </button>
          <button
            onClick={() => setActiveTab('upload')}
            className={`flex items-center space-x-2 px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'upload'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Upload className="w-4 h-4" />
            <span>Upload New</span>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'list' ? (
            <DocumentList />
          ) : (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Upload Documents</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Upload legal documents to analyze them with AI. Supported formats: PDF, DOCX, TXT (max 50MB each).
                </p>
              </div>
              <DocumentUpload />
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <div className="ml-3">
                    <h3 className="text-sm font-medium text-yellow-800">
                      Privacy Notice
                    </h3>
                    <div className="mt-2 text-sm text-yellow-700">
                      <p>
                        Your documents are encrypted and stored securely. They are only accessible to you and are not used for training AI models. 
                        Documents are processed to extract text and create searchable chunks for better AI responses.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 px-6 py-4 bg-gray-50">
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-500">
              {activeTab === 'list' 
                ? 'Select a document to analyze it in your conversations'
                : 'After upload, documents will be processed and available for analysis'
              }
            </div>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DocumentManager