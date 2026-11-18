export type CategoryId = 'restaurants' | 'bars_pmu' | 'cafes_brasseries' | 'boulangeries' | 'hotels';

export interface Category {
  id: CategoryId;
  label: string;
  icon: string;
  description: string;
  themes: string[];
}

export interface Business {
  id: string;
  name: string;
  category: CategoryId;
  city: string;
  rating: number; // e.g. 4.3
  totalReviews: number; // e.g. 14741
  address: string;
}

export type SentimentType = 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL' | 'MIXED';

export interface Review {
  avis_id: string;
  date: string; // ISO date e.g. "2026-10-16T14:32:00"
  semaine_id: string; // e.g. "2026-W42"
  client_id: string; // identifiant anonyme, ex. "AV-0042"
  etablissement_id: string;
  note_google: number; // 1 to 5
  texte: string;
  sentiment: SentimentType;
  score: number; // 0 à 1 : confiance de notre modèle NLP
  themes: string[]; // libellés des thèmes repérés
  themes_detail?: { libelle: string; polarite: 'positif' | 'negatif' | 'neutre' }[];
  humeur?: Humeur | null;
  a_verifier?: boolean; // confiance sous le seuil du modèle
  source?: 'Google' | 'TripAdvisor';
  isNew?: boolean;
}

export type Humeur = 'joie' | 'satisfaction' | 'neutre' | 'deception' | 'frustration' | 'colere';

export interface HumeurCount {
  humeur: Humeur;
  nb: number;
}

export interface ThemeMetric {
  theme: string;
  libelle: string;
  occurrences: number;
  pourcentage: number;
  variation_pts?: number; // delta vs previous week in percentage points
  tendance?: 'hausse' | 'baisse' | 'stable';
  citations: string[]; // 2 customer quotes
}

export interface DailyVolume {
  date: string;
  jourNom: string; // 'Lun 12', 'Mar 13', ...
  nb: number;
  positifs: number;
  negatifs: number;
  neutres: number;
  mitiges: number;
}

export type WeatherTrend = 'soleil' | 'variable' | 'orage' | 'brouillard';
export type TrendStatus = 'positive' | 'negative' | 'mitigee' | 'indeterminee';

export interface WeeklyReport {
  semaine_id: string;
  debut: string; // e.g. "12 octobre"
  fin: string; // e.g. "18 octobre"
  nb_avis: number;
  repartition: {
    POSITIVE: number;
    NEGATIVE: number;
    NEUTRAL: number;
    MIXED: number;
  };
  pct_positifs: number;
  pct_negatifs: number;
  pct_neutres_mitiges: number;
  score_confiance_moyen: number; // 0 to 1
  tendance: TrendStatus;
  variation_pts: number | null; // e.g. +8.4
  meteo: WeatherTrend;
  meteo_libelle: string; // "Ensoleillé", "Variable", "Orageux", "Brouillard"
  volume_par_jour: DailyVolume[];
  themes_negatifs: ThemeMetric[];
  themes_positifs: ThemeMetric[];
  humeurs: HumeurCount[];
  nb_a_verifier: number;
  note_moyenne: number | null;
  synthese: string;
}

export interface WeeklyTrendPoint {
  semaine_id: string;
  label: string; // "W35", "W36", ...
  pct_positifs: number | null;
  pct_negatifs: number | null;
  nb_avis: number;
}

export interface WatchyMessage {
  id: string;
  sender: 'user' | 'watchy';
  text: string;
  timestamp: string;
  citations?: string[]; // array of client_id or avis_id
  recommendedActions?: string[];
  replyDraft?: {
    forClientId: string;
    reviewSnippet: string;
    tone: 'professionnel' | 'chaleureux' | 'commercial';
    draftText: string;
  };
}

export interface BusinessLeaderboardEntry {
  business: Business;
  nb_avis: number;
  pct_positifs: number;
  pct_negatifs: number;
  tendance: TrendStatus;
  variation_pts: number | null;
  top_probleme: string;
  top_force: string;
  score_confiance: number;
}
