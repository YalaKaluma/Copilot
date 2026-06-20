import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { Copy, Check, Code2 } from 'lucide-react';
import { ReactNode, useState } from 'react';

interface ShowcaseComponentCardProps {
  id: string;
  title: string;
  description: string;
  icon: ReactNode;
  href: string;
  gradient: string;
  features: string[];
  techStack: string[];
  importStatement: string;
  index: number;
}

export function ShowcaseComponentCard({
  // id,  // Commented out unused prop
  title,
  description,
  icon,
  href,
  gradient,
  features,
  techStack,
  importStatement,
  index
}: ShowcaseComponentCardProps) {
  const [copied, setCopied] = useState(false);

  const handleCopyImport = () => {
    navigator.clipboard.writeText(importStatement);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      className="bg-white rounded-2xl border border-gray-200 overflow-hidden hover:shadow-xl transition-all"
    >
      {/* Component Header */}
      <div className={`p-8 bg-gradient-to-br ${gradient}`}>
        <div className="flex items-start justify-between text-white">
          <div className="p-3 bg-white/20 backdrop-blur rounded-xl">
            {icon}
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleCopyImport}
              className="p-2 bg-white/20 backdrop-blur rounded-lg hover:bg-white/30 transition-colors"
              title="Copy import"
            >
              {copied ? (
                <Check className="w-4 h-4" />
              ) : (
                <Copy className="w-4 h-4" />
              )}
            </button>
            <Link
              to={href}
              className="p-2 bg-white/20 backdrop-blur rounded-lg hover:bg-white/30 transition-colors"
              title="View demo"
            >
              <Code2 className="w-4 h-4" />
            </Link>
          </div>
        </div>
        <h2 className="text-2xl font-bold text-white mt-4 mb-2">
          {title}
        </h2>
        <p className="text-white/90 text-sm leading-relaxed">
          {description}
        </p>
      </div>

      {/* Component Details */}
      <div className="p-8 space-y-6">
        <ComponentFeatures features={features} />
        <ComponentTechStack techStack={techStack} />
        <ComponentActions href={href} />
      </div>
    </motion.div>
  );
}

function ComponentFeatures({ features }: { features: string[] }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
        Features
      </h3>
      <ul className="space-y-2">
        {features.map((feature) => (
          <li key={feature} className="flex items-start">
            <svg
              className="w-5 h-5 text-green-500 mr-2 flex-shrink-0 mt-0.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span className="text-sm text-gray-700">{feature}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ComponentTechStack({ techStack }: { techStack: string[] }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
        Tech Stack
      </h3>
      <div className="flex flex-wrap gap-2">
        {techStack.map((tech) => (
          <span
            key={tech}
            className="px-3 py-1 bg-gray-100 text-gray-700 text-xs font-medium rounded-full"
          >
            {tech}
          </span>
        ))}
      </div>
    </div>
  );
}

function ComponentActions({ href }: { href: string }) {
  return (
    <div className="pt-4 border-t border-gray-200">
      <Link
        to={href}
        className="w-full px-4 py-3 bg-gray-900 text-white rounded-xl font-medium text-sm hover:bg-gray-800 transition-colors flex items-center justify-center"
      >
        View Live Demo
        <svg
          className="w-4 h-4 ml-2"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
      </Link>
    </div>
  );
}