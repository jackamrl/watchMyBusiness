import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Search, Store, Star, Layers, Check } from 'lucide-react';
import { Business, CategoryId } from '../types';
import { BUSINESSES, CATEGORIES } from '../data/donnees';

interface BusinessSelectorProps {
  currentCategoryId: CategoryId;
  selectedBusinessId: string; // 'all' or specific business id
  onSelectBusiness: (id: string) => void;
}

export const BusinessSelector: React.FC<BusinessSelectorProps> = ({
  currentCategoryId,
  selectedBusinessId,
  onSelectBusiness,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  const categoryBusinesses = BUSINESSES.filter((b) => b.category === currentCategoryId);
  const currentCategory = CATEGORIES.find((c) => c.id === currentCategoryId);

  const selectedBusiness = BUSINESSES.find((b) => b.id === selectedBusinessId);
  const isAllSelected = selectedBusinessId === 'all';

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredBusinesses = categoryBusinesses.filter((b) =>
    b.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    b.city.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="relative inline-block" ref={dropdownRef}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        className="flex items-center gap-2.5 px-3.5 py-1.5 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100 hover:border-slate-300 dark:hover:border-slate-600 transition shadow-xs text-xs sm:text-sm font-medium cursor-pointer"
      >
        <div className="w-6 h-6 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
          {isAllSelected ? <Layers className="w-3.5 h-3.5" /> : <Store className="w-3.5 h-3.5" />}
        </div>

        <div className="flex flex-col text-left">
          <div className="flex items-center gap-1.5 font-bold leading-tight truncate max-w-[190px] sm:max-w-[240px]">
            <span>{isAllSelected ? `Tous les ${currentCategory?.label.toLowerCase() || 'établissements'}` : selectedBusiness?.name}</span>
          </div>
          <span className="text-[11px] text-slate-600 dark:text-slate-400 leading-tight">
            {isAllSelected
              ? `${categoryBusinesses.length} établissements · Vue comparative`
              : `${selectedBusiness?.city} · ★ ${selectedBusiness?.rating} (${selectedBusiness?.totalReviews.toLocaleString('fr-FR')} avis)`}
          </span>
        </div>

        <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ml-1 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          role="listbox"
          className="absolute z-50 left-0 mt-2 w-80 sm:w-96 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 shadow-xl p-2 animate-in fade-in zoom-in-95 duration-150"
        >
          {/* Search bar inside dropdown */}
          <div className="relative mb-2 px-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-2.5 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Rechercher un établissement..."
              className="w-full pl-9 pr-3 py-1.5 text-xs sm:text-sm rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
              autoFocus
            />
          </div>

          <div className="max-h-72 overflow-y-auto space-y-1 pr-1">
            {/* Option: Tous les établissements (seulement s'il y en a plusieurs) */}
            {categoryBusinesses.length > 1 && (
            <button
              type="button"
              role="option"
              aria-selected={isAllSelected}
              onClick={() => {
                onSelectBusiness('all');
                setIsOpen(false);
              }}
              className={`w-full text-left p-2.5 rounded-xl flex items-center justify-between transition cursor-pointer ${
                isAllSelected
                  ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-200 border border-emerald-200/70 dark:border-emerald-800'
                  : 'hover:bg-slate-50 dark:hover:bg-slate-800/60 text-slate-800 dark:text-slate-200'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-indigo-100 dark:bg-indigo-950/70 text-indigo-700 dark:text-indigo-400 flex items-center justify-center">
                  <Layers className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs sm:text-sm font-bold">Tous les établissements de la catégorie</div>
                  <div className="text-[11px] text-slate-600 dark:text-slate-400">
                    Vue comparative & classement ({categoryBusinesses.length} commerces)
                  </div>
                </div>
              </div>
              {isAllSelected && <Check className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />}
            </button>
            )}

            <div className="px-2 py-1 text-[10px] font-semibold tracking-wider uppercase text-slate-400 dark:text-slate-500">
              Établissements ({categoryBusinesses.length})
            </div>

            {filteredBusinesses.map((biz) => {
              const isSelected = selectedBusinessId === biz.id;
              return (
                <button
                  key={biz.id}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => {
                    onSelectBusiness(biz.id);
                    setIsOpen(false);
                  }}
                  className={`w-full text-left p-2.5 rounded-xl flex items-center justify-between transition cursor-pointer ${
                    isSelected
                      ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-200 border border-emerald-200/70 dark:border-emerald-800'
                      : 'hover:bg-slate-50 dark:hover:bg-slate-800/60 text-slate-800 dark:text-slate-200'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 flex items-center justify-center font-bold text-xs mt-0.5">
                      {biz.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <div className="text-xs sm:text-sm font-bold text-slate-900 dark:text-white leading-snug">
                        {biz.name}
                      </div>
                      <div className="text-[11px] text-slate-600 dark:text-slate-400">
                        {biz.city}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="inline-flex items-center gap-0.5 text-[11px] font-bold text-amber-600 dark:text-amber-400">
                          <Star className="w-3 h-3 fill-amber-400 text-amber-500" />
                          {biz.rating.toFixed(1).replace('.', ',')}
                        </span>
                        <span className="text-[10px] text-slate-400 dark:text-slate-500">
                          • {biz.totalReviews.toLocaleString('fr-FR')} avis Google
                        </span>
                      </div>
                    </div>
                  </div>
                  {isSelected && <Check className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 ml-2" />}
                </button>
              );
            })}

            {filteredBusinesses.length === 0 && (
              <div className="p-4 text-center text-xs text-slate-400">
                Aucun établissement trouvé pour &quot;{searchQuery}&quot;
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
