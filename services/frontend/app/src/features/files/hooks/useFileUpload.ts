import { useState, useCallback } from 'react';
import { fileService, FileRecord } from '../services/fileService';

export interface UploadingFile {
  id: string;
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  error?: string;
  result?: FileRecord;
}

export interface UseFileUploadOptions {
  bucketId: string;
  maxFileSize?: number; // in bytes
  acceptedFileTypes?: string[]; // MIME types or extensions
  onUploadComplete?: (file: FileRecord) => void;
  onUploadError?: (file: File, error: Error) => void;
  onAllUploadsComplete?: (files: FileRecord[]) => void;
}

export function useFileUpload(options: UseFileUploadOptions) {
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const validateFile = useCallback(
    (file: File): string | null => {
      // Check file size
      if (options.maxFileSize && file.size > options.maxFileSize) {
        const maxSizeMB = Math.round(options.maxFileSize / (1024 * 1024));
        return `File size exceeds ${maxSizeMB}MB limit`;
      }

      // Check file type
      if (options.acceptedFileTypes && options.acceptedFileTypes.length > 0) {
        const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
        const isAccepted = options.acceptedFileTypes.some(type => {
          if (type.startsWith('.')) {
            // Extension check
            return fileExtension === type.toLowerCase();
          } else {
            // MIME type check
            return file.type === type || file.type.startsWith(type.split('*')[0]);
          }
        });

        if (!isAccepted) {
          return `File type not accepted. Allowed types: ${options.acceptedFileTypes.join(', ')}`;
        }
      }

      return null; // No validation errors
    },
    [options.maxFileSize, options.acceptedFileTypes]
  );

  const uploadFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;

      setIsUploading(true);

      // Initialize upload state for all files
      const newUploadingFiles: UploadingFile[] = files.map(file => ({
        id: `${Date.now()}-${Math.random()}`,
        file,
        progress: 0,
        status: 'pending' as const,
      }));

      // Validate files
      for (const uploadingFile of newUploadingFiles) {
        const error = validateFile(uploadingFile.file);
        if (error) {
          uploadingFile.status = 'error';
          uploadingFile.error = error;
        }
      }

      setUploadingFiles(newUploadingFiles);

      const completedFiles: FileRecord[] = [];

      // Upload each file
      for (let i = 0; i < newUploadingFiles.length; i++) {
        const uploadingFile = newUploadingFiles[i];
        
        // Skip files with validation errors
        if (uploadingFile.status === 'error') {
          continue;
        }

        try {
          // Update status to uploading
          setUploadingFiles(prev =>
            prev.map(f =>
              f.id === uploadingFile.id
                ? { ...f, status: 'uploading' as const }
                : f
            )
          );

          // Upload file with progress tracking
          const result = await fileService.uploadFile(
            uploadingFile.file,
            options.bucketId,
            (progress) => {
              setUploadingFiles(prev =>
                prev.map(f =>
                  f.id === uploadingFile.id
                    ? { ...f, progress }
                    : f
                )
              );
            }
          );

          // Update status to completed
          setUploadingFiles(prev =>
            prev.map(f =>
              f.id === uploadingFile.id
                ? { ...f, status: 'completed' as const, progress: 100, result }
                : f
            )
          );

          completedFiles.push(result);
          options.onUploadComplete?.(result);
        } catch (error) {
          // Update status to error
          const errorMessage = error instanceof Error ? error.message : 'Upload failed';
          
          setUploadingFiles(prev =>
            prev.map(f =>
              f.id === uploadingFile.id
                ? { ...f, status: 'error' as const, error: errorMessage }
                : f
            )
          );

          options.onUploadError?.(uploadingFile.file, error as Error);
        }
      }

      setIsUploading(false);

      if (completedFiles.length > 0) {
        options.onAllUploadsComplete?.(completedFiles);
      }
    },
    [options, validateFile]
  );

  const removeFile = useCallback((fileId: string) => {
    setUploadingFiles(prev => prev.filter(f => f.id !== fileId));
  }, []);

  const clearCompleted = useCallback(() => {
    setUploadingFiles(prev => prev.filter(f => f.status !== 'completed'));
  }, []);

  const clearAll = useCallback(() => {
    setUploadingFiles([]);
  }, []);

  const retryFile = useCallback(
    async (fileId: string) => {
      const fileToRetry = uploadingFiles.find(f => f.id === fileId);
      if (!fileToRetry || fileToRetry.status === 'uploading') return;

      // Reset the file status
      setUploadingFiles(prev =>
        prev.map(f =>
          f.id === fileId
            ? { ...f, status: 'pending' as const, progress: 0, error: undefined }
            : f
        )
      );

      // Retry upload
      await uploadFiles([fileToRetry.file]);
    },
    [uploadingFiles, uploadFiles]
  );

  return {
    uploadFiles,
    uploadingFiles,
    isUploading,
    removeFile,
    clearCompleted,
    clearAll,
    retryFile,
  };
}