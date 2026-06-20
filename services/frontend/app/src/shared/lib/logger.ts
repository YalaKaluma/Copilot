/**
 * Centralized logger with levels and namespaces.
 *
 * Usage:
 *   import { logger } from '@/shared/lib/logger';
 *
 *   const log = logger.create('BatchUpload');
 *   log.debug('Starting upload');
 *   log.info('Got URLs');
 *   log.warn('Retrying...');
 *   log.error('Failed', error);
 *
 *   log.time('Step 1');
 *   // ... work
 *   log.timeEnd('Step 1');
 *
 * Configure via VITE_LOG_LEVEL environment variable:
 *   - 'debug' (default in dev): Shows all logs
 *   - 'info': Shows info, warn, error
 *   - 'warn': Shows warn, error
 *   - 'error': Shows only errors (default in prod)
 *   - 'silent': Shows nothing
 */

import { config } from './config';

type LogLevel = 'debug' | 'info' | 'warn' | 'error' | 'silent';

const LOG_LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
  silent: 4,
};

const currentLevel = config.logLevel;

interface NamespacedLogger {
  debug: (...args: unknown[]) => void;
  info: (...args: unknown[]) => void;
  warn: (...args: unknown[]) => void;
  error: (...args: unknown[]) => void;
  time: (label: string) => void;
  timeEnd: (label: string) => void;
}

function shouldLog(level: LogLevel): boolean {
  return LOG_LEVELS[level] >= LOG_LEVELS[currentLevel];
}

function formatPrefix(namespace: string): string {
  return `[${namespace}]`;
}

// Store timers per namespace
const timers = new Map<string, number>();

function createLogger(namespace: string): NamespacedLogger {
  const prefix = formatPrefix(namespace);

  return {
    debug: (...args: unknown[]) => {
      if (shouldLog('debug')) {
        console.log(prefix, ...args);
      }
    },

    info: (...args: unknown[]) => {
      if (shouldLog('info')) {
        console.info(prefix, ...args);
      }
    },

    warn: (...args: unknown[]) => {
      if (shouldLog('warn')) {
        console.warn(prefix, ...args);
      }
    },

    error: (...args: unknown[]) => {
      if (shouldLog('error')) {
        console.error(prefix, ...args);
      }
    },

    time: (label: string) => {
      if (shouldLog('debug')) {
        const key = `${namespace}:${label}`;
        timers.set(key, performance.now());
      }
    },

    timeEnd: (label: string) => {
      if (shouldLog('debug')) {
        const key = `${namespace}:${label}`;
        const start = timers.get(key);
        if (start !== undefined) {
          const duration = performance.now() - start;
          console.log(prefix, `${label}: ${duration.toFixed(1)}ms`);
          timers.delete(key);
        }
      }
    },
  };
}

// Root logger (no namespace)
const rootLogger: NamespacedLogger & { create: (namespace: string) => NamespacedLogger } = {
  ...createLogger('App'),
  create: createLogger,
};

export const logger = rootLogger;
export default logger;
