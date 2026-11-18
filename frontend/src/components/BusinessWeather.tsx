import React from 'react';
import { Sun, CloudSun, CloudRain, CloudFog, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { WeatherTrend, TrendStatus } from '../types';

interface BusinessWeatherProps {
  weekId: string;
  dates: string;
  businessName: string;
  meteo: WeatherTrend;
  meteoLibelle: string;
  variationPts: number | null;
  tendance: TrendStatus;
  nbAvis: number;
}

export const BusinessWeather: React.FC<BusinessWeatherProps> = ({
  weekId,
  dates,
  businessName,
  meteo,
  variationPts,
  tendance,
  nbAvis,
}) => {
  const weatherConfig = {
    soleil: {
      icon: Sun,
      emoji: '☀️',
      title: 'Ensoleillé',
      sub: 'Tendance positive et satisfaction élevée',
      bgGradient: 'from-amber-500/15 via-emerald-500/10 to-transparent',
      borderColor: 'border-emerald-300 dark:border-emerald-800/80',
      badgeBg: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
      textColor: 'text-emerald-700 dark:text-emerald-400',
      iconColor: 'text-amber-500 fill-amber-400 animate-spin-slow',
    },
    variable: {
      icon: CloudSun,
      emoji: '⛅',
      title: 'Variable',
      sub: 'Tendance mitigée avec quelques points de vigilance',
      bgGradient: 'from-amber-500/10 via-slate-500/5 to-transparent',
      borderColor: 'border-amber-300 dark:border-amber-800/80',
      badgeBg: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
      textColor: 'text-amber-700 dark:text-amber-400',
      iconColor: 'text-amber-500',
    },
    orage: {
      icon: CloudRain,
      emoji: '🌧️',
      title: 'Orageux',
      sub: 'Tendance négative nécessitant une intervention rapide',
      bgGradient: 'from-rose-500/15 via-red-500/10 to-transparent',
      borderColor: 'border-rose-300 dark:border-rose-800/80',
      badgeBg: 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300',
      textColor: 'text-rose-700 dark:text-rose-400',
      iconColor: 'text-rose-500 animate-bounce',
    },
    brouillard: {
      icon: CloudFog,
      emoji: '🌫️',
      title: 'Brouillard',
      sub: 'Données insuffisantes sur cette période',
      bgGradient: 'from-slate-400/10 via-slate-300/5 to-transparent',
      borderColor: 'border-slate-300 dark:border-slate-700',
      badgeBg: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300',
      textColor: 'text-slate-600 dark:text-slate-400',
      iconColor: 'text-slate-400',
    },
  }[meteo];

  const WeatherIcon = weatherConfig.icon;

  const prevWeekName = weekId.includes('-W')
    ? `W${parseInt(weekId.split('-W')[1], 10) - 1}`
    : 'semaine précédente';

  return (
    <div
      className={`relative overflow-hidden rounded-2xl bg-white dark:bg-slate-900 border ${weatherConfig.borderColor} shadow-sm p-4 sm:p-5 transition-all`}
    >
      <div className={`absolute inset-0 bg-gradient-to-r ${weatherConfig.bgGradient} pointer-events-none`} />

      <div className="relative flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Left: Week Title & Dates */}
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
              Rapport d&apos;activité hebdomadaire
            </span>
            <span className="text-slate-300 dark:text-slate-700">•</span>
            <span className="text-xs text-slate-600 dark:text-slate-400">{businessName}</span>
          </div>

          <div className="flex items-baseline gap-3 mt-1">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
              {weekId}
            </h1>
            <span className="text-sm sm:text-base font-semibold text-slate-600 dark:text-slate-400">
              {dates}
            </span>
          </div>

          <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
            Synthèse des {nbAvis} avis de la semaine (Google Maps et TripAdvisor), analysés par notre modèle NLP.
          </p>
        </div>

        {/* Right: Météo du business badge & Points variation */}
        <div className="flex items-center gap-3.5 bg-slate-50/80 dark:bg-slate-800/80 p-3 sm:px-4 sm:py-3 rounded-2xl border border-slate-200/80 dark:border-slate-700/80 shadow-xs">
          <div className="w-12 h-12 rounded-xl bg-white dark:bg-slate-900 shadow-sm flex items-center justify-center shrink-0 border border-slate-100 dark:border-slate-800 text-2xl">
            <span>{weatherConfig.emoji}</span>
          </div>

          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
                Météo du business
              </span>
              <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${weatherConfig.badgeBg}`}>
                {weatherConfig.title}
              </span>
            </div>

            <div className="flex items-center gap-1.5 mt-0.5">
              {variationPts !== null ? (
                <>
                  {variationPts > 0 ? (
                    <TrendingUp className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                  ) : variationPts < 0 ? (
                    <TrendingDown className="w-4 h-4 text-rose-600 dark:text-rose-400" />
                  ) : (
                    <Minus className="w-4 h-4 text-slate-400" />
                  )}
                  <span
                    className={`text-sm sm:text-base font-extrabold ${
                      variationPts > 0
                        ? 'text-emerald-700 dark:text-emerald-400'
                        : variationPts < 0
                        ? 'text-rose-700 dark:text-rose-400'
                        : 'text-slate-600 dark:text-slate-400'
                    }`}
                  >
                    {variationPts > 0 ? `+${variationPts.toFixed(1).replace('.', ',')}` : variationPts.toFixed(1).replace('.', ',')} pts
                  </span>
                  <span className="text-xs text-slate-600 dark:text-slate-400">
                    d&apos;avis positifs vs {prevWeekName}
                  </span>
                </>
              ) : (
                <span className="text-xs text-slate-600 dark:text-slate-400 italic">
                  Données de comparaison indisponibles
                </span>
              )}
            </div>
            <span className="text-[11px] text-slate-600 dark:text-slate-400 mt-0.5">
              {weatherConfig.sub}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
