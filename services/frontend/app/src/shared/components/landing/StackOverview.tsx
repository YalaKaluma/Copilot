import { motion } from 'motion/react';
import { Check } from 'lucide-react';

const stackHighlights = [
  {
    category: 'Frontend',
    color: 'indigo',
    items: ['React 19', 'TypeScript', 'Tailwind CSS v4', 'Vite', 'Motion']
  },
  {
    category: 'Backend',
    color: 'purple',
    items: ['FastAPI', 'SQLAlchemy', 'Alembic', 'Pydantic', 'Multi-LLM (OpenAI, Anthropic, Gemini)']
  },
  {
    category: 'Infrastructure',
    color: 'cyan',
    items: ['Redis Streams + Pub/Sub', 'Background Workers', 'Neon PostgreSQL', 'Docker Compose', 'Terraform + GCP']
  }
];

export function StackOverview() {
  return (
    <section className="py-24 border-y border-gray-200/50 dark:border-white/5 bg-gradient-to-b from-white/50 to-gray-50/50 dark:from-slate-900/50 dark:to-slate-950/50 backdrop-blur-sm relative z-10 transition-colors duration-300">
      <div className="max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.6 }}
        >
          <div className="text-center mb-16">
            <motion.span
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              className="inline-block px-4 py-1.5 text-sm font-medium text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-500/10 rounded-full mb-4"
            >
              The Stack
            </motion.span>
            <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4">
              Pre-Wired & Production Ready
            </h2>
            <p className="text-lg text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
              Every tool carefully selected. Every integration battle-tested.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {stackHighlights.map((stack, index) => (
              <StackCard key={stack.category} stack={stack} index={index} />
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}

interface StackCardProps {
  stack: {
    category: string;
    color: string;
    items: string[];
  };
  index: number;
}

function StackCard({ stack, index }: StackCardProps) {
  const colorClasses: Record<string, { border: string; dot: string; glow: string }> = {
    indigo: {
      border: 'group-hover:border-indigo-300 dark:group-hover:border-indigo-500/30',
      dot: 'bg-indigo-500',
      glow: 'shadow-indigo-500/50'
    },
    purple: {
      border: 'group-hover:border-purple-300 dark:group-hover:border-purple-500/30',
      dot: 'bg-purple-500',
      glow: 'shadow-purple-500/50'
    },
    cyan: {
      border: 'group-hover:border-cyan-300 dark:group-hover:border-cyan-500/30',
      dot: 'bg-cyan-500',
      glow: 'shadow-cyan-500/50'
    }
  };

  const colors = colorClasses[stack.color] || colorClasses.indigo;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-50px' }}
      transition={{ delay: index * 0.15, duration: 0.5 }}
      className="group"
    >
      <div className={`bg-white/80 dark:bg-white/5 rounded-2xl border border-gray-200/50 dark:border-white/10 p-6 hover:bg-white dark:hover:bg-white/10 transition-all duration-300 h-full ${colors.border}`}>
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className={`w-3 h-3 rounded-full ${colors.dot} shadow-lg ${colors.glow}`} />
          <h3 className="font-semibold text-gray-900 dark:text-white text-lg">{stack.category}</h3>
        </div>

        {/* Items */}
        <div className="space-y-3">
          {stack.items.map((item, i) => (
            <motion.div
              key={item}
              initial={{ opacity: 0, x: -10 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.15 + i * 0.05 }}
              className="flex items-center gap-3 group/item"
            >
              <div className="flex-shrink-0 w-5 h-5 rounded-md bg-gray-100 dark:bg-white/5 flex items-center justify-center group-hover/item:bg-emerald-100 dark:group-hover/item:bg-emerald-500/10 transition-colors">
                <Check className="w-3 h-3 text-gray-400 dark:text-gray-500 group-hover/item:text-emerald-600 dark:group-hover/item:text-emerald-400 transition-colors" />
              </div>
              <span className="text-sm text-gray-600 dark:text-gray-400 group-hover/item:text-gray-900 dark:group-hover/item:text-white transition-colors">
                {item}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
