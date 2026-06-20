/**
 * Centralized configuration for the frontend app.
 *
 * All environment variables should be read here with defaults.
 * This provides:
 * - Single source of truth for config
 * - Type safety
 * - Sensible defaults when env vars are missing
 *
 * Usage:
 *   import { config } from '@/shared/lib/config';
 *   console.log(config.logLevel);
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error' | 'silent';

interface AppConfig {
  // Environment
  isDev: boolean;
  isProd: boolean;
  /** When true, show copilot version selector (dev + staging; off in prod). Derived from ENVIRONMENT at build time. */
  versionSelectorEnabled: boolean;
  nodeEnv: string;

  // API
  backendUrl: string;

  // Auth
  clerkPublishableKey: string;

  // Feature flags
  debug: boolean;

  // Langfuse (optional trace link in Plan & Execution pane)
  langfuseProjectUrl: string;
  langfuseTraceEnabled: boolean;

  // Logging
  logLevel: LogLevel;
}

function getEnv(key: string, defaultValue: string = ''): string {
  return import.meta.env[key] ?? defaultValue;
}

function getBoolEnv(key: string, defaultValue: boolean): boolean {
  const value = import.meta.env[key];
  if (value === undefined) return defaultValue;
  return value === 'true' || value === '1';
}

function getLogLevel(): LogLevel {
  const level = getEnv('VITE_LOG_LEVEL');
  const validLevels: LogLevel[] = ['debug', 'info', 'warn', 'error', 'silent'];

  if (validLevels.includes(level as LogLevel)) {
    return level as LogLevel;
  }

  // Default: debug in dev, error in prod
  return import.meta.env.DEV ? 'debug' : 'error';
}

/** ENVIRONMENT (prod | staging | branch name) is passed at build time; version selector on for dev + staging only. */
function isVersionSelectorEnabled(): boolean {
  if (import.meta.env.DEV) return true;
  const env = getEnv('VITE_ENVIRONMENT', 'prod').toLowerCase();
  return env === 'staging';
}

export const config: AppConfig = {
  // Environment
  isDev: import.meta.env.DEV,
  isProd: import.meta.env.PROD,
  versionSelectorEnabled: isVersionSelectorEnabled(),
  nodeEnv: getEnv('NODE_ENV', 'development'),

  // API - empty string means use relative URLs (Vite proxy in dev)
  backendUrl: getEnv('VITE_BACKEND_URL', ''),

  // Auth
  clerkPublishableKey: getEnv('VITE_CLERK_PUBLISHABLE_KEY', ''),

  // Feature flags
  debug: getBoolEnv('VITE_DEBUG', import.meta.env.DEV),

  // Langfuse - feature on by default; set VITE_LANGFUSE_TRACE_ENABLED=false to disable
  langfuseProjectUrl: getEnv('VITE_LANGFUSE_PROJECT_URL', 'https://cloud.langfuse.com/project/cml9et6gm0097ad07wn1py4sq'),
  langfuseTraceEnabled: getBoolEnv('VITE_LANGFUSE_TRACE_ENABLED', true),

  // Logging
  logLevel: getLogLevel(),
};

export default config;
