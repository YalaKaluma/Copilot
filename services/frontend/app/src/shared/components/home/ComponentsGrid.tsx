import { motion } from 'motion/react';
import { MessageSquare, Upload, Bot, Radio, Workflow } from 'lucide-react';
import { ComponentCard } from './ComponentCard';

const components = [
  {
    id: 'chat',
    title: 'AI Chat Interface',
    description: 'Full-featured chat with OpenAI integration',
    icon: <MessageSquare className="w-6 h-6" />,
    demoHref: '/chat',
    gradient: 'from-indigo-500 to-purple-600',
    status: 'ready' as const
  },
  {
    id: 'file-upload',
    title: 'File Upload',
    description: 'Direct browser-to-GCS uploads with presigned URLs',
    icon: <Upload className="w-6 h-6" />,
    demoHref: '/file-upload',
    gradient: 'from-emerald-500 to-teal-600',
    status: 'ready' as const
  },
  {
    id: 'agent-chat',
    title: 'Agent Chat Interface',
    description: 'Basic Agent Chat Interface powered by the OpenAI Agent SDK',
    icon: <Bot className="w-6 h-6" />,
    demoHref: '/agent',
    gradient: 'from-gray-600 to-gray-900',
    status: 'ready' as const
  },
  {
    id: 'realtime-agent',
    title: 'Realtime Voice Agent',
    description: 'Voice-enabled AI agent with WebSocket streaming and low latency',
    icon: <Radio className="w-6 h-6" />,
    demoHref: '/realtime',
    gradient: 'from-rose-500 to-pink-600',
    status: 'ready' as const
  },
  {
    id: 'jobs',
    title: 'Background Jobs',
    description: 'Redis Streams queue with real-time SSE progress updates',
    icon: <Workflow className="w-6 h-6" />,
    demoHref: '/jobs',
    gradient: 'from-blue-500 to-indigo-600',
    status: 'ready' as const
  }
];

export function ComponentsGrid() {
  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="mb-12"
    >
      <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-8">Available Components</h2>
      <div className="grid md:grid-cols-2 gap-6">
        {components.map((component, index) => (
          <ComponentCard key={component.id} {...component} index={index} />
        ))}
      </div>
    </motion.section>
  );
}
