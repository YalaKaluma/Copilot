import React, { useEffect, useState } from 'react';
import { FileIcon, Download, Trash2, Search, FolderOpen, Image, FileText, Film, Music } from 'lucide-react';
import { fileService, FileRecord } from '../services/fileService';
import { cn } from '../../../shared/utils/cn';

interface FileListProps {
  bucketId?: string;
  onFileSelect?: (file: FileRecord) => void;
  onFileDelete?: (file: FileRecord) => void;
  className?: string;
}

export function FileList({
  bucketId,
  onFileSelect,
  onFileDelete,
  className,
}: FileListProps) {
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredFiles, setFilteredFiles] = useState<FileRecord[]>([]);

  useEffect(() => {
    loadFiles();
  }, [bucketId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    // Filter files based on search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      setFilteredFiles(
        files.filter(file =>
          file.filename.toLowerCase().includes(query) ||
          file.original_filename.toLowerCase().includes(query)
        )
      );
    } else {
      setFilteredFiles(files);
    }
  }, [files, searchQuery]);

  const loadFiles = async () => {
    try {
      setLoading(true);
      const response = await fileService.listFiles({
        bucket_id: bucketId,
        limit: 100,
        sort_by: 'created_at',
        sort_order: 'desc',
      });
      setFiles(response.files);
    } catch (error) {
      console.error('Failed to load files:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (file: FileRecord) => {
    if (!confirm(`Delete "${file.filename}"?`)) return;

    try {
      await fileService.deleteFile(file.id);
      setFiles(prev => prev.filter(f => f.id !== file.id));
      onFileDelete?.(file);
    } catch (error) {
      console.error('Failed to delete file:', error);
      alert('Failed to delete file');
    }
  };

  const handleDownload = async (file: FileRecord) => {
    try {
      const url = await fileService.getDownloadUrl(file.id);
      window.open(url, '_blank');
    } catch (error) {
      console.error('Failed to get download URL:', error);
      alert('Failed to download file');
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      const hours = Math.floor(diff / (1000 * 60 * 60));
      if (hours === 0) {
        const minutes = Math.floor(diff / (1000 * 60));
        return minutes === 0 ? 'Just now' : `${minutes}m ago`;
      }
      return `${hours}h ago`;
    }
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days} days ago`;
    
    return date.toLocaleDateString();
  };

  const getFileIcon = (contentType: string, _filename: string) => {
    if (contentType.startsWith('image/')) {
      return <Image className="w-5 h-5" />;
    }
    if (contentType.startsWith('video/')) {
      return <Film className="w-5 h-5" />;
    }
    if (contentType.startsWith('audio/')) {
      return <Music className="w-5 h-5" />;
    }
    if (contentType.includes('pdf') || contentType.includes('document')) {
      return <FileText className="w-5 h-5" />;
    }
    return <FileIcon className="w-5 h-5" />;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className={cn('w-full', className)}>
      {/* Search Bar */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
          />
        </div>
      </div>

      {/* Empty State */}
      {filteredFiles.length === 0 && (
        <div className="text-center py-12 px-4">
          <FolderOpen className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            {searchQuery ? 'No files found' : 'No files uploaded yet'}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {searchQuery
              ? 'Try adjusting your search'
              : 'Upload some files to get started'}
          </p>
        </div>
      )}

      {/* File Table */}
      {filteredFiles.length > 0 && (
        <div className="overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-800/50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Size
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Modified
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Status
                </th>
                <th className="relative px-6 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {filteredFiles.map((file) => (
                <tr
                  key={file.id}
                  className="hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer"
                  onClick={() => onFileSelect?.(file)}
                >
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="flex-shrink-0 text-gray-400">
                        {getFileIcon(file.content_type, file.filename)}
                      </div>
                      <div className="ml-3">
                        <p className="text-sm font-medium text-gray-900 dark:text-white">
                          {file.filename}
                        </p>
                        {file.original_filename !== file.filename && (
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            {file.original_filename}
                          </p>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {formatFileSize(file.file_size)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {formatDate(file.updated_at)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={cn(
                        'px-2 inline-flex text-xs leading-5 font-semibold rounded-full',
                        file.status === 'available'
                          ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
                          : file.status === 'pending'
                          ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300'
                          : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
                      )}
                    >
                      {file.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div
                      className="flex items-center space-x-2"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={() => handleDownload(file)}
                        className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300"
                        title="Download"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(file)}
                        className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}