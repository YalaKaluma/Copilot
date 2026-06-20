import apiClient from '../../../shared/lib/api-client';
import type {
  TemplateListItem,
  TemplateDetail,
  CreateTemplateRequest,
  UpdateTemplateRequest,
} from '../types/template.types';

class TemplateService {
  async fetchTemplates(): Promise<TemplateListItem[]> {
    return apiClient.get<TemplateListItem[]>('/templates');
  }

  async fetchTemplate(id: string): Promise<TemplateDetail> {
    return apiClient.get<TemplateDetail>(`/templates/${id}`);
  }

  async createTemplate(data: CreateTemplateRequest): Promise<TemplateDetail> {
    return apiClient.post<TemplateDetail>('/templates', data);
  }

  async updateTemplate(id: string, data: UpdateTemplateRequest): Promise<TemplateDetail> {
    return apiClient.patch<TemplateDetail>(`/templates/${id}`, data);
  }

  async deleteTemplate(id: string): Promise<void> {
    await apiClient.delete(`/templates/${id}`);
  }
}

export const templateService = new TemplateService();
