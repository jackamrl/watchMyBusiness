import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  Search,
  SlidersHorizontal,
  X,
  ArrowDownWideNarrow,
  MessageSquare,
  Sparkles,
  ChevronDown,
  Tag,
  Check,
  Bike,
  Sparkle,
  Clock,
  HeartHandshake,
  UtensilsCrossed,
  Receipt,
  Volume2,
} from 'lucide-react';
import { Review, SentimentType } from '../types';
import { ReviewCard } from './ReviewCard';
import { filterReviewsList, COMMON_SEARCH_TOPICS, QuickSearchTopic } from '../utils/metrics';

interface ReviewFeedProps {
  reviews: Review[];
  activeThemeFilter: string | null;
  onClearThemeFilter: () => void;
  highlightedClientId: string | null;
  onRespondWithWatchy: (review: Review) => void;
  onlyToVerify?: boolean;
  onToggleOnlyToVerify?: () => void;
}

export const ReviewFeed: React.FC<ReviewFeedProps> = ({
  reviews,
  activeThemeFilter,
  onClearThemeFilter,
  highlightedClientId,
  onRespondWithWatchy,
  onlyToVerify = false,
  onToggleOnlyToVerify,
}) => {
  const [selectedSentiment, setSelectedSentiment] = useState<'ALL' | SentimentType>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [isTopicMenuOpen, setIsTopicMenuOpen] = useState(false);
  const [sortBy, setSortBy] = useState<'recent' | 'negative' | 'rating_asc' | 'rating_desc'>('recent');

  const topicMenuRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close topic dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (topicMenuRef.current && !topicMenuRef.current.contains(event.target as Node)) {
        setIsTopicMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Compute detected themes in current reviews with review count
  const detectedThemes = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of reviews) {
      for (const t of r.themes) {
        map.set(t, (map.get(t) || 0) + 1);
      }
    }
    return Array.from(map.entries())
      .map(([theme, count]) => ({ theme, count }))
      .sort((a, b) => b.count - a.count);
  }, [reviews]);

  const filteredReviews = filterReviewsList(onlyToVerify ? reviews.filter((r) => r.a_verifier) : reviews, {
    sentiment: selectedSentiment,
    search: searchQuery,
    theme: activeThemeFilter || undefined,
    sortBy,
  });

  const sentimentsList: { id: 'ALL' | SentimentType; label: string; count: number }[] = [
    { id: 'ALL', label: 'Tous', count: reviews.length },
    { id: 'POSITIVE', label: 'Positifs', count: reviews.filter((r) => r.sentiment === 'POSITIVE').length },
    { id: 'NEGATIVE', label: 'Négatifs', count: reviews.filter((r) => r.sentiment === 'NEGATIVE').length },
    { id: 'NEUTRAL', label: 'Neutres', count: reviews.filter((r) => r.sentiment === 'NEUTRAL').length },
    { id: 'MIXED', label: 'Mitigés', count: reviews.filter((r) => r.sentiment === 'MIXED').length },
  ];

  const handleSelectTopic = (topic: QuickSearchTopic) => {
    if (searchQuery.toLowerCase() === topic.keywords.toLowerCase()) {
      setSearchQuery('');
    } else {
      setSearchQuery(topic.keywords);
    }
    setIsTopicMenuOpen(false);
  };

  const handleSelectDetectedTheme = (themeName: string) => {
    if (searchQuery.toLowerCase() === themeName.toLowerCase()) {
      setSearchQuery('');
    } else {
      setSearchQuery(themeName);
    }
    setIsTopicMenuOpen(false);
  };

  return (
    <section className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-xs p-4 sm:p-5">
      {/* Top Header & Search Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            <h2 className="text-base sm:text-lg font-extrabold text-slate-900 dark:text-white">
              Flux des avis
            </h2>
            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
              {filteredReviews.length} avis
            </span>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
            Avis Google Maps et TripAdvisor, classés par notre modèle : sentiment, humeur, thèmes et confiance
          </p>
        </div>

        {/* Search & Sort Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Smart Search Input with Interactive Topic Selector */}
          <div className="relative min-w-[260px] sm:min-w-[320px] flex-1 sm:flex-initial" ref={topicMenuRef}>
            <div className="relative flex items-center">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 pointer-events-none" />
              <input
                ref={inputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => setIsTopicMenuOpen(true)}
                placeholder="Rechercher livraison, propreté, attente..."
                className="w-full pl-9 pr-24 py-1.5 text-xs sm:text-sm rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
              />

              {/* Action buttons inside the right side of the search input */}
              <div className="absolute right-1.5 flex items-center gap-1">
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearchQuery('');
                      inputRef.current?.focus();
                    }}
                    title="Effacer la recherche"
                    aria-label="Effacer la recherche"
                    className="p-1 rounded-md text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-700 transition cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}

                {/* Dropdown toggle for choosing topic */}
                <button
                  type="button"
                  onClick={() => setIsTopicMenuOpen(!isTopicMenuOpen)}
                  aria-expanded={isTopicMenuOpen}
                  title="Choisir ce que vous voulez chercher"
                  aria-label="Choisir un thème de recherche"
                  className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-bold transition cursor-pointer ${
                    isTopicMenuOpen
                      ? 'bg-slate-900 text-white dark:bg-emerald-600'
                      : 'bg-white dark:bg-slate-700/80 text-slate-700 dark:text-slate-200 border border-slate-200/80 dark:border-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <span>Thèmes</span>
                  <ChevronDown className={`w-3 h-3 transition-transform duration-200 ${isTopicMenuOpen ? 'rotate-180' : ''}`} />
                </button>
              </div>
            </div>

            {/* Dropdown Menu: Choose what to search */}
            {isTopicMenuOpen && (
              <div
                role="listbox"
                aria-label="Thèmes de recherche"
                className="absolute z-50 left-0 right-0 mt-2 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 shadow-2xl p-3 animate-in fade-in zoom-in-95 duration-150 max-h-[380px] overflow-y-auto"
              >
                <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-xs font-extrabold uppercase tracking-wider text-slate-900 dark:text-white flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-emerald-500" />
                    Choisir un sujet de recherche
                  </span>
                  <span className="text-[10px] text-slate-600 dark:text-slate-400">
                    Cliquez pour filtrer
                  </span>
                </div>

                {/* Frequent presets */}
                <div className="space-y-1">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 px-1 py-0.5">
                    Sujets fréquents (PME &amp; commerces)
                  </div>
                  {COMMON_SEARCH_TOPICS.map((topic) => {
                    const isSelected = searchQuery.toLowerCase() === topic.keywords.toLowerCase();
                    return (
                      <button
                        key={topic.id}
                        type="button"
                        onClick={() => handleSelectTopic(topic)}
                        className={`w-full text-left p-2 rounded-xl flex items-center justify-between transition cursor-pointer ${
                          isSelected
                            ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-200 border border-emerald-200 dark:border-emerald-800'
                            : 'hover:bg-slate-50 dark:hover:bg-slate-800/70 text-slate-800 dark:text-slate-200'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <span className="text-base leading-none">{topic.icon}</span>
                          <div>
                            <div className="text-xs font-bold leading-tight flex items-center gap-1.5">
                              <span>{topic.label}</span>
                              {isSelected && <span className="text-[9px] font-extrabold text-emerald-600">Actif</span>}
                            </div>
                            <div className="text-[10px] text-slate-600 dark:text-slate-400">
                              {topic.description}
                            </div>
                          </div>
                        </div>
                        {isSelected && <Check className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />}
                      </button>
                    );
                  })}
                </div>

                {/* Themes detected in reviews this week */}
                {detectedThemes.length > 0 && (
                  <div className="mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800">
                    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 px-1 py-0.5 mb-1 flex items-center gap-1">
                      <Tag className="w-3 h-3 text-indigo-500" />
                      Thèmes détectés cette semaine ({detectedThemes.length})
                    </div>
                    <div className="flex flex-wrap gap-1.5 p-1">
                      {detectedThemes.map((dt) => {
                        const isSelected = searchQuery.toLowerCase() === dt.theme.toLowerCase();
                        return (
                          <button
                            key={dt.theme}
                            type="button"
                            onClick={() => handleSelectDetectedTheme(dt.theme)}
                            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                              isSelected
                                ? 'bg-indigo-600 text-white shadow-xs'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                            }`}
                          >
                            <span>#{dt.theme}</span>
                            <span className={`text-[10px] px-1 py-0.2 rounded-full ${isSelected ? 'bg-white/20 text-white' : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'}`}>
                              {dt.count}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Sort Selector */}
          <div className="flex items-center gap-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-2.5 py-1.5 text-xs">
            <ArrowDownWideNarrow className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-transparent text-slate-700 dark:text-slate-300 font-semibold focus:outline-none cursor-pointer"
            >
              <option value="recent">Plus récents d&apos;abord</option>
              <option value="negative">Priorité aux plus négatifs</option>
              <option value="rating_asc">Note croissante (1★ d&apos;abord)</option>
              <option value="rating_desc">Note décroissante (5★ d&apos;abord)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Direct Search Topic Chips (One-click selection bar: Livraison, Propreté, etc.) */}
      <div className="flex items-center gap-1.5 overflow-x-auto py-2 scrollbar-none no-scrollbar border-b border-slate-100 dark:border-slate-800">
        <span className="text-[11px] font-bold text-slate-600 dark:text-slate-400 shrink-0 flex items-center gap-1 mr-1">
          <Tag className="w-3 h-3 text-emerald-600" />
          Recherche directe :
        </span>

        {COMMON_SEARCH_TOPICS.map((topic) => {
          const isSelected = searchQuery.toLowerCase() === topic.keywords.toLowerCase();
          return (
            <button
              key={topic.id}
              type="button"
              onClick={() => handleSelectTopic(topic)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition cursor-pointer select-none ${
                isSelected
                  ? 'bg-emerald-600 text-white shadow-xs font-bold ring-2 ring-emerald-500/30'
                  : 'bg-slate-100/90 text-slate-700 hover:bg-slate-200/90 dark:bg-slate-800/80 dark:text-slate-300 dark:hover:bg-slate-700'
              }`}
            >
              <span>{topic.icon}</span>
              <span>{topic.label}</span>
              {isSelected && <Check className="w-3 h-3 ml-0.5" />}
            </button>
          );
        })}
      </div>

      {/* Filter Pills (Tous, Positifs, Négatifs, Neutres, Mitigés) & Active search banner */}
      <div className="flex flex-wrap items-center justify-between gap-2 my-3">
        <div className="flex flex-wrap items-center gap-1.5">
          {sentimentsList.map((tab) => {
            const isSelected = selectedSentiment === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setSelectedSentiment(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold transition cursor-pointer ${
                  isSelected
                    ? 'bg-slate-900 text-white dark:bg-emerald-600 dark:text-white shadow-xs'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
                }`}
              >
                <span>{tab.label}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                    isSelected
                      ? 'bg-white/20 text-white'
                      : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-400'
                  }`}
                >
                  {tab.count}
                </span>
              </button>
            );
          })}
          {onToggleOnlyToVerify && (
            <button
              type="button"
              onClick={onToggleOnlyToVerify}
              title="Avis sur lesquels le modèle hésite (confiance sous son seuil)"
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold transition cursor-pointer ${
                onlyToVerify
                  ? 'bg-violet-600 text-white shadow-xs'
                  : 'bg-violet-50 text-violet-700 hover:bg-violet-100 dark:bg-violet-950/60 dark:text-violet-300'
              }`}
            >
              <span>À vérifier</span>
              <span className={`text-[10px] px-1.5 rounded-full ${onlyToVerify ? 'bg-white/20' : 'bg-violet-100 dark:bg-violet-900'}`}>
                {reviews.filter((r) => r.a_verifier).length}
              </span>
            </button>
          )}
        </div>

        {/* Active Search & Active Theme Indicators */}
        <div className="flex flex-wrap items-center gap-2">
          {searchQuery && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 text-xs font-semibold text-emerald-800 dark:text-emerald-300">
              <span>Recherche : <strong>« {searchQuery} »</strong> ({filteredReviews.length} avis)</span>
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="p-0.5 hover:bg-emerald-200/60 dark:hover:bg-emerald-900 rounded-md cursor-pointer transition"
                title="Effacer la recherche"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {activeThemeFilter && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800 text-xs font-semibold text-indigo-700 dark:text-indigo-300">
              <span>Filtre thème : <strong>#{activeThemeFilter}</strong></span>
              <button
                type="button"
                onClick={onClearThemeFilter}
                className="p-0.5 hover:bg-indigo-200/60 dark:hover:bg-indigo-900 rounded-md cursor-pointer transition"
                title="Supprimer le filtre de thème"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Reviews List */}
      <div className="space-y-3 max-h-[700px] overflow-y-auto pr-1">
        {filteredReviews.map((review) => (
          <ReviewCard
            key={review.avis_id}
            review={review}
            isHighlighted={highlightedClientId === review.client_id}
            highlightSearchTerm={searchQuery}
            onRespondWithWatchy={onRespondWithWatchy}
          />
        ))}

        {filteredReviews.length === 0 && (
          <div className="py-12 text-center bg-slate-50/50 dark:bg-slate-800/30 rounded-2xl border border-dashed border-slate-200 dark:border-slate-800">
            <SlidersHorizontal className="w-8 h-8 text-slate-400 mx-auto mb-2 opacity-60" />
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
              Aucun avis ne correspond à {searchQuery ? `« ${searchQuery} »` : 'vos filtres'}
            </p>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
              Essayez de choisir un autre thème ou réinitialisez vos critères de recherche.
            </p>
            <button
              type="button"
              onClick={() => {
                setSelectedSentiment('ALL');
                setSearchQuery('');
                onClearThemeFilter();
              }}
              className="mt-3 px-3.5 py-1.5 text-xs font-bold rounded-xl bg-slate-900 text-white dark:bg-emerald-600 hover:opacity-90 cursor-pointer"
            >
              Réinitialiser tous les filtres
            </button>
          </div>
        )}
      </div>
    </section>
  );
};
