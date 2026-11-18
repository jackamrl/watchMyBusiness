import React from 'react';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import { WEEKS_LIST } from '../data/donnees';

interface WeekSelectorProps {
  currentWeekId: string;
  onSelectWeek: (weekId: string) => void;
  reviewCount?: number;
}

export const WeekSelector: React.FC<WeekSelectorProps> = ({
  currentWeekId,
  onSelectWeek,
  reviewCount,
}) => {
  const currentIndex = WEEKS_LIST.findIndex((w) => w.id === currentWeekId);
  const currentWeek = WEEKS_LIST[currentIndex] || WEEKS_LIST[0];

  const hasNext = currentIndex > 0; // closer to current (W42 is index 0)
  const hasPrev = currentIndex < WEEKS_LIST.length - 1; // older

  const handlePrev = () => {
    if (hasPrev) {
      onSelectWeek(WEEKS_LIST[currentIndex + 1].id);
    }
  };

  const handleNext = () => {
    if (hasNext) {
      onSelectWeek(WEEKS_LIST[currentIndex - 1].id);
    }
  };

  return (
    <div className="flex items-center gap-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-1 shadow-xs">
      <button
        type="button"
        onClick={handlePrev}
        disabled={!hasPrev}
        aria-label="Semaine précédente"
        title="Semaine précédente"
        className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition cursor-pointer"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>

      <div className="flex items-center gap-2 px-2.5 py-0.5">
        <Calendar className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
        <div className="flex flex-col text-left">
          <span className="text-xs font-bold text-slate-900 dark:text-white leading-tight">
            {currentWeek.id}
            {reviewCount !== undefined && (
              <span className="font-normal text-slate-600 dark:text-slate-400 ml-1.5">
                · {reviewCount} avis
              </span>
            )}
          </span>
          <span className="text-[10px] text-slate-600 dark:text-slate-400 leading-tight">
            {currentWeek.dates}
          </span>
        </div>
      </div>

      <button
        type="button"
        onClick={handleNext}
        disabled={!hasNext}
        aria-label="Semaine suivante"
        title="Semaine suivante"
        className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition cursor-pointer"
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
};
