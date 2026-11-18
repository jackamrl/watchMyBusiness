import { Review, SentimentType, ThemeMetric, WeatherTrend, TrendStatus } from '../types';

export function calculateSentimentCounts(reviews: Review[]): {
  POSITIVE: number;
  NEGATIVE: number;
  NEUTRAL: number;
  MIXED: number;
  total: number;
} {
  const counts = { POSITIVE: 0, NEGATIVE: 0, NEUTRAL: 0, MIXED: 0, total: reviews.length };
  for (const r of reviews) {
    if (r.sentiment in counts) {
      counts[r.sentiment as SentimentType]++;
    }
  }
  return counts;
}

export function calculateSentimentPercentages(reviews: Review[]): {
  pctPositifs: number;
  pctNegatifs: number;
  pctNeutresMitiges: number;
} {
  const total = reviews.length;
  if (total === 0) {
    return { pctPositifs: 0, pctNegatifs: 0, pctNeutresMitiges: 0 };
  }
  const counts = calculateSentimentCounts(reviews);
  const round1 = (val: number) => Math.round((val / total) * 1000) / 10;

  const pctPositifs = round1(counts.POSITIVE);
  const pctNegatifs = round1(counts.NEGATIVE);
  const pctNeutresMitiges = round1(counts.NEUTRAL + counts.MIXED);

  return { pctPositifs, pctNegatifs, pctNeutresMitiges };
}

export function calculateAverageConfidence(reviews: Review[]): number {
  if (reviews.length === 0) return 0;
  const sum = reviews.reduce((acc, r) => acc + (r.score || 0.9), 0);
  return Math.round((sum / reviews.length) * 1000) / 1000;
}

export function determineBusinessWeather(
  pctPositifs: number,
  pctNegatifs: number,
  variationPts: number | null,
  reviewCount: number
): { meteo: WeatherTrend; meteoLibelle: string; tendance: TrendStatus } {
  if (reviewCount < 4) {
    return {
      meteo: 'brouillard',
      meteoLibelle: 'Brouillard (données insuffisantes)',
      tendance: 'indeterminee',
    };
  }

  // If negative reviews are high or variation drops sharply
  if (pctNegatifs >= 30 || (variationPts !== null && variationPts <= -5.0)) {
    return {
      meteo: 'orage',
      meteoLibelle: 'Orageux (tendance négative)',
      tendance: 'negative',
    };
  }

  // If positive reviews are strong and not dropping
  if (pctPositifs >= 70 && (variationPts === null || variationPts >= -1.0)) {
    return {
      meteo: 'soleil',
      meteoLibelle: 'Ensoleillé (tendance positive)',
      tendance: 'positive',
    };
  }

  return {
    meteo: 'variable',
    meteoLibelle: 'Variable (mitigée)',
    tendance: 'mitigee',
  };
}

export function extractThemeMetrics(
  reviews: Review[],
  targetSentiment: 'POSITIVE' | 'NEGATIVE',
  availableThemes?: string[]
): ThemeMetric[] {
  const filtered = reviews.filter((r) =>
    targetSentiment === 'POSITIVE'
      ? r.sentiment === 'POSITIVE'
      : r.sentiment === 'NEGATIVE' || r.sentiment === 'MIXED'
  );

  const themeMap = new Map<string, { occurrences: number; citations: string[] }>();

  // If specific availableThemes provided, seed them
  if (availableThemes) {
    availableThemes.forEach((t) => themeMap.set(t, { occurrences: 0, citations: [] }));
  }

  for (const review of filtered) {
    for (const theme of review.themes) {
      const entry = themeMap.get(theme) || { occurrences: 0, citations: [] };
      entry.occurrences++;
      if (entry.citations.length < 2 && review.texte && review.texte.length > 10) {
        // truncate citation cleanly if needed
        const snippet = review.texte.length > 85 ? review.texte.slice(0, 82) + '...' : review.texte;
        entry.citations.push(snippet);
      }
      themeMap.set(theme, entry);
    }
  }

  const totalFiltered = filtered.length || 1;
  const metrics: ThemeMetric[] = [];

  for (const [theme, data] of themeMap.entries()) {
    if (data.occurrences > 0) {
      const pct = Math.round((data.occurrences / totalFiltered) * 1000) / 10;
      metrics.push({
        theme,
        libelle: theme,
        occurrences: data.occurrences,
        pourcentage: pct,
        citations: data.citations,
      });
    }
  }

  // Sort descending by occurrences
  return metrics.sort((a, b) => b.occurrences - a.occurrences);
}

export function normalizeFrenchText(str: string): string {
  if (!str) return '';
  return str
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

export interface QuickSearchTopic {
  id: string;
  label: string;
  icon: string;
  keywords: string;
  description: string;
}

export const COMMON_SEARCH_TOPICS: QuickSearchTopic[] = [
  { id: 'livraison', label: 'Livraison', icon: '🛵', keywords: 'livraison', description: 'Délais, emballage, livreurs et commandes à emporter' },
  { id: 'proprete', label: 'Propreté', icon: '✨', keywords: 'propreté', description: 'Hygiène des lieux, tables, sanitaires et cuisine' },
  { id: 'attente', label: 'Temps d\'attente', icon: '⏱️', keywords: 'attente', description: 'File d\'attente, délais de commande et de service' },
  { id: 'accueil', label: 'Accueil & service', icon: '🤝', keywords: 'accueil', description: 'Sourire, amabilité de l\'équipe et prise en charge' },
  { id: 'plats', label: 'Qualité des plats', icon: '🍽️', keywords: 'qualité', description: 'Saveurs, portions, fraîcheur et cuisson' },
  { id: 'prix', label: 'Prix & addition', icon: '💶', keywords: 'prix', description: 'Rapport qualité-prix et tarifs des consommations' },
  { id: 'ambiance', label: 'Ambiance & cadre', icon: '🎵', keywords: 'ambiance', description: 'Bruit, confort de la salle et atmosphère' },
];

export function filterReviewsList(
  reviews: Review[],
  filters: {
    sentiment?: 'ALL' | SentimentType;
    search?: string;
    theme?: string;
    sortBy?: 'recent' | 'negative' | 'rating_asc' | 'rating_desc';
  }
): Review[] {
  let result = [...reviews];

  if (filters.sentiment && filters.sentiment !== 'ALL') {
    result = result.filter((r) => r.sentiment === filters.sentiment);
  }

  if (filters.theme) {
    result = result.filter((r) => r.themes.includes(filters.theme!));
  }

  if (filters.search && filters.search.trim() !== '') {
    const rawTerms = filters.search.trim().split(/\s+/).filter(Boolean);
    const normalizedTerms = rawTerms.map(normalizeFrenchText);

    result = result.filter((r) => {
      const normText = normalizeFrenchText(r.texte);
      const normClient = normalizeFrenchText(r.client_id);
      const normThemes = r.themes.map(normalizeFrenchText).join(' ');

      // Every term in search query must match either text, client_id, or themes
      return normalizedTerms.every(
        (term) =>
          normText.includes(term) ||
          normClient.includes(term) ||
          normThemes.includes(term)
      );
    });
  }

  if (filters.sortBy === 'negative') {
    result.sort((a, b) => {
      // Prioritize NEGATIVE, then MIXED, then NEUTRAL, then POSITIVE
      const order = { NEGATIVE: 0, MIXED: 1, NEUTRAL: 2, POSITIVE: 3 };
      const diff = order[a.sentiment] - order[b.sentiment];
      if (diff !== 0) return diff;
      return a.note_google - b.note_google; // Lower rating first
    });
  } else if (filters.sortBy === 'rating_asc') {
    result.sort((a, b) => a.note_google - b.note_google);
  } else if (filters.sortBy === 'rating_desc') {
    result.sort((a, b) => b.note_google - a.note_google);
  } else {
    // Recent first (date descending)
    result.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  }

  return result;
}

export function formatPtsVariation(val: number | null): string {
  if (val === null || val === undefined) return 'Données précédentes indisponibles';
  if (val > 0) return `+${val.toFixed(1).replace('.', ',')} pts d'avis positifs vs semaine précédente`;
  if (val < 0) return `${val.toFixed(1).replace('.', ',')} pts d'avis positifs vs semaine précédente`;
  return `Stable (0,0 pt) vs semaine précédente`;
}
