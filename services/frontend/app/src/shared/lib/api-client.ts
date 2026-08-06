import axios, { AxiosInstance, AxiosError, AxiosRequestConfig } from 'axios';
import { API_BASE_URL } from '../constants/api';

interface RequestOptions extends AxiosRequestConfig {
  useAuth?: boolean;
  _retry?: boolean;
}

/**
 * API Client with Clerk authentication support
 */
class ApiClient {
  private axiosInstance: AxiosInstance;
  private getClerkToken: (() => Promise<string | null>) | null = null;
  private _isReady: boolean = false;

  constructor(baseURL: string = API_BASE_URL) {
    this.axiosInstance = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor to add auth token
    this.axiosInstance.interceptors.request.use(
      async (config) => {
        if (this.getClerkToken) {
          try {
            const token = await this.getClerkToken();
            if (token) {
              config.headers.Authorization = `Bearer ${token}`;
            }
          } catch (error) {
            console.warn('Failed to get Clerk token:', error);
          }
        }
        const tenantCode = window.localStorage.getItem('skaiTenantCode');
        if (tenantCode) {
          config.headers['X-Tenant-Code'] = tenantCode;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling
    this.axiosInstance.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config;
        
        // If we get a 401, try to refresh the token once
        if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
          originalRequest._retry = true;
          
          if (this.getClerkToken) {
            try {
              const freshToken = await this.getClerkToken();
              if (freshToken) {
                originalRequest.headers.Authorization = `Bearer ${freshToken}`;
                return this.axiosInstance(originalRequest);
              }
            } catch (retryError) {
              console.warn('Failed to retry with fresh token:', retryError);
            }
          }
        }

        // Format error message
        let errorMessage = 'An error occurred';
        if (error.response?.data) {
          const data = error.response.data as { detail?: unknown; message?: string };
          if (data.detail) {
            if (Array.isArray(data.detail)) {
              // FastAPI validation error
              errorMessage = data.detail
                .map((err: { loc?: string[]; msg?: string }) => `${err.loc?.join('.')} - ${err.msg}`)
                .join(', ');
            } else {
              errorMessage = data.detail;
            }
          } else if (data.message) {
            errorMessage = data.message;
          }
        } else if (error.message) {
          errorMessage = error.message;
        }

        const enhancedError = new Error(
          `API Error (${error.response?.status || 'unknown'}): ${errorMessage}`
        );
        (enhancedError as { status?: number; originalError?: unknown }).status = error.response?.status;
        (enhancedError as { status?: number; originalError?: unknown }).originalError = error;
        
        return Promise.reject(enhancedError);
      }
    );
  }

  /**
   * Check if API client is ready (has Clerk token getter configured)
   */
  get isReady(): boolean {
    return this._isReady;
  }

  /**
   * Stream response from an endpoint (for SSE/streaming responses)
   */
  async stream(endpoint: string, data: unknown, token?: string, signal?: AbortSignal): Promise<Response> {
    const url = `${this.axiosInstance.defaults.baseURL}${endpoint}`;

    // Use provided token or get from Clerk
    const authToken = token || (this.getClerkToken ? await this.getClerkToken() : null);

    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      },
      body: JSON.stringify(data),
      signal,
    });
  }

  /**
   * Set Clerk token getter function
   * This should be called when Clerk is available
   */
  setClerkTokenGetter(getter: () => Promise<string | null>) {
    this.getClerkToken = getter;
    this._isReady = true;
  }

  // HTTP method shortcuts
  async get<T = unknown>(url: string, config?: RequestOptions): Promise<T> {
    const response = await this.axiosInstance.get<T>(url, config);
    return response.data;
  }

  async getBlob(url: string, config?: RequestOptions): Promise<Blob> {
    const response = await this.axiosInstance.get<Blob>(url, {
      ...config,
      responseType: 'blob',
    });
    return response.data;
  }

  async post<T = unknown>(url: string, data?: unknown, config?: RequestOptions): Promise<T> {
    const response = await this.axiosInstance.post<T>(url, data, config);
    return response.data;
  }

  async put<T = unknown>(url: string, data?: unknown, config?: RequestOptions): Promise<T> {
    const response = await this.axiosInstance.put<T>(url, data, config);
    return response.data;
  }

  async patch<T = unknown>(url: string, data?: unknown, config?: RequestOptions): Promise<T> {
    const response = await this.axiosInstance.patch<T>(url, data, config);
    return response.data;
  }

  async delete<T = unknown>(url: string, config?: RequestOptions): Promise<T> {
    const response = await this.axiosInstance.delete<T>(url, config);
    return response.data;
  }

  /**
   * Upload file with authentication
   */
  async uploadFile<T = unknown>(url: string, file: File, config?: RequestOptions): Promise<T> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await this.axiosInstance.post<T>(url, formData, {
      ...config,
      headers: {
        ...config?.headers,
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }
}

// Export singleton instance
export const apiClient = new ApiClient();
export default apiClient;
