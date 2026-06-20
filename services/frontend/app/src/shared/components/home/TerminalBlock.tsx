import { motion } from 'motion/react';
import { Terminal } from 'lucide-react';

export function TerminalBlock() {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.5, duration: 0.5 }}
            className="rounded-xl overflow-hidden border border-white/10 bg-[#1a1b26] shadow-2xl font-mono text-sm w-full max-w-md"
        >
            {/* Terminal Title Bar */}
            <div className="flex items-center justify-between px-4 py-3 bg-white/5 border-b border-white/5">
                <div className="flex gap-2">
                    <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
                    <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
                    <div className="w-3 h-3 rounded-full bg-[#27c93f]" />
                </div>
                <div className="flex items-center gap-1.5 text-gray-400 text-xs">
                    <Terminal className="w-3.5 h-3.5" />
                    <span>zsh</span>
                </div>
                <div className="w-16" /> {/* Spacer for centering */}
            </div>

            {/* Terminal Content */}
            <div className="p-4 space-y-2 text-gray-300">
                <div className="flex items-center gap-2">
                    <span className="text-emerald-400">➜</span>
                    <span className="text-blue-400">~/project</span>
                    <span className="text-gray-500">git clone fullstack-template</span>
                </div>
                <div className="text-gray-500 pb-2">Cloning into 'fullstack-template'...</div>

                <div className="flex items-start gap-2">
                    <span className="text-emerald-400">➜</span>
                    <span className="text-blue-400">~/project</span>
                    <motion.div>
                        <span className="text-white">pnpm dev</span>
                        <motion.span
                            animate={{ opacity: [0, 1, 0] }}
                            transition={{ repeat: Infinity, duration: 0.8 }}
                            className="inline-block w-2.5 h-4 ml-1 align-middle bg-gray-400"
                        />
                    </motion.div>
                </div>

                <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    transition={{ delay: 2, duration: 0.5 }}
                    className="text-gray-400 pt-2 border-t border-white/5 mt-2"
                >
                    <div className="flex justify-between text-xs mb-1">
                        <span>Local:</span>
                        <span className="text-blue-400">http://localhost:3000</span>
                    </div>
                    <div className="flex justify-between text-xs">
                        <span className="text-emerald-500">Ready in 234ms</span>
                    </div>
                </motion.div>
            </div>
        </motion.div>
    );
}
