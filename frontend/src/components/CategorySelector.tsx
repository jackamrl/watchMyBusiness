import React from 'react';
import { Category, CategoryId } from '../types';
import { CATEGORIES } from '../data/donnees';

interface CategorySelectorProps {
  selectedCategory: CategoryId;
  onSelectCategory: (id: CategoryId) => void;
}

export const CategorySelector: React.FC<CategorySelectorProps> = ({
  selectedCategory,
  onSelectCategory,
}) => {
  return (
    <nav
      aria-label="Catégories d'établissements"
      className="flex items-center gap-1.5 overflow-x-auto py-1 px-1 scrollbar-none no-scrollbar"
    >
      {CATEGORIES.map((cat: Category) => {
        const isSelected = selectedCategory === cat.id;
        return (
          <button
            key={cat.id}
            type="button"
            onClick={() => onSelectCategory(cat.id)}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs sm:text-sm font-semibold transition-all duration-200 whitespace-nowrap cursor-pointer select-none focus:outline-none focus:ring-2 focus:ring-emerald-500/40 ${
              isSelected
                ? 'bg-slate-900 text-white shadow-md shadow-slate-900/15 dark:bg-emerald-600 dark:text-white scale-102 ring-1 ring-slate-800'
                : 'bg-white/90 text-slate-700 hover:bg-slate-100/90 hover:text-slate-900 border border-slate-200/80 dark:bg-slate-800/80 dark:text-slate-300 dark:border-slate-700 dark:hover:bg-slate-700'
            }`}
            aria-pressed={isSelected}
          >
            <span className="text-base leading-none">{cat.icon}</span>
            <span>{cat.label}</span>
          </button>
        );
      })}
    </nav>
  );
};
