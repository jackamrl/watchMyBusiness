import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { DailyVolume } from '../types';

interface DailyVolumeChartProps {
  data: DailyVolume[];
}

export const DailyVolumeChart: React.FC<DailyVolumeChartProps> = ({ data }) => {
  return (
    <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-xs flex flex-col justify-between">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">
            Volume quotidien par sentiment
          </h3>
          <p className="text-xs text-slate-600 dark:text-slate-400">
            Barres empilées sur les 7 jours de la semaine
          </p>
        </div>
      </div>

      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" opacity={0.6} />
            <XAxis
              dataKey="jourNom"
              tickLine={false}
              axisLine={{ stroke: '#cbd5e1' }}
              tick={{ fill: '#64748b', fontSize: 11 }}
            />
            <YAxis
              allowDecimals={false}
              tickLine={false}
              axisLine={{ stroke: '#cbd5e1' }}
              tick={{ fill: '#64748b', fontSize: 11 }}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  const total = payload.reduce((acc, curr) => acc + (Number(curr.value) || 0), 0);
                  return (
                    <div className="bg-slate-900 text-white text-xs p-3 rounded-xl shadow-xl border border-slate-700 min-w-[140px]">
                      <div className="font-bold border-b border-slate-700 pb-1 mb-1.5 flex justify-between">
                        <span>{label}</span>
                        <span className="text-emerald-400">{total} avis</span>
                      </div>
                      <div className="space-y-1">
                        {payload.map((entry, index) => (
                          <div key={`item-${index}`} className="flex items-center justify-between gap-3 text-[11px]">
                            <span className="flex items-center gap-1.5 text-slate-300">
                              <span
                                className="w-2 h-2 rounded-full inline-block"
                                style={{ backgroundColor: entry.color }}
                              />
                              {entry.name}
                            </span>
                            <span className="font-bold">{entry.value}</span>
                          </div>
                        ))}
                      </div>
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
              wrapperStyle={{ paddingBottom: '8px', fontSize: '11px' }}
            />
            {/* Stacked bars colored by sentiment */}
            <Bar dataKey="positifs" name="Positifs" stackId="a" fill="#059669" radius={[0, 0, 0, 0]} />
            <Bar dataKey="negatifs" name="Négatifs" stackId="a" fill="#e11d48" radius={[0, 0, 0, 0]} />
            <Bar dataKey="neutres" name="Neutres" stackId="a" fill="#64748b" radius={[0, 0, 0, 0]} />
            <Bar dataKey="mitiges" name="Mitigés" stackId="a" fill="#d97706" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
