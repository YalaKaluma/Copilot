import { BarChart3 } from 'lucide-react';
import type { ChartItem } from '../types/chart.types';
import { ChartRenderer } from './ChartRenderer';

export interface ChartsPanelProps {
  charts: ChartItem[];
}

export function ChartsPanel({ charts }: ChartsPanelProps) {
  if (charts.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white p-6 text-center">
        <p className="text-sm text-sk-contrast-grey">
          Charts from your conversation will appear here.
        </p>
        <p className="text-xs text-sk-contrast-grey mt-2">
          Send a message to generate charts.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {charts.map((chart) => (
        <div
          key={chart.id}
          className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white p-4 shadow-sm"
        >
          <div className="flex items-start gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-white/10 flex items-center justify-center flex-shrink-0">
              <BarChart3 className="w-5 h-5 text-sk-contrast-grey" />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-semibold text-sk-text">{chart.title}</h3>
              <p className="text-xs text-sk-contrast-grey mt-0.5 capitalize">
                {chart.chartType} chart
              </p>
            </div>
          </div>
          <div className="min-h-[200px]">
            <ChartRenderer chart={chart} height={220} />
          </div>
        </div>
      ))}
    </div>
  );
}
