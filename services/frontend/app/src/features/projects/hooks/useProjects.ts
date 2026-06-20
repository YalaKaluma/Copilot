import { useState, useCallback } from 'react';
import { toast } from 'sonner';
import { logger } from '../../../shared/lib/logger';
import { projectService } from '../services/projectService';
import type { Project, ProjectListItem, CreateProjectRequest, UpdateProjectRequest } from '../types/project.types';

const log = logger.create('Projects');

interface UseProjectsReturn {
  projects: ProjectListItem[];
  isLoading: boolean;
  fetchProjects: () => Promise<void>;
  getProject: (id: string) => Promise<Project | null>;
  createProject: (data: CreateProjectRequest) => Promise<Project | null>;
  updateProject: (id: string, data: UpdateProjectRequest) => Promise<Project | null>;
  deleteProject: (id: string) => Promise<boolean>;
}

export function useProjects(): UseProjectsReturn {
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchProjects = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await projectService.listProjects();
      setProjects(data);
    } catch (error) {
      log.error('Failed to fetch projects:', error);
      toast.error('Failed to load projects');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const getProject = useCallback(async (id: string): Promise<Project | null> => {
    try {
      return await projectService.getProject(id);
    } catch (error) {
      log.error('Failed to load project:', error);
      toast.error('Failed to load project');
      return null;
    }
  }, []);

  const createProject = useCallback(async (data: CreateProjectRequest): Promise<Project | null> => {
    try {
      const project = await projectService.createProject(data);
      setProjects((prev) => [project, ...prev]);
      toast.success('Project created');
      return project;
    } catch (error) {
      log.error('Failed to create project:', error);
      toast.error('Failed to create project');
      return null;
    }
  }, []);

  const updateProject = useCallback(async (id: string, data: UpdateProjectRequest): Promise<Project | null> => {
    try {
      const project = await projectService.updateProject(id, data);
      setProjects((prev) =>
        prev.map((p) => (p.id === id ? { ...p, ...project } : p))
      );
      toast.success('Project updated');
      return project;
    } catch (error) {
      log.error('Failed to update project:', error);
      toast.error('Failed to update project');
      return null;
    }
  }, []);

  const deleteProject = useCallback(async (id: string): Promise<boolean> => {
    try {
      await projectService.deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
      toast.success('Project deleted');
      return true;
    } catch (error) {
      log.error('Failed to delete project:', error);
      toast.error('Failed to delete project');
      return false;
    }
  }, []);

  return {
    projects,
    isLoading,
    fetchProjects,
    getProject,
    createProject,
    updateProject,
    deleteProject,
  };
}
