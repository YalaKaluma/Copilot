import apiClient from '../../../shared/lib/api-client';
import type { Project, ProjectListItem, CreateProjectRequest, UpdateProjectRequest } from '../types/project.types';

class ProjectService {
  async listProjects(): Promise<ProjectListItem[]> {
    return apiClient.get<ProjectListItem[]>('/projects');
  }

  async getProject(id: string): Promise<Project> {
    return apiClient.get<Project>(`/projects/${id}`);
  }

  async createProject(data: CreateProjectRequest): Promise<Project> {
    return apiClient.post<Project>('/projects', data);
  }

  async updateProject(id: string, data: UpdateProjectRequest): Promise<Project> {
    return apiClient.patch<Project>(`/projects/${id}`, data);
  }

  async deleteProject(id: string): Promise<void> {
    await apiClient.delete(`/projects/${id}`);
  }
}

export const projectService = new ProjectService();
