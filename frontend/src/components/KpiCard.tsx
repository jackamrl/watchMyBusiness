import React from 'react';
import { LucideIcon } from 'lucide-react';

interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  badge?: {
    text: string;
    variant: 'positive' | 'negative' | 'neutral' | 'mixed' | 'info';
  };
  sparklineData: (number | null)[];
  color: 'emerald' | 'coral' | 'amber' | 'indigo';
  icon: LucideIcon;
}

export const KpiCard: React.FC<KpiCardProps> = ({
  title,
  value,
  subtitle,
  badge,
  sparklineData,
  color,
  icon: Icon,
}) => {
  const colorStyles = {
    emerald: {
      text: 'text-emerald-800 dark:text-emerald-300',
      bgLight: 'bg-emerald-50 dark:bg-emerald-950/40',
      stroke: '#059669',
      border: 'border-emerald-100 dark:border-emerald-900/40',
      badge: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-300',
    },
    coral: {
      text: 'text-rose-800 dark:text-rose-300',
      bgLight: 'bg-rose-50 dark:bg-rose-950/40',
      stroke: '#e11d48',
      border: 'border-rose-100 dark:border-rose-900/40',
      badge: 'bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-300',
    },
    amber: {
      text: 'text-amber-800 dark:text-amber-300',
      bgLight: 'bg-amber-50 dark:bg-amber-950/40',
      stroke: '#d97706',
      border: 'border-amber-100 dark:border-amber-900/40',
      badge: 'bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-300',
    },
    indigo: {
      text: 'text-indigo-800 dark:text-indigo-300',
      bgLight: 'bg-indigo-50 dark:bg-indigo-950/40',
      stroke: '#4f46e5',
      border: 'border-indigo-100 dark:border-indigo-900/40',
      badge: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/60 dark:text-indigo-300',
    },
  }[color];

  // Generate SVG sparkline path
  const validData = sparklineData.filter((d): d is number => d !== null);
  const minVal = validData.length > 0 ? Math.min(...validData) : 0;
  const maxVal = validData.length > 0 ? Math.max(...validData) : 100;
  const range = maxVal - minVal || 1;

  const width = 96;
  const height = 32;
  const padding = 2;

  const points = sparklineData.map((d, i) => {
    if (d === null) return null;
    const x = padding + (i / Math.max(sparklineData.length - 1, 1)) * (width - 2 * padding);
    const y = height - padding - ((d - minVal) / range) * (height - 2 * padding);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  // Build SVG path with gap handling
  let pathD = '';
  let isDrawing = false;
  points.forEach((pt) => {
    if (pt === null) {
      isDrawing = false;
    } else {
      if (!isDrawing) {
        pathD += ` M ${pt}`;
        isDrawing = true;
      } else {
        pathD += ` L ${pt}`;
      }
    }
  });

  return (
    <div className={`p-4 rounded-2xl bg-white dark:bg-slate-900 border ${colorStyles.border} shadow-xs hover:shadow-md transition-all duration-200 group flex flex-col justify-between`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-600 dark:text-slate-400">
          {title}
        </span>
        <div className={`w-7 h-7 rounded-lg ${colorStyles.bgLight} ${colorStyles.text} flex items-center justify-center shrink-0`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>

      <div className="flex items-end justify-between mt-2.5">
        <div>
          <div className={`text-2xl sm:text-3xl font-extrabold tracking-tight ${colorStyles.text}`}>
            {value}
          </div>
          {subtitle && (
            <div className="text-[11px] text-slate-600 dark:text-slate-400 mt-0.5">
              {subtitle}
            </div>
          )}
        </div>

        {/* Mini sparkline */}
        <div className="flex flex-col items-end">
          <svg
            width={width}
            height={height}
            className="overflow-visible"
            aria-label={`Mini-courbe tendance ${title}`}
          >
            {/* Background baseline */}
            <line
              x1={0}
              y1={height - 2}
              x2={width}
              y2={height - 2}
              stroke="currentColor"
              className="text-slate-200 dark:text-slate-800"
              strokeDasharray="2 2"
            />
            {/* Sparkline curve */}
            <path
              d={pathD}
              fill="none"
              stroke={colorStyles.stroke}
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="text-[9px] text-slate-600 dark:text-slate-400 tracking-tight mt-0.5">
            12 dernières semaines
          </span>
        </div>
      </div>

      {badge && (
        <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between">
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${colorStyles.badge}`}>
            {badge.text}
          </span>
        </div>
      )}
    </div>
  );
};
