import { Link } from 'react-router-dom';
import { Code2, ArrowRight } from 'lucide-react';
import { ThemeToggle } from '../ThemeToggle';

export function LandingNav() {
  return (
    <nav className="fixed top-0 w-full bg-white/70 dark:bg-slate-950/80 backdrop-blur-md border-b border-gray-200 dark:border-white/5 z-50 transition-colors duration-300">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3 group">
          <div className="relative">
            <div className="absolute -inset-1 bg-indigo-500 rounded-lg blur opacity-20 group-hover:opacity-40 transition-opacity" />
            <div className="relative w-10 h-10 bg-white/50 dark:bg-slate-900 border border-gray-200 dark:border-white/10 rounded-xl flex items-center justify-center shadow-xl">
              <Code2 className="w-6 h-6 text-indigo-600 dark:text-indigo-500" />
            </div>
          </div>
          <div className="flex flex-col">
            <span className="text-lg font-bold text-gray-900 dark:text-white leading-none tracking-tight">
              Tomoro
            </span>
            <span className="text-xs font-medium text-gray-500 dark:text-gray-500">
              Fullstack Kit
            </span>
          </div>
        </Link>

        <div className="flex items-center gap-4">
          <ThemeToggle />
          <Link
            to="/login"
            className="px-4 py-2 bg-slate-900 dark:bg-white text-white dark:text-slate-950 rounded-lg text-sm font-semibold hover:opacity-90 transition-all flex items-center gap-2 shadow-lg shadow-indigo-500/10 active:scale-95"
          >
            View Demo
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </nav>
  );
}