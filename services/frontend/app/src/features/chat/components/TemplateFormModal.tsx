import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { motion } from 'motion/react';
import type { TemplateDetail, CreateTemplateRequest, UpdateTemplateRequest } from '../types/template.types';

interface TemplateFormModalProps {
  template?: TemplateDetail | null;
  onSave: (data: CreateTemplateRequest | UpdateTemplateRequest) => Promise<void>;
  onClose: () => void;
}

export function TemplateFormModal({ template, onSave, onClose }: TemplateFormModalProps) {
  const [name, setName] = useState(template?.name || '');
  const [description, setDescription] = useState(template?.description || '');
  const [content, setContent] = useState(template?.content || '');
  const [isDefault, setIsDefault] = useState(template?.isDefault || false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setName(template?.name || '');
    setDescription(template?.description || '');
    setContent(template?.content || '');
    setIsDefault(template?.isDefault || false);
  }, [template]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  const clearError = () => { if (error) setError(null); };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    const trimmedContent = content.trim();

    if (!trimmedName || !trimmedContent) return;

    setIsSaving(true);
    setError(null);

    try {
      if (!template) {
        await onSave({
          name: trimmedName,
          description: description.trim() || undefined,
          content: trimmedContent,
          isDefault,
        } as CreateTemplateRequest);
      } else {
        await onSave({
          name: trimmedName,
          description: description.trim() || null,
          content: trimmedContent,
          isDefault,
        } as UpdateTemplateRequest);
      }
    } catch {
      setError(template ? 'Failed to update template. Please try again.' : 'Failed to create template. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.15 }}
        className="relative bg-sk-white rounded-xl border border-gray-200 dark:border-white/10 shadow-xl w-full max-w-lg mx-4"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-white/10">
          <h3 className="text-sm font-semibold text-sk-text">
            {template ? 'Edit Template' : 'Create Template'}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-white/10 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-600 dark:text-gray-300">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => { setName(e.target.value); clearError(); }}
              maxLength={100}
              required
              className="w-full rounded-lg border border-gray-200 dark:border-white/10 bg-sk-white px-3 py-2 text-sm text-sk-text outline-none transition placeholder-gray-400 focus:border-sk-accent-red focus:ring-1 focus:ring-sk-accent-red/30"
              placeholder="Template name"
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-600 dark:text-gray-300">Description <span className="text-gray-400">(optional)</span></label>
            <input
              type="text"
              value={description}
              onChange={(e) => { setDescription(e.target.value); clearError(); }}
              maxLength={255}
              className="w-full rounded-lg border border-gray-200 dark:border-white/10 bg-sk-white px-3 py-2 text-sm text-sk-text outline-none transition placeholder-gray-400 focus:border-sk-accent-red focus:ring-1 focus:ring-sk-accent-red/30"
              placeholder="Short description"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-600 dark:text-gray-300">Content</label>
            <textarea
              value={content}
              onChange={(e) => { setContent(e.target.value); clearError(); }}
              required
              rows={6}
              className="w-full rounded-lg border border-gray-200 dark:border-white/10 bg-sk-white px-3 py-2 text-sm text-sk-text outline-none transition placeholder-gray-400 focus:border-sk-accent-red focus:ring-1 focus:ring-sk-accent-red/30 resize-none"
              placeholder="Template instructions that will be appended to your message..."
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={isDefault}
              onChange={(e) => { setIsDefault(e.target.checked); clearError(); }}
              className="rounded border-gray-300 text-sk-accent-red focus:ring-sk-accent-red/30"
            />
            <span className="text-xs text-gray-600 dark:text-gray-300">Set as default template</span>
          </label>

          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="px-4 py-2 rounded-lg text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-white/10 transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || !content.trim() || isSaving}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-sk-accent-red hover:bg-sk-accent-red/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
            >
              {isSaving ? 'Saving...' : template ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </motion.div>
    </div>,
    document.body
  );
}
