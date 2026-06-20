import { Github } from 'lucide-react';

export function LandingFooter() {
  return (
    <footer className="py-8 relative z-10">
      <div className="max-w-7xl mx-auto px-6">
        <div className="border-t border-gray-200 dark:border-white/10 pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            © {new Date().getFullYear()} Tomoro Fullstack Kit. All rights reserved.
          </p>
          <div className="flex items-center gap-6">
            <a
              href="https://github.com/tomoro-ai/fullstack-template"
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors cursor-pointer"
            >
              <Github className="w-5 h-5" />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}