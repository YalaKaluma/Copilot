import type { ChartItem } from '../types/chart.types';

const CHART_COLORS = [
  'hsl(0, 70%, 55%)',
  'hsl(220, 60%, 55%)',
  'hsl(150, 50%, 45%)',
  'hsl(40, 80%, 50%)',
  'hsl(280, 55%, 55%)',
  'hsl(180, 55%, 45%)',
  'hsl(25, 75%, 55%)',
  'hsl(320, 50%, 55%)',
];

function formatValue(v: number): string {
  return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export interface ChartRendererProps {
  chart: ChartItem;
  height?: number;
}

export function ChartRenderer({ chart, height = 220 }: ChartRendererProps) {
  const { data, chartType } = chart;

  if (data.length === 0) {
    return (
      <p className="text-xs text-sk-contrast-grey py-4 text-center">No data</p>
    );
  }

  const maxVal = Math.max(...data.map((d) => d.value), 1);

  if (chartType === 'line') {
    const padding = { top: 24, right: 8, bottom: 28, left: 36 };
    const w = 280;
    const h = height - padding.top - padding.bottom;
    const minV = Math.min(...data.map((d) => d.value));
    const range = Math.max(...data.map((d) => d.value)) - minV || 1;
    const points = data.map((d, i) => {
      const x = padding.left + (i / Math.max(data.length - 1, 1)) * (w - padding.left - padding.right);
      const y = padding.top + h - ((d.value - minV) / range) * h;
      return `${x},${y}`;
    });
    const pathD = `M ${points.join(' L ')}`;

    return (
      <div className="w-full" style={{ height }}>
        <svg width="100%" height={height} viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="xMidYMid meet" className="overflow-visible">
          <path d={pathD} fill="none" stroke={CHART_COLORS[0]} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          {data.map((d, i) => {
            const x = padding.left + (i / Math.max(data.length - 1, 1)) * (w - padding.left - padding.right);
            const y = padding.top + h - ((d.value - minV) / range) * h;
            return (
              <g key={i}>
                <circle cx={x} cy={y} r={3} fill={CHART_COLORS[0]} />
                <text x={x} y={height - 6} textAnchor="middle" className="fill-[hsl(0,0%,60%)] text-[10px]">{d.label}</text>
              </g>
            );
          })}
        </svg>
      </div>
    );
  }

  if (chartType === 'pie') {
    const total = data.reduce((s, d) => s + d.value, 0) || 1;
    let acc = 0;
    const segments = data.map((d, i) => {
      const pct = d.value / total;
      const start = acc;
      acc += pct;
      return { label: d.label, value: d.value, pct: (pct * 100).toFixed(0), start: start * 100, color: CHART_COLORS[i % CHART_COLORS.length] };
    });
    const r = 72;
    const cx = 100;
    const cy = height / 2;
    const circumference = 2 * Math.PI * r;

    return (
      <div className="w-full flex flex-col items-center gap-2" style={{ height }}>
        <svg width="200" height={height - 48} viewBox={`0 0 200 ${height - 48}`} className="flex-shrink-0">
          <g transform={`translate(${cx}, ${cy})`}>
            {segments.map((seg, i) => (
              <circle
                key={i}
                r={r}
                fill="none"
                stroke={seg.color}
                strokeWidth={r * 1.6}
                strokeDasharray={`${(seg.value / total) * circumference} ${circumference}`}
                strokeDashoffset={-(seg.start / 100) * circumference}
                transform="rotate(-90)"
              />
            ))}
          </g>
        </svg>
        <div className="flex flex-wrap justify-center gap-x-3 gap-y-1 text-xs">
          {segments.map((seg, i) => (
            <span key={i} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: seg.color }} />
              <span className="text-sk-text">{seg.label}</span>
              <span className="text-sk-contrast-grey">{seg.pct}%</span>
            </span>
          ))}
        </div>
      </div>
    );
  }

  // bar (default)
  return (
    <div className="w-full space-y-2" style={{ minHeight: height }}>
      {data.map((d, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="text-xs text-sk-text truncate w-24 flex-shrink-0" title={d.label}>{d.label}</span>
          <div className="flex-1 min-w-0 h-6 rounded bg-gray-200 dark:bg-white/10 overflow-hidden">
            <div
              className="h-full rounded bg-sk-accent-red transition-[width]"
              style={{ width: `${Math.min(100, (d.value / maxVal) * 100)}%` }}
            />
          </div>
          <span className="text-xs text-sk-contrast-grey tabular-nums w-14 text-right flex-shrink-0">{formatValue(d.value)}</span>
        </div>
      ))}
    </div>
  );
}
