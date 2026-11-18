import React from 'react';
import { Star, MessageSquarePlus, Sparkles, UserCheck } from 'lucide-react';
import { Review } from '../types';
import { HUMEURS } from '../utils/humeurs';

interface ReviewCardProps {
  review: Review;
  isHighlighted?: boolean;
  highlightSearchTerm?: string;
  onRespondWithWatchy: (review: Review) => void;
}

export const ReviewCard: React.FC<ReviewCardProps> = ({
  review,
  isHighlighted,
  highlightSearchTerm,
  onRespondWithWatchy,
}) => {
  const sentimentStyles = {
    POSITIVE: {
      badge: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800',
      label: 'POSITIF',
      indicator: 'bg-emerald-500',
    },
    NEGATIVE: {
      badge: 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border-rose-300 dark:border-rose-800',
      label: 'NÉGATIF',
      indicator: 'bg-rose-500',
    },
    NEUTRAL: {
      badge: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300 border-slate-300 dark:border-slate-700',
      label: 'NEUTRE',
      indicator: 'bg-slate-500',
    },
    MIXED: {
      badge: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border-amber-300 dark:border-amber-800',
      label: 'MITIGÉ',
      indicator: 'bg-amber-500',
    },
  }[review.sentiment];

  const formattedDate = new Date(review.date).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

  const isNegativeOrMixed = review.sentiment === 'NEGATIVE' || review.sentiment === 'MIXED';

  // Highlight search term helper
  const renderHighlightedText = (text: string, query?: string) => {
    if (!query || !query.trim()) return text;
    const terms = query.trim().split(/\s+/).filter(Boolean);
    if (terms.length === 0) return text;
    const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    try {
      const regex = new RegExp(`(${escaped})`, 'gi');
      const parts = text.split(regex);
      return parts.map((part, i) =>
        regex.test(part) ? (
          <mark
            key={i}
            className="bg-amber-200 text-amber-950 dark:bg-amber-500/30 dark:text-amber-200 px-1 py-0.5 rounded font-semibold"
          >
            {part}
          </mark>
        ) : (
          part
        )
      );
    } catch {
      return text;
    }
  };

  return (
    <article
      id={`review-${review.client_id}`}
      className={`relative p-4 rounded-2xl bg-white dark:bg-slate-900 border transition-all duration-300 ${
        isHighlighted
          ? 'ring-2 ring-emerald-500 border-emerald-400 dark:border-emerald-600 shadow-lg bg-emerald-50/20'
          : 'border-slate-200/80 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 shadow-xs'
      } ${review.isNew ? 'animate-in slide-in-from-top-4 duration-500' : ''}`}
    >
      {/* Header: Rating, Client ID, Date, Sentiment Badge */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          {/* Anonymized Client ID */}
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 font-mono text-xs font-bold">
            <UserCheck className="w-3 h-3 text-slate-400" />
            <span>{review.client_id}</span>
          </div>

          {/* Google Stars Rating */}
          <div className="flex items-center" aria-label={`Note Google : ${review.note_google} sur 5`}>
            {[1, 2, 3, 4, 5].map((star) => (
              <Star
                key={star}
                className={`w-3.5 h-3.5 ${
                  star <= review.note_google
                    ? 'text-amber-400 fill-amber-400'
                    : 'text-slate-200 dark:text-slate-700'
                }`}
              />
            ))}
          </div>

          <span className="text-slate-300 dark:text-slate-700">•</span>
          <time className="text-xs text-slate-600 dark:text-slate-400">{formattedDate}</time>
          {review.source && (
            <span className="text-[10px] font-semibold text-slate-500 dark:text-slate-400">{review.source}</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {review.a_verifier && (
            <span
              title="Confiance du modèle sous son seuil : à relire"
              className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300"
            >
              À vérifier
            </span>
          )}

          {/* New Badge */}
          {review.isNew && (
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-500 text-white animate-pulse">
              <Sparkles className="w-3 h-3" />
              Nouveau
            </span>
          )}

          {/* Sentiment Badge with Confidence Score */}
          <span
            className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border flex items-center gap-1.5 ${sentimentStyles.badge}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${sentimentStyles.indicator}`} />
            {sentimentStyles.label} · {Math.round(review.score * 100)}%
          </span>
        </div>
      </div>

      {/* Review Text with Search Highlight */}
      <p className="text-xs sm:text-sm text-slate-800 dark:text-slate-200 mt-2.5 leading-relaxed font-normal">
        {renderHighlightedText(review.texte, highlightSearchTerm)}
      </p>

      {/* Footer: Clean Business Theme Tags + Action */}
      <div className="flex flex-wrap items-center justify-between gap-2 mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800/80">
        {/* Business themes only (no stop words) */}
        <div className="flex flex-wrap items-center gap-1.5">
          {review.humeur && HUMEURS[review.humeur] && (
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 mr-1">
              {HUMEURS[review.humeur].emoji} {HUMEURS[review.humeur].libelle}
            </span>
          )}
          {review.themes.length > 0 && (
            <span className="text-[10px] uppercase font-bold text-slate-400 dark:text-slate-500 mr-1">
              Thèmes :
            </span>
          )}
          {review.themes.map((theme) => {
            const polarite = review.themes_detail?.find((t) => t.libelle === theme)?.polarite;
            const isThemeMatched =
              highlightSearchTerm &&
              theme.toLowerCase().includes(highlightSearchTerm.trim().toLowerCase());
            return (
              <span
                key={theme}
                className={`text-[11px] font-semibold px-2 py-0.5 rounded-md border transition-all ${
                  isThemeMatched
                    ? 'bg-amber-100 dark:bg-amber-950/80 text-amber-900 dark:text-amber-200 border-amber-300 dark:border-amber-700 font-bold'
                    : polarite === 'negatif'
                    ? 'bg-rose-50 dark:bg-rose-950/50 text-rose-800 dark:text-rose-300 border-rose-200/70 dark:border-rose-800/60'
                    : polarite === 'positif'
                    ? 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-800 dark:text-emerald-300 border-emerald-200/70 dark:border-emerald-800/60'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200/60 dark:border-slate-700/60'
                }`}
                title={polarite ? `Thème ${polarite}` : undefined}
              >
                {polarite === 'negatif' ? '− ' : polarite === 'positif' ? '+ ' : ''}{theme}
              </span>
            );
          })}
        </div>

        {/* Action Button: Répondre avec Watchy (recommended for negative/mixed reviews) */}
        {isNegativeOrMixed && (
          <button
            type="button"
            onClick={() => onRespondWithWatchy(review)}
            className="flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/60 hover:bg-indigo-100 dark:hover:bg-indigo-900/80 border border-indigo-200/80 dark:border-indigo-800/80 transition cursor-pointer shadow-xs ml-auto"
          >
            <MessageSquarePlus className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
            <span>Répondre avec Watchy</span>
          </button>
        )}
      </div>
    </article>
  );
};
