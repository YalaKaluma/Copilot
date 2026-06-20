import { Link } from 'react-router-dom';

export function ShowcaseHeader() {
  return (
    <div className="border-b border-gray-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-8 py-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Component Library</h1>
            <p className="text-sm text-gray-600 mt-1">
              Ready-to-use components for your application
            </p>
          </div>
          <Link
            to="/"
            className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
          >
            ← Back to Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}