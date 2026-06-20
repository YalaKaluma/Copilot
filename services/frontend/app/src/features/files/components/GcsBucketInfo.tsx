import { Cloud } from 'lucide-react';

interface GcsBucketInfoProps {
  bucketName: string;
}

export function GcsBucketInfo({ bucketName }: GcsBucketInfoProps) {
  return (
    <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg p-4 mb-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Cloud className="w-5 h-5 text-slate-600 dark:text-slate-400" />
          <div>
            <p className="text-sm font-medium text-slate-900 dark:text-slate-100">Google Cloud Storage Bucket</p>
            <p className="text-sm text-slate-700 dark:text-slate-300 font-mono">{bucketName}</p>
          </div>
        </div>
        <div className="text-xs text-slate-600 dark:text-slate-400">
          All files are stored in this GCS bucket
        </div>
      </div>
    </div>
  );
}