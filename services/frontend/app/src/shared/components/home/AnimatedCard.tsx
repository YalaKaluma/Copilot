import { motion } from 'motion/react';
import { cn } from '../../utils/cn';
import { ReactNode } from 'react';

interface AnimatedCardProps {
    children: ReactNode;
    className?: string;
    delay?: number;
    onClick?: () => void;
}

export function AnimatedCard({ children, className, delay = 0, onClick }: AnimatedCardProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay, ease: "easeOut" }}
            whileHover={{ y: -5, scale: 1.02 }}
            className={cn(
                "relative overflow-hidden rounded-2xl border border-gray-200 dark:border-white/10 bg-white/70 dark:bg-white/5 p-6 backdrop-blur-md shadow-sm dark:shadow-xl",
                "hover:border-indigo-500/30 dark:hover:border-white/20 hover:bg-white/80 dark:hover:bg-white/10 hover:shadow-md dark:hover:shadow-2xl hover:shadow-indigo-500/10 transition-colors",
                "group",
                className
            )}
            onClick={onClick}
        >
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 via-purple-500/5 to-pink-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="relative z-10">{children}</div>
        </motion.div>
    );
}
