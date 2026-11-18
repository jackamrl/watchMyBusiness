import React from 'react';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';

export interface WeekOption {
  id: string;
  label: string;
  dates: string;
}

interface WeekSelectorProps {
  currentWeekId: string;
  onSelectWeek: (weekId: string) => void;
  weeks: WeekOption[];
  reviewCount?: number;
}

export const WeekSelector: React.FC<WeekSelectorProps> = ({
  currentWeekId,
  onSelectWeek,
  weeks,
  reviewCount,
}) => {
  const currentIndex = weeks.findIndex((w) => w.id === currentWeekId);
  const currentWeek = weeks[currentIndex] || weeks[0];

  const hasNext = currentIndex > 0;
  const hasPrev = currentIndex >= 0 && currentIndex < weeks.length - 1;

  if (!currentWeek) {
    return (
      <div className="text-xs text-slate-500 px-3 py-2 border rounded-xl">Aucune semaine</div>
    );
  }

  return (
    <div className="flex items-center gap-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-1 shadow-xs">
      <button
        type="button"
        onClick={() => hasPrev && onSelectWeek(weeks[currentIndex + 1].id)}
        disabled={!hasPrev}
        aria-label="Semaine précédente"
        className="p-1.5 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>

      <div className="flex items-center gap-2 px-2 min-w-[160px]">
        <Calendar className="w-3.5 h-3.5 text-slate-400" />
        <div className="leading-tight">
          <div className="text-xs font-bold text-slate-900 dark:text-white">{currentWeek.label}</div>
          <div className="text-[10px] text-slate-500 dark:text-slate-400">{currentWeek.dates}</div>
        </div>
        {reviewCount != null && (
          <span className="ml-auto text-[10px] font-semibold text-slate-500">{reviewCount} avis</span>
        )}
      </div>

      <button
        type="button"
        onClick={() => hasNext && onSelectWeek(weeks[currentIndex - 1].id)}
        disabled={!hasNext}
        aria-label="Semaine suivante"
        className="p-1.5 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed"
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
};
