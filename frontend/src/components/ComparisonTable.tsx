import React from 'react';
import { Star, TrendingUp, TrendingDown, Minus, ArrowRight, Award, AlertTriangle, ShieldCheck } from 'lucide-react';
import { BusinessLeaderboardEntry } from '../types';

interface ComparisonTableProps {
  entries: BusinessLeaderboardEntry[];
  weekLabel: string;
  categoryLabel: string;
  onSelectBusiness: (businessId: string) => void;
}

export const ComparisonTable: React.FC<ComparisonTableProps> = ({
  entries,
  weekLabel,
  categoryLabel,
  onSelectBusiness,
}) => {
  return (
    <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-xs p-4 sm:p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Award className="w-5 h-5 text-amber-500" />
            <h2 className="text-lg font-extrabold text-slate-900 dark:text-white">
              Classement comparatif · {categoryLabel}
            </h2>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
            Comparaison multi-établissements pour la {weekLabel}
          </p>
        </div>
        <span className="text-xs font-semibold px-3 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 self-start sm:self-auto">
          {entries.length} établissements surveillés
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs sm:text-sm">
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-800 text-[11px] uppercase tracking-wider text-slate-600 dark:text-slate-400">
              <th className="py-3 px-3 font-bold">Rang</th>
              <th className="py-3 px-3 font-bold">Établissement</th>
              <th className="py-3 px-3 font-bold text-center">Note Google</th>
              <th className="py-3 px-3 font-bold text-center">Avis W42</th>
              <th className="py-3 px-3 font-bold text-center">% Positifs</th>
              <th className="py-3 px-3 font-bold text-center">Tendance</th>
              <th className="py-3 px-3 font-bold">Thème le plus problématique</th>
              <th className="py-3 px-3 font-bold text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
            {entries.map((entry, index) => {
              const isTop = index === 0;

              return (
                <tr
                  key={entry.business.id}
                  className="hover:bg-slate-50/80 dark:hover:bg-slate-800/50 transition duration-150"
                >
                  {/* Rank */}
                  <td className="py-3 px-3 whitespace-nowrap">
                    <span
                      className={`w-6 h-6 rounded-full inline-flex items-center justify-center font-extrabold text-xs ${
                        isTop
                          ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 ring-2 ring-amber-400'
                          : index === 1
                          ? 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200'
                          : index === 2
                          ? 'bg-amber-50 text-amber-900 border border-amber-300'
                          : 'text-slate-600 dark:text-slate-400'
                      }`}
                    >
                      {index + 1}
                    </span>
                  </td>

                  {/* Business Name & City */}
                  <td className="py-3 px-3">
                    <div className="font-bold text-slate-900 dark:text-white leading-tight">
                      {entry.business.name}
                    </div>
                    <div className="text-[11px] text-slate-600 dark:text-slate-400">
                      {entry.business.city}
                    </div>
                  </td>

                  {/* Google Rating */}
                  <td className="py-3 px-3 text-center whitespace-nowrap">
                    <div className="inline-flex items-center gap-1 font-bold text-slate-900 dark:text-white">
                      <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-500" />
                      <span>{entry.business.rating.toFixed(1).replace('.', ',')}</span>
                    </div>
                    <div className="text-[10px] text-slate-600 dark:text-slate-400">
                      {entry.business.totalReviews.toLocaleString('fr-FR')} total
                    </div>
                  </td>

                  {/* Reviews this week */}
                  <td className="py-3 px-3 text-center whitespace-nowrap font-semibold text-slate-800 dark:text-slate-200">
                    {entry.nb_avis}
                  </td>

                  {/* % Positifs with Bar */}
                  <td className="py-3 px-3 text-center whitespace-nowrap">
                    <div className="font-extrabold text-emerald-800 dark:text-emerald-300">
                      {entry.pct_positifs}%
                    </div>
                    <div className="w-20 mx-auto bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden mt-1">
                      <div
                        className="bg-emerald-500 h-full rounded-full"
                        style={{ width: `${entry.pct_positifs}%` }}
                      />
                    </div>
                  </td>

                  {/* Trend */}
                  <td className="py-3 px-3 text-center whitespace-nowrap">
                    {entry.variation_pts !== null ? (
                      <span
                        className={`inline-flex items-center gap-1 font-bold text-xs ${
                          entry.variation_pts > 0
                            ? 'text-emerald-800 dark:text-emerald-300'
                            : entry.variation_pts < 0
                            ? 'text-rose-800 dark:text-rose-300'
                            : 'text-slate-600 dark:text-slate-400'
                        }`}
                      >
                        {entry.variation_pts > 0 ? (
                          <TrendingUp className="w-3.5 h-3.5" />
                        ) : entry.variation_pts < 0 ? (
                          <TrendingDown className="w-3.5 h-3.5" />
                        ) : (
                          <Minus className="w-3 h-3" />
                        )}
                        {entry.variation_pts > 0 ? `+${entry.variation_pts}` : entry.variation_pts} pts
                      </span>
                    ) : (
                      <span className="text-slate-600 dark:text-slate-400 text-xs">—</span>
                    )}
                  </td>

                  {/* Most problematic theme */}
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-1.5 text-xs text-rose-800 dark:text-rose-300 font-semibold">
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-rose-500" />
                      <span className="truncate max-w-[170px]">{entry.top_probleme}</span>
                    </div>
                    <div className="flex items-center gap-1 text-[11px] text-emerald-800 dark:text-emerald-300 mt-0.5">
                      <ShieldCheck className="w-3 h-3 shrink-0 text-emerald-500" />
                      <span className="truncate max-w-[170px]">{entry.top_force}</span>
                    </div>
                  </td>

                  {/* Action */}
                  <td className="py-3 px-3 text-right whitespace-nowrap">
                    <button
                      type="button"
                      onClick={() => onSelectBusiness(entry.business.id)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-slate-900 text-white dark:bg-emerald-600 dark:hover:bg-emerald-500 hover:bg-slate-800 text-xs font-bold transition cursor-pointer shadow-xs"
                    >
                      <span>Voir le détail</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
