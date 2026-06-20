// API base URL configuration
// Use VITE_BACKEND_URL (what we're actually setting) or fall back to VITE_API_BASE_URL
// In local development, use /api to leverage Vite's proxy
const baseUrl = import.meta.env.VITE_BACKEND_URL || import.meta.env.VITE_API_BASE_URL || '/api';

// Ensure the base URL always ends with /api for consistency
// Local: /api stays /api
// Production: https://backend.run.app becomes https://backend.run.app/api
export const API_BASE_URL = baseUrl === '/api' ? baseUrl : `${baseUrl}/api`;