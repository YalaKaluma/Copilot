import { FileStatsResponse } from '../services/fileService';
import { formatFileSize } from '../utils/formatters';

interface FileStorageHeaderProps {
  stats: FileStatsResponse | null;
}

export function FileStorageHeader({ stats }: FileStorageHeaderProps) {
  return (
    <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">File Storage</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Upload and manage files in your Google Cloud Storage bucket
            </p>
          </div>

          {stats && (
            <div className="flex items-center space-x-6">
              <StatCard value={stats.total_files} label="Total Files" />
              <StatCard
                value={formatFileSize(stats.total_size_bytes)}
                label="Total Size"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface StatCardProps {
  value: string | number;
  label: string;
}

function StatCard({ value, label }: StatCardProps) {
  return (
    <div className="text-center">
      <p className="text-2xl font-semibold text-gray-900 dark:text-white">{value}</p>
      <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
    </div>
  );
}