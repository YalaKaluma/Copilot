import { Link } from 'react-router-dom';
import { PlayCircle, ArrowRight } from 'lucide-react';
import { ReactNode } from 'react';
import { AnimatedCard } from './AnimatedCard';
import { cn } from '../../utils/cn';

interface ComponentCardProps {
  title: string;
  description: string;
  icon: ReactNode;
  demoHref: string;
  gradient: string;
  status: 'ready' | 'coming-soon';
  index: number;
}

export function ComponentCard({
  title,
  description,
  icon,
  demoHref,
  gradient,
  status,
  index
}: ComponentCardProps) {
  return (
    <AnimatedCard delay={index * 0.1} className="h-full flex flex-col">
      <div className="flex items-start justify-between mb-4">
        <div className={cn(
          "p-3 rounded-xl bg-gradient-to-br text-white shadow-lg",
          gradient
        )}>
          {icon}
        </div>
        {status === 'coming-soon' && (
          <span className="px-2 py-1 bg-gray-100 dark:bg-white/10 text-gray-500 dark:text-white/60 text-xs font-medium rounded-full border border-gray-200 dark:border-white/5">
            Coming Soon
          </span>
        )}
      </div>

      <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
        {title}
      </h3>
      <p className="text-gray-600 dark:text-gray-400 mb-6 flex-grow leading-relaxed">
        {description}
      </p>

      <Link
        to={status === 'ready' ? demoHref : '#'}
        className={cn(
          "group flex items-center justify-between w-full px-4 py-3 rounded-xl transition-all",
          status === 'ready'
            ? "bg-gray-100 dark:bg-white/10 hover:bg-gray-200 dark:hover:bg-white/20 text-gray-900 dark:text-white hover:pl-5"
            : "bg-gray-50 dark:bg-white/5 text-gray-400 dark:text-gray-500 cursor-not-allowed"
        )}
        onClick={(e) => status !== 'ready' && e.preventDefault()}
      >
        <span className="font-medium">
          {status === 'ready' ? 'View Demo' : 'Not Available'}
        </span>
        {status === 'ready' ? (
          <ArrowRight className="w-4 h-4 opacity-50 group-hover:opacity-100 transition-opacity" />
        ) : (
          <PlayCircle className="w-4 h-4" />
        )}
      </Link>
    </AnimatedCard>
  );
}