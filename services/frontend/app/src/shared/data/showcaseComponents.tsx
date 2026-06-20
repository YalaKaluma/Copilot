import { MessageSquare, Upload, Bot, Radio, Workflow } from 'lucide-react';

export const showcaseComponents = [
  {
    id: 'chat',
    title: 'AI Chat Interface',
    description: 'Production-ready chat component with OpenAI integration, streaming responses, and model selection.',
    icon: <MessageSquare className="w-6 h-6" />,
    href: '/chat',
    gradient: 'from-indigo-500 to-purple-600',
    features: [
      'Streaming responses',
      'Model selection (GPT-5, GPT-4, etc.)',
      'Conversation history',
      'Typing indicators',
      'Error handling'
    ],
    techStack: ['OpenAI API', 'Server-Sent Events', 'React Hooks', 'Tailwind CSS'],
    importStatement: `import { ChatInterface } from '@/features/chat/components/ChatInterface';`
  },
  {
    id: 'agent-chat',
    title: 'Agent Chat Interface',
    description: 'Grey-themed chat experience backed by the Agent service with session persistence.',
    icon: <Bot className="w-6 h-6" />,
    href: '/agent',
    gradient: 'from-gray-600 to-gray-900',
    features: [
      'Session-scoped memory',
      'Streaming responses',
    ],
    techStack: ['OpenAI Agent SDK', 'React Hooks', 'Tailwind CSS'],
    importStatement: `import { AgentChatInterface } from '@/features/chat/components/AgentChatInterface';`
  },
  {
    id: 'file-upload',
    title: 'File Upload System',
    description: 'Direct browser-to-GCS uploads using presigned URLs with trust-but-verify pattern for secure file handling.',
    icon: <Upload className="w-6 h-6" />,
    href: '/file-upload',
    gradient: 'from-emerald-500 to-teal-600',
    features: [
      'Drag & drop interface',
      'Direct browser-to-GCS uploads',
      'Presigned URL generation',
      'Trust-but-verify pattern',
      'Real-time progress tracking'
    ],
    techStack: ['Google Cloud Storage', 'Presigned URLs', 'React Dropzone', 'XMLHttpRequest Upload'],
    importStatement: `import { FileUpload } from '@/features/files/components/FileUpload';`
  },
  {
    id: 'realtime',
    title: 'Realtime Voice Agent',
    description: 'Voice-enabled AI agent using OpenAI Realtime API for bidirectional audio streaming.',
    icon: <Radio className="w-6 h-6" />,
    href: '/realtime',
    gradient: 'from-rose-500 to-pink-600',
    features: [
      'Bidirectional audio',
      'Voice activity detection',
      'Real-time transcription',
      'Low-latency responses'
    ],
    techStack: ['OpenAI Realtime API', 'WebRTC', 'Web Audio API', 'WebSocket'],
    importStatement: `import { RealtimeAgent } from '@/features/chat/components/RealtimeAgent';`
  },
  {
    id: 'jobs',
    title: 'Background Jobs',
    description: 'Real-time job processing with Redis Streams for queuing and Pub/Sub for live progress updates via SSE.',
    icon: <Workflow className="w-6 h-6" />,
    href: '/jobs',
    gradient: 'from-blue-500 to-indigo-600',
    features: [
      'Redis Stream queue',
      'Real-time SSE updates',
      'Progress tracking',
      'Worker architecture'
    ],
    techStack: ['Redis Streams', 'Redis Pub/Sub', 'Server-Sent Events', 'Background Workers'],
    importStatement: `import { JobsDemo, useCreateJob, useJobStream } from '@/features/jobs';`
  }
];
