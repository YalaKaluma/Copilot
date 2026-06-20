import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';
import apiClient from '../../../shared/lib/api-client';
import { fileService, FileStatsResponse } from '../services/fileService';

export interface UseFileStorageReturn {
  gcsConfigured: boolean;
  gcsBucketName: string | null;
  loading: boolean;
  stats: FileStatsResponse | null;
  authError: string | null;
  defaultBucketId: string | null;
  notification: { type: 'error' | 'success' | 'info'; message: string } | null;
  setNotification: (notification: { type: 'error' | 'success' | 'info'; message: string } | null) => void;
  checkGcsAndInitialize: () => Promise<void>;
  refreshStats: () => void;
  handleUploadComplete: () => void;
  handleFileDelete: () => void;
}

export function useFileStorage(): UseFileStorageReturn {
  const { isLoaded, isSignedIn } = useAuth();
  const [gcsConfigured, setGcsConfigured] = useState(false);
  const [gcsBucketName, setGcsBucketName] = useState<string | null>(null);
  const [checkingGcs, setCheckingGcs] = useState(true);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<FileStatsResponse | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [authError, setAuthError] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ type: 'error' | 'success' | 'info'; message: string } | null>(null);
  const [defaultBucketId, setDefaultBucketId] = useState<string | null>(null);

  const loadStats = useCallback(async (bucketId: string) => {
    try {
      const statsData = await fileService.getFileStats(bucketId);
      setStats(statsData);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  }, []);

  const checkGcsAndInitialize = useCallback(async () => {
    setCheckingGcs(true);
    setLoading(true);
    try {
      const storageStatus = await apiClient.get('/health/storage');
      
      if (storageStatus.configured) {
        setGcsConfigured(true);
        setGcsBucketName(storageStatus.bucket_name);
        await initializeDefaultBucket();
      } else {
        setGcsConfigured(false);
        setLoading(false);
        console.log('GCS not configured:', storageStatus.details);
      }
    } catch (error) {
      console.log('GCS check failed:', error);
      setGcsConfigured(false);
      setLoading(false);
    } finally {
      setCheckingGcs(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const initializeDefaultBucket = async () => {
    try {
      const response = await fileService.listBuckets();
      const bucketList = Array.isArray(response) ? response : (response.buckets || []);
      
      let defaultBucket;
      if (bucketList.length > 0) {
        defaultBucket = bucketList[0];
      } else {
        try {
          defaultBucket = await fileService.createBucket('default-storage');
        } catch (error) {
          console.error('Failed to create default bucket record:', error);
          const retryResponse = await fileService.listBuckets();
          const retryList = Array.isArray(retryResponse) ? retryResponse : (retryResponse.buckets || []);
          if (retryList.length > 0) {
            defaultBucket = retryList[0];
          }
        }
      }
      
      if (defaultBucket) {
        setDefaultBucketId(defaultBucket.id);
        await loadStats(defaultBucket.id);
      }
    } catch (error) {
      console.error('Failed to initialize:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      checkGcsAndInitialize();
    } else if (isLoaded && !isSignedIn) {
      setAuthError('You must be signed in to access file storage');
      setLoading(false);
      setCheckingGcs(false);
    }
  }, [isLoaded, isSignedIn, checkGcsAndInitialize]);

  useEffect(() => {
    if (defaultBucketId) {
      loadStats(defaultBucketId);
    }
  }, [defaultBucketId, refreshKey, loadStats]);

  const handleUploadComplete = useCallback(() => {
    setRefreshKey(prev => prev + 1);
    if (defaultBucketId) {
      loadStats(defaultBucketId);
    }
    setNotification({ type: 'success', message: 'File uploaded successfully' });
  }, [defaultBucketId, loadStats]);

  const handleFileDelete = useCallback(() => {
    setRefreshKey(prev => prev + 1);
    if (defaultBucketId) {
      loadStats(defaultBucketId);
    }
    setNotification({ type: 'success', message: 'File deleted successfully' });
  }, [defaultBucketId, loadStats]);

  const refreshStats = useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  return {
    gcsConfigured,
    gcsBucketName,
    loading: loading || checkingGcs,
    stats,
    authError,
    defaultBucketId,
    notification,
    setNotification,
    checkGcsAndInitialize,
    refreshStats,
    handleUploadComplete,
    handleFileDelete
  };
}