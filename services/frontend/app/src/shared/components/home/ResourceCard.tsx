import { ArrowUpRight } from 'lucide-react';
import { ReactNode } from 'react';
import { AnimatedCard } from './AnimatedCard';

interface ResourceCardProps {
  title: string;
  description: string;
  icon: ReactNode;
  href: string;
  index: number;
}

export function ResourceCard({ title, description, icon, href, index }: ResourceCardProps) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="block h-full">
      <AnimatedCard delay={index * 0.1} className="h-full bg-white/70 dark:bg-white/5 border border-gray-200 dark:border-white/10 hover:border-indigo-500/50 dark:hover:border-indigo-500/50 group shadow-sm dark:shadow-none hover:shadow-md transition-all">
        <div className="flex items-start justify-between mb-4">
          <div className="p-2.5 bg-indigo-50 dark:bg-white/10 rounded-lg text-indigo-600 dark:text-indigo-400 group-hover:scale-110 transition-transform duration-300">
            {icon}
          </div>
          <ArrowUpRight className="w-4 h-4 text-gray-400 dark:text-gray-500 group-hover:text-gray-900 dark:group-hover:text-white transition-colors" />
        </div>

        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
          {title}
        </h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
          {description}
        </p>
      </AnimatedCard>
    </a>
  );
}