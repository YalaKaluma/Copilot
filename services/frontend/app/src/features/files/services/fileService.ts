import apiClient from '../../../shared/lib/api-client';

// Types
export interface Bucket {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  file_count?: number;
  total_size?: number;
}

export interface FileRecord {
  id: string;
  filename: string;
  original_filename: string;
  bucket_id: string;
  file_size: number;
  content_type: string;
  storage_path: string;
  status: 'pending' | 'uploading' | 'available' | 'deleted';
  created_at: string;
  updated_at: string;
  created_by_id?: string;
  metadata?: Record<string, unknown>;
}

export interface FileUploadUrlRequest {
  bucket_id: string;
  filename: string;
  content_type: string;
  file_size: number;
}

export interface FileUploadUrlResponse {
  file_id: string;
  upload_url: string;
  expires_in: number;
  storage_path: string;
}

export interface FileListResponse {
  files: FileRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface BucketListResponse {
  buckets?: Bucket[];
  total?: number;
}

export interface FileStatsResponse {
  total_files: number;
  total_size_bytes: number;
  average_size_bytes: number;
  bucket_id?: string;
}

// Batch upload types
export interface FileUploadMetadata {
  filename: string;
  content_type: string;
  file_size: number;
}

export interface BatchFileUploadUrlRequest {
  bucket_id: string;
  files: FileUploadMetadata[];
}

export interface BatchFileUploadUrlResponseItem {
  index: number;
  upload_url: string;
  file_id: string;
  storage_path: string;
}

export interface BatchFileUploadUrlResponse {
  files: BatchFileUploadUrlResponseItem[];
  expires_in: number;
}

export interface BatchConfirmRequest {
  file_ids: string[];
}

export interface BatchConfirmResponseItem {
  file_id: string;
  success: boolean;
  status: string;
}

export interface BatchConfirmResponse {
  files: BatchConfirmResponseItem[];
  confirmed_count: number;
  failed_count: number;
}

export interface BatchUploadProgress {
  fileIndex: number;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  error?: string;
}

/**
 * Service for file operations with presigned URL support
 */
class FileService {
  // Bucket operations
  async listBuckets(): Promise<BucketListResponse> {
    const response = await apiClient.get<Bucket[] | BucketListResponse>('/buckets/');
    // Handle both array response and object with buckets property
    if (Array.isArray(response)) {
      return { buckets: response, total: response.length };
    }
    return response as BucketListResponse;
  }

  async createBucket(name: string): Promise<Bucket> {
    // Backend expects both 'name' and 'slug' fields
    const slug = name.toLowerCase().replace(/[^a-z0-9-]/g, '-');
    return apiClient.post<Bucket>('/buckets/', { 
      name: name,
      slug: slug,
      provider: 'gcp',
      is_public: false
    });
  }

  async getBucket(bucketId: string): Promise<Bucket> {
    return apiClient.get<Bucket>(`/buckets/${bucketId}/`);
  }

  async deleteBucket(bucketId: string): Promise<void> {
    return apiClient.delete(`/buckets/${bucketId}/`);
  }

  // File operations
  async listFiles(params?: {
    bucket_id?: string;
    limit?: number;
    offset?: number;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  }): Promise<FileListResponse> {
    return apiClient.get<FileListResponse>('/files/', { params });
  }

  async searchFiles(params: {
    q?: string;
    bucket_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<FileListResponse> {
    return apiClient.get<FileListResponse>('/files/search/', { params });
  }

  async getFileStats(bucketId?: string): Promise<FileStatsResponse> {
    const params = bucketId ? { bucket_id: bucketId } : undefined;
    return apiClient.get<FileStatsResponse>('/files/stats', { params });
  }

  async getFile(fileId: string): Promise<FileRecord> {
    return apiClient.get<FileRecord>(`/files/${fileId}`);
  }

  async deleteFile(fileId: string): Promise<void> {
    return apiClient.delete(`/files/${fileId}`);
  }

  /**
   * Get a presigned URL for uploading a file directly to storage
   */
  async getUploadUrl(request: FileUploadUrlRequest): Promise<FileUploadUrlResponse> {
    return apiClient.post<FileUploadUrlResponse>('/files/upload/url', request);
  }

  /**
   * Upload a file directly to storage using a presigned URL
   */
  async uploadToPresignedUrl(
    url: string,
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      // Track upload progress
      if (onProgress) {
        xhr.upload.addEventListener('progress', (event) => {
          if (event.lengthComputable) {
            const progress = Math.round((event.loaded / event.total) * 100);
            onProgress(progress);
          }
        });
      }

      // Handle completion
      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve();
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      });

      // Handle errors
      xhr.addEventListener('error', () => {
        reject(new Error('Upload failed due to network error'));
      });

      xhr.addEventListener('abort', () => {
        reject(new Error('Upload was cancelled'));
      });

      // Send the request
      xhr.open('PUT', url, true);
      xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
      xhr.send(file);
    });
  }

  /**
   * Confirm that a file upload completed successfully
   */
  async confirmUpload(fileId: string): Promise<FileRecord> {
    return apiClient.post<FileRecord>(`/files/upload/confirm/${fileId}`);
  }

  /**
   * Complete file upload flow with presigned URL
   */
  async uploadFile(
    file: File,
    bucketId: string,
    onProgress?: (progress: number) => void
  ): Promise<FileRecord> {
    try {
      // Step 1: Get presigned URL
      const uploadUrlResponse = await this.getUploadUrl({
        bucket_id: bucketId,
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
        file_size: file.size,
      });

      // Step 2: Upload file directly to storage
      await this.uploadToPresignedUrl(
        uploadUrlResponse.upload_url,
        file,
        onProgress
      );

      // Step 3: Confirm upload completion
      const fileRecord = await this.confirmUpload(uploadUrlResponse.file_id);

      return fileRecord;
    } catch (error) {
      console.error('File upload failed:', error);
      // Check if it's a GCS configuration issue
      if (error instanceof Error && error.message.includes('404')) {
        throw new Error('File upload requires Google Cloud Storage to be configured. Please set up GCS credentials first.');
      }
      throw error;
    }
  }

  /**
   * Upload multiple files with progress tracking
   */
  async uploadMultipleFiles(
    files: File[],
    bucketId: string,
    onProgress?: (fileIndex: number, progress: number) => void
  ): Promise<FileRecord[]> {
    const results: FileRecord[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const result = await this.uploadFile(
        file,
        bucketId,
        (progress) => onProgress?.(i, progress)
      );
      results.push(result);
    }

    return results;
  }

  /**
   * Get download URL for a file
   */
  async getDownloadUrl(fileId: string): Promise<string> {
    const response = await apiClient.get<{ signed_url: string; expires_in_seconds: number }>(
      `/files/${fileId}/download`
    );
    return response.signed_url;
  }

  // ==========================================================================
  // Batch Upload Methods
  // ==========================================================================

  /**
   * Get presigned URLs for multiple files in a single request
   */
  async getBatchUploadUrls(
    bucketId: string,
    files: File[]
  ): Promise<BatchFileUploadUrlResponse> {
    const request: BatchFileUploadUrlRequest = {
      bucket_id: bucketId,
      files: files.map((file) => ({
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
        file_size: file.size,
      })),
    };
    return apiClient.post<BatchFileUploadUrlResponse>('/files/upload/batch-urls', request);
  }

  /**
   * Confirm multiple file uploads
   */
  async batchConfirmUploads(fileIds: string[]): Promise<BatchConfirmResponse> {
    return apiClient.post<BatchConfirmResponse>('/files/upload/batch-confirm', {
      file_ids: fileIds,
    });
  }

  /**
   * Upload multiple files using batch endpoints for better performance
   *
   * Flow:
   * 1. Get all presigned URLs in one request
   * 2. Upload all files in parallel
   * 3. Confirm all uploads in one request
   */
  async uploadFilesBatch(
    files: File[],
    bucketId: string,
    onProgress?: (progress: BatchUploadProgress[]) => void
  ): Promise<{ successful: FileRecord[]; failed: { file: File; error: string }[] }> {
    // Initialize progress tracking
    const progressState: BatchUploadProgress[] = files.map((_, index) => ({
      fileIndex: index,
      progress: 0,
      status: 'pending' as const,
    }));

    const updateProgress = (index: number, updates: Partial<BatchUploadProgress>) => {
      progressState[index] = { ...progressState[index], ...updates };
      onProgress?.([...progressState]);
    };

    try {
      // Step 1: Get all presigned URLs in one request
      const batchUrlResponse = await this.getBatchUploadUrls(bucketId, files);

      // Step 2: Upload all files in parallel
      const uploadPromises = batchUrlResponse.files.map(async (urlItem) => {
        const file = files[urlItem.index];
        updateProgress(urlItem.index, { status: 'uploading' });

        try {
          await this.uploadToPresignedUrl(
            urlItem.upload_url,
            file,
            (progress) => updateProgress(urlItem.index, { progress })
          );
          updateProgress(urlItem.index, { status: 'completed', progress: 100 });
          return { success: true, fileId: urlItem.file_id, index: urlItem.index };
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Upload failed';
          updateProgress(urlItem.index, { status: 'error', error: errorMessage });
          return { success: false, fileId: urlItem.file_id, index: urlItem.index, error: errorMessage };
        }
      });

      const uploadResults = await Promise.all(uploadPromises);

      // Step 3: Confirm successful uploads in one request
      const successfulFileIds = uploadResults
        .filter((r) => r.success)
        .map((r) => r.fileId);

      const failedUploads = uploadResults
        .filter((r) => !r.success)
        .map((r) => ({
          file: files[r.index],
          error: r.error || 'Upload failed',
        }));

      if (successfulFileIds.length > 0) {
        const confirmResponse = await this.batchConfirmUploads(successfulFileIds);

        // Get file records for confirmed uploads
        const confirmedFileIds = confirmResponse.files
          .filter((f) => f.success)
          .map((f) => f.file_id);

        const fileRecords = await Promise.all(
          confirmedFileIds.map((id) => this.getFile(id))
        );

        // Add failed confirmations to failed list
        const failedConfirmations = confirmResponse.files
          .filter((f) => !f.success)
          .map((f) => {
            const urlItem = batchUrlResponse.files.find((u) => u.file_id === f.file_id);
            return {
              file: files[urlItem?.index ?? 0],
              error: `Confirmation failed: ${f.status}`,
            };
          });

        return {
          successful: fileRecords,
          failed: [...failedUploads, ...failedConfirmations],
        };
      }

      return { successful: [], failed: failedUploads };
    } catch (error) {
      // If batch URL request fails, all files fail
      const errorMessage = error instanceof Error ? error.message : 'Batch upload failed';
      return {
        successful: [],
        failed: files.map((file) => ({ file, error: errorMessage })),
      };
    }
  }
}

// Export singleton instance
export const fileService = new FileService();
export default fileService;