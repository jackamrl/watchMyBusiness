import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { WeeklyTrendPoint } from '../types';

interface WeeklyTrendChartProps {
  data: WeeklyTrendPoint[];
  currentWeekId: string;
}

export const WeeklyTrendChart: React.FC<WeeklyTrendChartProps> = ({
  data,
  currentWeekId,
}) => {
  return (
    <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-xs">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">
            Évolution semaine après semaine (12 semaines)
          </h3>
          <p className="text-xs text-slate-600 dark:text-slate-400">
            Comparatif des taux d&apos;avis positifs et négatifs dans le temps
          </p>
        </div>

        <div className="flex items-center gap-2 text-[11px] text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800 px-2.5 py-1 rounded-lg">
          <span className="w-2 h-2 rounded-full bg-slate-400" />
          <span>Interruption visible si absence de collecte (pas de chute à 0%)</span>
        </div>
      </div>

      <div className="h-60 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 15, right: 15, left: -15, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" opacity={0.6} />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={{ stroke: '#cbd5e1' }}
              tick={({ x, y, payload }) => {
                const isSelected = data.find((d) => d.label === payload.value)?.semaine_id === currentWeekId;
                return (
                  <text
                    x={Number(x)}
                    y={Number(y) + 12}
                    fill={isSelected ? '#059669' : '#64748b'}
                    fontSize={11}
                    fontWeight={isSelected ? 700 : 500}
                    textAnchor="middle"
                  >
                    {payload.value}
                    {isSelected && ' •'}
                  </text>
                );
              }}
            />
            <YAxis
              unit="%"
              domain={[0, 100]}
              tickLine={false}
              axisLine={{ stroke: '#cbd5e1' }}
              tick={{ fill: '#64748b', fontSize: 11 }}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  const item = data.find((d) => d.label === label);
                  const isNull = item?.pct_positifs === null;
                  return (
                    <div className="bg-slate-900 text-white text-xs p-3 rounded-xl shadow-xl border border-slate-700 min-w-[160px]">
                      <div className="font-bold border-b border-slate-700 pb-1 mb-1.5 flex justify-between">
                        <span>Semaine {item?.semaine_id || label}</span>
                        <span className="text-slate-400 text-[10px]">
                          {isNull ? 'Aucune donnée' : `${item?.nb_avis} avis`}
                        </span>
                      </div>

                      {isNull ? (
                        <div className="text-amber-400 text-[11px] italic">
                          Données insuffisantes / non collectées
                        </div>
                      ) : (
                        <div className="space-y-1">
                          <div className="flex items-center justify-between text-emerald-400">
                            <span>Positifs :</span>
                            <span className="font-bold">{item?.pct_positifs}%</span>
                          </div>
                          <div className="flex items-center justify-between text-rose-400">
                            <span>Négatifs :</span>
                            <span className="font-bold">{item?.pct_negatifs}%</span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                }
                return null;
              }}
            />
            <Legend
              verticalAlign="top"
              align="right"
              iconType="circle"
              wrapperStyle={{ paddingBottom: '10px', fontSize: '11px' }}
            />

            {/* connectNulls={false} ensures that weeks without data are shown as a gap rather than 0% */}
            <Line
              type="monotone"
              dataKey="pct_positifs"
              name="% Positifs"
              stroke="#059669"
              strokeWidth={3}
              dot={{ r: 4, fill: '#059669', strokeWidth: 2, stroke: '#fff' }}
              activeDot={{ r: 6 }}
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="pct_negatifs"
              name="% Négatifs"
              stroke="#e11d48"
              strokeWidth={3}
              dot={{ r: 4, fill: '#e11d48', strokeWidth: 2, stroke: '#fff' }}
              activeDot={{ r: 6 }}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
