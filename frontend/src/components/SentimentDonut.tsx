import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { Smile, Frown, Meh, HelpCircle } from 'lucide-react';

interface SentimentDonutProps {
  repartition: {
    POSITIVE: number;
    NEGATIVE: number;
    NEUTRAL: number;
    MIXED: number;
  };
  totalAvis: number;
}

export const SentimentDonut: React.FC<SentimentDonutProps> = ({
  repartition,
  totalAvis,
}) => {
  const data = [
    {
      name: 'Positifs',
      key: 'POSITIVE',
      value: repartition.POSITIVE,
      color: '#059669', // Emerald
      icon: Smile,
      badgeText: 'Avis positifs',
    },
    {
      name: 'Négatifs',
      key: 'NEGATIVE',
      value: repartition.NEGATIVE,
      color: '#e11d48', // Coral red
      icon: Frown,
      badgeText: 'Avis négatifs',
    },
    {
      name: 'Neutres',
      key: 'NEUTRAL',
      value: repartition.NEUTRAL,
      color: '#64748b', // Slate
      icon: Meh,
      badgeText: 'Avis neutres',
    },
    {
      name: 'Mitigés',
      key: 'MIXED',
      value: repartition.MIXED,
      color: '#d97706', // Amber
      icon: HelpCircle,
      badgeText: 'Avis mitigés',
    },
  ].filter((item) => item.value > 0);

  // If no reviews at all
  const chartData = data.length > 0 ? data : [{ name: 'Aucun avis', value: 1, color: '#e2e8f0', key: 'NONE', icon: Meh, badgeText: 'Aucun' }];

  return (
    <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-xs flex flex-col justify-between">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">
            Répartition des sentiments
          </h3>
          <p className="text-xs text-slate-600 dark:text-slate-400">
            Notre modèle NLP (Transformer maison)
          </p>
        </div>
        <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
          {totalAvis} avis
        </span>
      </div>

      <div className="relative h-48 w-full my-auto flex items-center justify-center">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={52}
              outerRadius={75}
              paddingAngle={3}
              dataKey="value"
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} strokeWidth={1} />
              ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const d = payload[0].payload;
                  const pct = totalAvis > 0 ? Math.round((d.value / totalAvis) * 1000) / 10 : 0;
                  return (
                    <div className="bg-slate-900 text-white text-xs px-3 py-2 rounded-xl shadow-lg border border-slate-700">
                      <div className="font-bold flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: d.color }} />
                        {d.name}
                      </div>
                      <div className="text-slate-300 mt-1">
                        {d.value} avis ({pct} %)
                      </div>
                    </div>
                  );
                }
                return null;
              }}
            />
          </PieChart>
        </ResponsiveContainer>

        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-2xl font-extrabold text-slate-900 dark:text-white leading-none">
            {totalAvis}
          </span>
          <span className="text-[10px] font-medium uppercase tracking-wider text-slate-600 dark:text-slate-400 mt-0.5">
            Total
          </span>
        </div>
      </div>

      {/* Accessible detailed legend */}
      <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-slate-100 dark:border-slate-800">
        {data.map((item) => {
          const ItemIcon = item.icon;
          const pct = totalAvis > 0 ? Math.round((item.value / totalAvis) * 1000) / 10 : 0;
          return (
            <div key={item.key} className="flex items-center gap-2 p-1.5 rounded-lg bg-slate-50/70 dark:bg-slate-800/50">
              <span
                className="w-3 h-3 rounded-full shrink-0 flex items-center justify-center text-white"
                style={{ backgroundColor: item.color }}
              >
                <ItemIcon className="w-2 h-2" />
              </span>
              <div className="flex flex-col min-w-0">
                <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate">
                  {item.name}
                </span>
                <span className="text-[11px] text-slate-600 dark:text-slate-400">
                  {item.value} ({pct} %)
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
