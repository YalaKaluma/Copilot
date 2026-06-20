import { Puzzle } from 'lucide-react';

export function QuickStartSection() {
  return (
    <div className="bg-white/70 dark:bg-white/5 rounded-2xl p-8 border border-gray-200 dark:border-white/10 mb-12 shadow-sm dark:shadow-none hover:shadow-md transition-shadow">
      <div className="flex items-start gap-6">
        <div className="bg-indigo-600 dark:bg-indigo-500 rounded-xl p-4 shadow-lg shadow-indigo-500/20">
          <Puzzle className="w-8 h-8 text-white" />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
            Plug & Play Components
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-6 text-lg">
            Snap components together to build your app. Type-safe, pre-configured, and ready to connect.
          </p>
          <div className="flex flex-wrap gap-4">
            <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-white/5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-white/5">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              Modular Architecture
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-white/5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-white/5">
              <span className="w-2 h-2 bg-indigo-500 rounded-full" />
              TypeScript Ready
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}