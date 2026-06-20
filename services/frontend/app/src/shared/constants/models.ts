/**
 * Model and provider-related constants
 */

// Default models per provider
export const DEFAULT_MODEL = 'gpt-5-mini' as const;

// Fallback models when API is unavailable
export const FALLBACK_MODELS = ['gpt-5-mini', 'gpt-5.2', 'gpt-4o-mini'] as const;

// Provider identifiers
export const PROVIDERS = {
  OPENAI: 'openai',
  ANTHROPIC: 'anthropic',
  GEMINI: 'gemini',
} as const;

// Default provider priority (first available is used)
export const PROVIDER_PRIORITY = ['openai', 'anthropic', 'gemini'] as const;

// Provider display configuration
export const PROVIDER_CONFIG = {
  openai: {
    name: 'OpenAI',
    color: 'green',
    defaultModel: 'gpt-5-mini',
  },
  anthropic: {
    name: 'Claude',
    color: 'orange',
    defaultModel: 'claude-sonnet-4-5-20250929',
  },
  gemini: {
    name: 'Gemini',
    color: 'blue',
    defaultModel: 'gemini-3-flash-preview',
  },
} as const;
