import React from 'react';
import { AlertCircle, CheckCircle2, TrendingUp, TrendingDown, Minus, Quote, Filter } from 'lucide-react';
import { ThemeMetric } from '../types';

interface ThemeColumnProps {
  type: 'negative' | 'positive';
  themes: ThemeMetric[];
  activeFilterTheme: string | null;
  onSelectThemeFilter: (theme: string | null) => void;
}

export const ThemeColumn: React.FC<ThemeColumnProps> = ({
  type,
  themes,
  activeFilterTheme,
  onSelectThemeFilter,
}) => {
  const isNegative = type === 'negative';

  const styles = isNegative
    ? {
        title: 'Ce qui a posé problème',
        subtitle: 'Principaux motifs d’irritation repérés par notre modèle NLP',
        icon: AlertCircle,
        headerBg: 'bg-rose-50/70 dark:bg-rose-950/30 text-rose-800 dark:text-rose-300 border-rose-200/80 dark:border-rose-900/50',
        barColor: 'bg-rose-500',
        pillBg: 'bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-200',
        activeCard: 'ring-2 ring-rose-500 bg-rose-50/40 dark:bg-rose-950/20',
        quoteColor: 'text-rose-600 dark:text-rose-400',
        arrowUp: 'text-rose-600', // for problems, an increase is bad
        arrowDown: 'text-emerald-600', // for problems, a decrease is good
      }
    : {
        title: 'Ce qui a bien fonctionné',
        subtitle: 'Points forts plébiscités dans les avis positifs',
        icon: CheckCircle2,
        headerBg: 'bg-emerald-50/70 dark:bg-emerald-950/30 text-emerald-800 dark:text-emerald-300 border-emerald-200/80 dark:border-emerald-900/50',
        barColor: 'bg-emerald-500',
        pillBg: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-200',
        activeCard: 'ring-2 ring-emerald-500 bg-emerald-50/40 dark:bg-emerald-950/20',
        quoteColor: 'text-emerald-600 dark:text-emerald-400',
        arrowUp: 'text-emerald-600',
        arrowDown: 'text-amber-600',
      };

  const HeaderIcon = styles.icon;

  return (
    <div className="flex flex-col h-full rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-xs p-4 sm:p-5">
      {/* Column Header */}
      <div className={`flex items-start justify-between p-3 rounded-xl border ${styles.headerBg} mb-4`}>
        <div className="flex items-center gap-2.5">
          <HeaderIcon className="w-5 h-5 shrink-0" />
          <div>
            <h3 className="text-sm font-extrabold tracking-tight">
              {styles.title}
            </h3>
            <p className="text-[11px] opacity-85 leading-tight mt-0.5">
              {styles.subtitle}
            </p>
          </div>
        </div>
        <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-white/80 dark:bg-slate-900/80 shadow-xs">
          {themes.length} thèmes
        </span>
      </div>

      {/* Themes List */}
      <div className="space-y-3 flex-1 overflow-y-auto">
        {themes.map((item) => {
          const isActive = activeFilterTheme === item.theme;

          return (
            <div
              key={item.theme}
              onClick={() => onSelectThemeFilter(isActive ? null : item.theme)}
              className={`p-3.5 rounded-xl border border-slate-200/90 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 hover:bg-slate-100/70 dark:hover:bg-slate-800/80 transition cursor-pointer group ${
                isActive ? styles.activeCard : ''
              }`}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  onSelectThemeFilter(isActive ? null : item.theme);
                }
              }}
              title="Cliquer pour filtrer les avis sur ce thème"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs sm:text-sm font-bold text-slate-900 dark:text-white">
                    {item.libelle}
                  </span>
                  {isActive && (
                    <span className="flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded-md bg-slate-900 text-white dark:bg-white dark:text-slate-900">
                      <Filter className="w-2.5 h-2.5" />
                      Filtré
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {/* Variation arrow vs previous week */}
                  {item.variation_pts !== undefined && (
                    <span
                      className={`flex items-center text-[11px] font-bold ${
                        item.variation_pts > 0 ? styles.arrowUp : styles.arrowDown
                      }`}
                      title={`${item.variation_pts > 0 ? '+' : ''}${item.variation_pts} pts vs semaine précédente`}
                    >
                      {item.variation_pts > 0 ? (
                        <TrendingUp className="w-3.5 h-3.5 mr-0.5" />
                      ) : item.variation_pts < 0 ? (
                        <TrendingDown className="w-3.5 h-3.5 mr-0.5" />
                      ) : (
                        <Minus className="w-3 h-3 text-slate-400 mr-0.5" />
                      )}
                      {item.variation_pts > 0 ? `+${item.variation_pts}` : item.variation_pts} pts
                    </span>
                  )}

                  <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md ${styles.pillBg}`}>
                    {item.occurrences} avis ({item.pourcentage}%)
                  </span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden mt-2">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${styles.barColor}`}
                  style={{ width: `${Math.min(item.pourcentage, 100)}%` }}
                />
              </div>

              {/* Two customer quotes */}
              {item.citations && item.citations.length > 0 && (
                <div className="mt-2.5 space-y-1.5 pt-2 border-t border-slate-200/60 dark:border-slate-700/50">
                  {item.citations.slice(0, 2).map((quote, qIdx) => (
                    <div
                      key={qIdx}
                      className="text-[11px] text-slate-600 dark:text-slate-400 italic flex items-start gap-1.5 leading-snug"
                    >
                      <Quote className={`w-3 h-3 shrink-0 mt-0.5 ${styles.quoteColor}`} />
                      <span>« {quote} »</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}

        {themes.length === 0 && (
          <div className="p-6 text-center text-xs text-slate-400 italic bg-slate-50 dark:bg-slate-800/40 rounded-xl">
            Aucun thème spécifique identifié sur cette période.
          </div>
        )}
      </div>

      <div className="mt-3 text-right">
        <span className="text-[10px] text-slate-400 dark:text-slate-500">
          Astuce : cliquez sur un thème pour isoler les avis correspondants ci-dessous
        </span>
      </div>
    </div>
  );
};
