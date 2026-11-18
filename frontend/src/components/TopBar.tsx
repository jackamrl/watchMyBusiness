import React from 'react';
import { Sun, Moon, LogOut, Radio, RefreshCw } from 'lucide-react';
import { WatchyEyeLogo } from './WatchyEyeLogo';
import { CategorySelector } from './CategorySelector';
import { BusinessSelector } from './BusinessSelector';
import { WeekSelector } from './WeekSelector';
import { CategoryId } from '../types';

interface TopBarProps {
  selectedCategory: CategoryId;
  onSelectCategory: (id: CategoryId) => void;
  selectedBusinessId: string;
  onSelectBusiness: (id: string) => void;
  selectedWeekId: string;
  onSelectWeek: (id: string) => void;
  reviewCount: number;
  lastCollectTime: string;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
  userEmail: string;
  onLogout: () => void;
  onManualTriggerCollect?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  selectedCategory,
  onSelectCategory,
  selectedBusinessId,
  onSelectBusiness,
  selectedWeekId,
  onSelectWeek,
  reviewCount,
  lastCollectTime,
  isDarkMode,
  onToggleDarkMode,
  userEmail,
  onLogout,
  onManualTriggerCollect,
}) => {
  return (
    <header className="sticky top-0 z-40 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border-b border-slate-200/80 dark:border-slate-800 transition-colors">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 py-2.5">
        {/* Top row: Brand + Category Chips + Actions */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Brand Logo with Blinking Eye */}
          <div className="flex items-center gap-3 shrink-0">
            <WatchyEyeLogo size="md" />
          </div>

          {/* Central: Category Selector (Central, very visible) */}
          <div className="order-3 lg:order-2 w-full lg:w-auto flex justify-center py-0.5">
            <CategorySelector
              selectedCategory={selectedCategory}
              onSelectCategory={onSelectCategory}
            />
          </div>

          {/* Right: Live indicator + Dark mode + User Profile */}
          <div className="order-2 lg:order-3 flex items-center gap-2 sm:gap-3 shrink-0 ml-auto lg:ml-0">
            {/* Live Indicator with pulsing green dot */}
            <div
              className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800/80 text-[11px] sm:text-xs font-semibold text-emerald-800 dark:text-emerald-300"
              title="Collecte automatique des avis (Apify), analyse par notre modèle NLP"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              <span className="hidden sm:inline">Dernier avis ·</span>
              <span className="font-normal text-emerald-700 dark:text-emerald-400">
                {lastCollectTime}
              </span>

              {onManualTriggerCollect && (
                <button
                  type="button"
                  onClick={onManualTriggerCollect}
                  title="Simuler une collecte d'avis immédiate"
                  className="ml-1 p-0.5 hover:text-emerald-950 dark:hover:text-emerald-100 hover:rotate-180 transition-transform duration-300 cursor-pointer"
                  aria-label="Collecte manuelle"
                >
                  <RefreshCw className="w-3 h-3" />
                </button>
              )}
            </div>

            {/* Dark Mode Toggle */}
            <button
              type="button"
              onClick={onToggleDarkMode}
              aria-label={isDarkMode ? 'Passer en mode clair' : 'Passer en mode sombre'}
              title={isDarkMode ? 'Passer en mode clair' : 'Passer en mode sombre'}
              className="w-8 h-8 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 flex items-center justify-center transition cursor-pointer"
            >
              {isDarkMode ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4" />}
            </button>

            {/* User Profile & Logout */}
            <div className="flex items-center gap-2 pl-1 border-l border-slate-200 dark:border-slate-800">
              <div
                className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-600 to-emerald-500 text-white font-bold text-xs flex items-center justify-center shadow-xs"
                title={`Connecté en tant que ${userEmail}`}
              >
                {userEmail.slice(0, 2).toUpperCase()}
              </div>

              <button
                type="button"
                onClick={onLogout}
                aria-label="Se déconnecter"
                title="Se déconnecter de WatchMyBusiness"
                className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg transition cursor-pointer"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>Déconnexion</span>
              </button>
            </div>
          </div>
        </div>

        {/* Second row: Business Selector + Week Selector */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 mt-2.5 pt-2 border-t border-slate-100 dark:border-slate-800/80">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
              Établissement :
            </span>
            <BusinessSelector
              currentCategoryId={selectedCategory}
              selectedBusinessId={selectedBusinessId}
              onSelectBusiness={onSelectBusiness}
            />
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <span className="hidden sm:inline text-[11px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
              Période :
            </span>
            <WeekSelector
              currentWeekId={selectedWeekId}
              onSelectWeek={onSelectWeek}
              reviewCount={reviewCount}
            />
          </div>
        </div>
      </div>
    </header>
  );
};
