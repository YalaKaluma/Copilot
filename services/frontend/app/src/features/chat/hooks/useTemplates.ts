import { useState, useCallback, useRef } from 'react';
import { templateService } from '../services/templateService';
import type {
  TemplateListItem,
  TemplateDetail,
  CreateTemplateRequest,
  UpdateTemplateRequest,
} from '../types/template.types';

interface UseTemplatesReturn {
  templates: TemplateListItem[];
  activeTemplate: TemplateDetail | null;
  isLoading: boolean;
  fetchTemplates: () => Promise<void>;
  selectTemplate: (id: string) => Promise<void>;
  clearActiveTemplate: () => void;
  createTemplate: (data: CreateTemplateRequest) => Promise<TemplateDetail>;
  updateTemplate: (id: string, data: UpdateTemplateRequest) => Promise<TemplateDetail>;
  deleteTemplate: (id: string) => Promise<void>;
}

export function useTemplates(): UseTemplatesReturn {
  const [templates, setTemplates] = useState<TemplateListItem[]>([]);
  const [activeTemplate, setActiveTemplate] = useState<TemplateDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const templatesRequestVersion = useRef(0);

  const fetchTemplates = useCallback(async () => {
    const requestVersion = ++templatesRequestVersion.current;
    setIsLoading(true);
    try {
      const data = await templateService.fetchTemplates();
      if (requestVersion === templatesRequestVersion.current) {
        setTemplates(data);
      }
    } catch (err) {
      console.warn('Failed to fetch templates:', err);
    } finally {
      if (requestVersion === templatesRequestVersion.current) {
        setIsLoading(false);
      }
    }
  }, []);

  const selectTemplate = useCallback(async (id: string) => {
    try {
      const detail = await templateService.fetchTemplate(id);
      setActiveTemplate(detail);
    } catch (err) {
      console.warn('Failed to fetch template:', err);
    }
  }, []);

  const clearActiveTemplate = useCallback(() => {
    setActiveTemplate(null);
  }, []);

  const createTemplate = useCallback(async (data: CreateTemplateRequest): Promise<TemplateDetail> => {
    try {
      const created = await templateService.createTemplate(data);
      // Invalidate older in-flight list requests so they don't overwrite fresh local state.
      setIsLoading(false);
      templatesRequestVersion.current += 1;
      setTemplates((prev) => [
        { id: created.id, name: created.name, description: created.description, isDefault: created.isDefault, createdAt: created.createdAt, updatedAt: created.updatedAt },
        ...prev.map((t) => (data.isDefault ? { ...t, isDefault: false } : t)),
      ]);
      return created;
    } catch (err) {
      console.warn('Failed to create template:', err);
      throw err;
    }
  }, []);

  const updateTemplate = useCallback(async (id: string, data: UpdateTemplateRequest): Promise<TemplateDetail> => {
    try {
      const updated = await templateService.updateTemplate(id, data);
      // Invalidate older in-flight list requests so they don't overwrite fresh local state.
      setIsLoading(false);
      templatesRequestVersion.current += 1;
      setTemplates((prev) =>
        prev.map((t) => {
          if (t.id === id) return { ...t, name: updated.name, description: updated.description, isDefault: updated.isDefault, updatedAt: updated.updatedAt };
          if (data.isDefault) return { ...t, isDefault: false };
          return t;
        })
      );
      if (activeTemplate?.id === id) {
        setActiveTemplate(updated);
      }
      return updated;
    } catch (err) {
      console.warn('Failed to update template:', err);
      throw err;
    }
  }, [activeTemplate]);

  const deleteTemplate = useCallback(async (id: string) => {
    // Invalidate older in-flight list requests so they don't overwrite fresh local state.
    setIsLoading(false);
    templatesRequestVersion.current += 1;
    // Optimistic remove
    setTemplates((prev) => prev.filter((t) => t.id !== id));
    if (activeTemplate?.id === id) {
      setActiveTemplate(null);
    }
    try {
      await templateService.deleteTemplate(id);
    } catch (err) {
      console.warn('Failed to delete template:', err);
      // Re-fetch to restore
      fetchTemplates();
    }
  }, [activeTemplate, fetchTemplates]);

  return {
    templates,
    activeTemplate,
    isLoading,
    fetchTemplates,
    selectTemplate,
    clearActiveTemplate,
    createTemplate,
    updateTemplate,
    deleteTemplate,
  };
}
