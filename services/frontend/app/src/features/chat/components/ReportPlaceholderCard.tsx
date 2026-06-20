import { FileText } from 'lucide-react';

export function ReportPlaceholderCard() {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-white/10 flex items-center justify-center flex-shrink-0">
          <FileText className="w-5 h-5 text-sk-contrast-grey" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-sk-text mb-1">Executive Summary</h3>
          <p className="text-xs text-sk-contrast-grey leading-relaxed">
            Chat with SKAI to generate a CEO-level executive summary.
          </p>
        </div>
      </div>
    </div>
  );
}
