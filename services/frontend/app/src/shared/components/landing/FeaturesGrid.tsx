import { motion } from 'motion/react';
import { Cable, Database, GitBranch, Shield, Cpu, Workflow } from 'lucide-react';

const features = [
  {
    icon: Cable,
    title: 'Instant Integration',
    description: 'Frontend and backend communicate out of the box. No configuration required.',
    color: 'indigo',
    gradient: 'from-indigo-500 to-indigo-600'
  },
  {
    icon: Database,
    title: 'Live Database',
    description: 'Neon PostgreSQL with auto-migrations. Your schema evolves with your code.',
    color: 'purple',
    gradient: 'from-purple-500 to-purple-600'
  },
  {
    icon: GitBranch,
    title: 'CI/CD Pipeline',
    description: 'Push to deploy. GitHub Actions orchestrates your entire release flow.',
    color: 'cyan',
    gradient: 'from-cyan-500 to-cyan-600'
  },
  {
    icon: Shield,
    title: 'Auth Ready',
    description: 'Clerk authentication pre-wired. Users, sessions, and security handled.',
    color: 'emerald',
    gradient: 'from-emerald-500 to-emerald-600'
  },
  {
    icon: Cpu,
    title: 'AI Native',
    description: 'Multi-provider LLM service (OpenAI, Anthropic, Gemini). Switch providers seamlessly.',
    color: 'orange',
    gradient: 'from-orange-500 to-orange-600'
  },
  {
    icon: Workflow,
    title: 'Background Jobs',
    description: 'Redis Streams + Pub/Sub with real-time SSE progress. Built-in worker architecture.',
    color: 'blue',
    gradient: 'from-blue-500 to-blue-600'
  }
];

export function FeaturesGrid() {
  return (
    <section className="py-24 relative z-10">
      <div className="max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <motion.span
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="inline-block px-4 py-1.5 text-sm font-medium text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 rounded-full mb-4"
          >
            Everything Connected
          </motion.span>
          <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4">
            Plug In Your Stack
          </h2>
          <p className="text-lg text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
            Every component is pre-integrated. Pick what you need, it just works.
          </p>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <FeatureCard key={feature.title} feature={feature} index={index} />
          ))}
        </div>
      </div>
    </section>
  );
}

interface FeatureCardProps {
  feature: {
    icon: React.ComponentType<{ className?: string }>;
    title: string;
    description: string;
    color: string;
    gradient: string;
  };
  index: number;
}

function FeatureCard({ feature, index }: FeatureCardProps) {
  const Icon = feature.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-50px' }}
      transition={{ delay: index * 0.1, duration: 0.5 }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className="group relative"
    >
      {/* Card */}
      <div className="relative p-6 rounded-2xl bg-white/70 dark:bg-white/5 border border-gray-200/50 dark:border-white/10 backdrop-blur-sm overflow-hidden transition-all duration-300 hover:border-gray-300 dark:hover:border-white/20 hover:shadow-xl hover:shadow-black/5 dark:hover:shadow-none">
        {/* Hover gradient overlay */}
        <div className={`absolute inset-0 bg-gradient-to-br ${feature.gradient} opacity-0 group-hover:opacity-5 dark:group-hover:opacity-10 transition-opacity duration-300`} />

        {/* Connection indicator */}
        <div className="absolute top-4 right-4 flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs text-gray-400 dark:text-gray-500 font-medium">Connected</span>
        </div>

        {/* Icon */}
        <div className={`inline-flex p-3 rounded-xl bg-gradient-to-br ${feature.gradient} mb-4 shadow-lg`}>
          <Icon className="w-6 h-6 text-white" />
        </div>

        {/* Content */}
        <h3 className="font-semibold text-gray-900 dark:text-white mb-2 text-lg">
          {feature.title}
        </h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
          {feature.description}
        </p>

        {/* Bottom connector line */}
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-12 h-0.5 bg-gradient-to-r from-transparent via-gray-300 dark:via-gray-600 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
      </div>
    </motion.div>
  );
}
