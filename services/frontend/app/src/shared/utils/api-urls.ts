/**
 * Get the API documentation URL based on the current environment
 * @returns The full URL to the API docs
 */
export function getApiDocsUrl(): string {
  // Use VITE_BACKEND_URL if available (production/staging)
  const backendUrl = import.meta.env.VITE_BACKEND_URL;

  if (backendUrl) {
    // Production/staging - use the backend URL directly
    return `${backendUrl}/docs`;
  }

  // Local development - backend runs on port 8080
  return 'http://localhost:8080/docs';
}

/**
 * Get the backend health check URL
 * @returns The full URL to the health endpoint
 */
export function getHealthUrl(): string {
  const backendUrl = import.meta.env.VITE_BACKEND_URL;

  if (backendUrl) {
    return `${backendUrl}/health`;
  }

  return 'http://localhost:8080/health';
}