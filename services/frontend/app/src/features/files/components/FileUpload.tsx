import React, { useCallback, useState } from 'react';
import { Upload, X, FileIcon, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { useFileUpload, UploadingFile } from '../hooks/useFileUpload';
import { cn } from '../../../shared/utils/cn';

interface FileUploadProps {
  bucketId: string;
  maxFileSize?: number;
  acceptedFileTypes?: string[];
  multiple?: boolean;
  onUploadComplete?: (files: File[]) => void;
  className?: string;
}

export function FileUpload({
  bucketId,
  maxFileSize = 10 * 1024 * 1024, // 10MB default
  acceptedFileTypes,
  multiple = true,
  onUploadComplete,
  className,
}: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);

  const {
    uploadFiles,
    uploadingFiles,
    isUploading,
    removeFile,
    clearCompleted,
    retryFile,
  } = useFileUpload({
    bucketId,
    maxFileSize,
    acceptedFileTypes,
    onAllUploadsComplete: onUploadComplete,
  });

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      const files = Array.from(e.dataTransfer.files);
      if (!multiple && files.length > 1) {
        uploadFiles([files[0]]);
      } else {
        uploadFiles(files);
      }
    },
    [uploadFiles, multiple]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      uploadFiles(files);
      // Reset input value to allow selecting the same file again
      e.target.value = '';
    },
    [uploadFiles]
  );

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const getFileIcon = (file: UploadingFile) => {
    if (file.status === 'completed') {
      return <CheckCircle className="w-5 h-5 text-green-500" />;
    }
    if (file.status === 'error') {
      return <AlertCircle className="w-5 h-5 text-red-500" />;
    }
    if (file.file.type.startsWith('image/')) {
      return (
        <img
          src={URL.createObjectURL(file.file)}
          alt={file.file.name}
          className="w-10 h-10 object-cover rounded"
        />
      );
    }
    return <FileIcon className="w-5 h-5 text-gray-400" />;
  };

  const hasCompleted = uploadingFiles.some(f => f.status === 'completed');

  return (
    <div className={cn('w-full', className)}>
      {/* Educational Note about Trust-But-Verify Pattern */}
      <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-700/50 rounded-lg p-3 mb-4">
        <div className="flex items-start space-x-2">
          <svg className="w-5 h-5 text-emerald-600 dark:text-emerald-400 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          <div className="flex-1">
            <p className="text-sm font-medium text-emerald-900 dark:text-emerald-200">Trust-But-Verify Upload Pattern</p>
            <p className="text-xs text-emerald-700 dark:text-emerald-300 mt-0.5">
              This template uses a secure 3-step upload process: 1) Get a presigned URL from the backend,
              2) Upload directly to Google Cloud Storage, 3) Confirm the upload with the backend.
              This pattern prevents malicious uploads while maintaining performance.
            </p>
            <button
              onClick={() => window.open('https://cloud.google.com/storage/docs/access-control/signed-urls', '_blank')}
              className="text-xs text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 underline mt-1"
            >
              Learn more about presigned URLs →
            </button>
          </div>
        </div>
      </div>

      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          'relative border-2 border-dashed rounded-lg p-8 text-center transition-all',
          isDragging
            ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20'
            : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500',
          isUploading && 'opacity-50 pointer-events-none'
        )}
      >
        <input
          type="file"
          id="file-upload"
          className="hidden"
          multiple={multiple}
          accept={acceptedFileTypes?.join(',')}
          onChange={handleFileSelect}
          disabled={isUploading}
        />

        <label
          htmlFor="file-upload"
          className="cursor-pointer flex flex-col items-center"
        >
          <Upload className="w-12 h-12 text-gray-400 mb-4" />
          <p className="text-lg font-medium text-gray-700 dark:text-gray-200 mb-1">
            {isDragging ? 'Drop files here' : 'Drag & drop files here'}
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            or <span className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300">browse</span>
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500">
            {acceptedFileTypes && acceptedFileTypes.length > 0
              ? `Accepted: ${acceptedFileTypes.join(', ')}`
              : 'All file types accepted'}
            {maxFileSize && ` • Max size: ${formatFileSize(maxFileSize)}`}
          </p>
        </label>
      </div>

      {/* Upload Progress List */}
      {uploadingFiles.length > 0 && (
        <div className="mt-6 space-y-2">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Uploading {uploadingFiles.length} file{uploadingFiles.length !== 1 ? 's' : ''}
            </h3>
            {hasCompleted && (
              <button
                onClick={clearCompleted}
                className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
              >
                Clear completed
              </button>
            )}
          </div>

          {uploadingFiles.map((file) => (
            <div
              key={file.id}
              className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3 flex-1 min-w-0">
                  {getFileIcon(file)}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                      {file.file.name}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {formatFileSize(file.file.size)}
                      {file.error && (
                        <span className="text-red-500 ml-2">{file.error}</span>
                      )}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  {file.status === 'error' && (
                    <button
                      onClick={() => retryFile(file.id)}
                      className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                      title="Retry upload"
                    >
                      <RefreshCw className="w-4 h-4 text-gray-500 dark:text-gray-400" />
                    </button>
                  )}
                  <button
                    onClick={() => removeFile(file.id)}
                    className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                    title="Remove"
                  >
                    <X className="w-4 h-4 text-gray-500 dark:text-gray-400" />
                  </button>
                </div>
              </div>

              {/* Progress Bar */}
              {file.status === 'uploading' && (
                <div className="mt-2">
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                    <div
                      className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                      style={{ width: `${file.progress}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{file.progress}%</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}