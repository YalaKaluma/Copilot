import { motion } from 'motion/react';
import { useUser } from '@clerk/clerk-react';

export function WelcomeSection() {
  const { user } = useUser();

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-12"
    >
      <span className="text-indigo-600 dark:text-indigo-400 font-semibold tracking-wider text-sm uppercase mb-2 block">
        Dashboard
      </span>
      <h1 className="text-4xl md:text-5xl font-bold text-gray-900 dark:text-white mb-4">
        Hello, <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 via-purple-600 to-cyan-600 dark:from-indigo-400 dark:via-purple-400 dark:to-cyan-400">{user?.firstName || 'Builder'}</span>
      </h1>
      <p className="text-xl text-gray-600 dark:text-gray-400 max-w-2xl">
        All systems are go. Select a module to begin or check the status below.
      </p>
    </motion.div>
  );
}