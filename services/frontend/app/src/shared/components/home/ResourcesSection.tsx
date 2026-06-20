import { motion } from 'motion/react';
import { Book, Github, Code2 } from 'lucide-react';
import { ResourceCard } from './ResourceCard';
import { getApiDocsUrl } from '../../utils/api-urls';

const resources = [
  {
    title: 'Documentation',
    description: 'Learn how to use and customize components',
    icon: <Book className="w-5 h-5" />,
    href: 'https://www.notion.so/Full-Stack-Template-26f0de3387ea809ab1feeccd752c9a17'
  },
  {
    title: 'GitHub Repository',
    description: 'View source code and contribute',
    icon: <Github className="w-5 h-5" />,
    href: 'https://github.com/tomoro-ai/fullstack-template'
  },
  {
    title: 'API Reference',
    description: 'Explore the backend API endpoints',
    icon: <Code2 className="w-5 h-5" />,
    href: getApiDocsUrl()
  }
];

export function ResourcesSection() {
  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
    >
      <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-8">Resources</h2>
      <div className="grid md:grid-cols-3 gap-6">
        {resources.map((resource, index) => (
          <ResourceCard key={resource.title} {...resource} index={index} />
        ))}
      </div>
    </motion.section>
  );
}