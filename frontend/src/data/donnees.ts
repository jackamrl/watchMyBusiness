/**
 * Données réelles du tableau de bord.
 *
 * `donnees-modele.json` est produit par `python -m nlp tableau-demo` dans le dépôt
 * watchMyBusiness : les vrais avis de L'As du Fallafel (Google Maps + TripAdvisor),
 * chacun classé par NOTRE modèle NLP (sentiment, humeur, thèmes, confiance), puis
 * agrégés par semaine avec les mêmes règles que le rapport du lundi.
 * Aucune donnée inventée : tout ce que l'interface affiche vient de ce fichier.
 */
import {
  Business,
  Category,
  Humeur,
  HumeurCount,
  Review,
  SentimentType,
  WeeklyTrendPoint,
} from '../types';
import brut from './donnees-modele.json';

interface ThemeBrut {
  theme: string;
  libelle: string;
  polarite: 'positif' | 'negatif' | 'neutre';
}

interface AvisBrut {
  review_id: string;
  date_avis: string;
  note: number | null;
  texte: string;
  source: 'Google' | 'TripAdvisor';
  sentiment: 'POSITIF' | 'NEGATIF' | 'NEUTRE' | 'MIXTE';
  humeur: Humeur | null;
  confiance: number;
  a_verifier: boolean;
  themes: ThemeBrut[];
}

interface ClassementBrut {
  theme: string;
  libelle: string;
  occurrences: number;
  part: number;
  exemples: { extrait: string }[];
}

export interface RapportBrut {
  semaine_id: string;
  periode_debut: string;
  periode_fin: string;
  nb_avis: number;
  note_moyenne: number | null;
  nb_positif: number;
  nb_negatif: number;
  nb_neutre: number;
  nb_mixte: number;
  pct_positif: number;
  pct_negatif: number;
  pct_neutre: number;
  pct_mixte: number;
  nb_a_verifier: number;
  tendance: 'positive' | 'negative' | 'mitigee' | 'aucune';
  top_negatifs: ClassementBrut[];
  top_positifs: ClassementBrut[];
  humeurs: HumeurCount[];
  synthese: string;
  modele: string;
}

const donnees = brut as unknown as {
  modele: { version: string; seuil_confiance: number };
  rapports: RapportBrut[];
  avis: AvisBrut[];
};

export const MODELE = donnees.modele;
export const ETABLISSEMENT_ID = 'as-du-fallafel';
const NB_SEMAINES = 12;

const SENTIMENTS: Record<AvisBrut['sentiment'], SentimentType> = {
  POSITIF: 'POSITIVE',
  NEGATIF: 'NEGATIVE',
  NEUTRE: 'NEUTRAL',
  MIXTE: 'MIXED',
};

/** Les 8 thèmes de la taxonomie « restaurant » utilisée par le modèle. */
export const THEMES_RESTAURANT = [
  'Qualité de la cuisine',
  'Attente',
  'Service et accueil',
  'Prix',
  'Cadre et ambiance',
  'Hygiène',
  'Régularité',
  'Vente à emporter',
];

export const CATEGORIES: Category[] = [
  {
    id: 'restaurants',
    label: 'Restaurants',
    icon: '🍽️',
    description: 'Restauration rapide et tables traditionnelles',
    themes: THEMES_RESTAURANT,
  },
];

export const BUSINESSES: Business[] = [
  {
    id: ETABLISSEMENT_ID,
    name: "L'As du Fallafel",
    category: 'restaurants',
    city: 'Paris 4e (Le Marais)',
    rating: 4.3,
    totalReviews: 14741,
    address: '34 Rue des Rosiers, 75004 Paris',
  },
];

const moisCourt = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });

/** Rapports des 12 dernières semaines, la plus récente en premier. */
export const RAPPORTS: RapportBrut[] = [...donnees.rapports]
  .sort((a, b) => b.periode_debut.localeCompare(a.periode_debut))
  .slice(0, NB_SEMAINES);

export const WEEKS_LIST = RAPPORTS.map((r, i) => ({
  id: r.semaine_id,
  label: `Semaine ${r.semaine_id}`,
  dates: `Du ${moisCourt(r.periode_debut)} au ${moisCourt(r.periode_fin)}`,
  isCurrent: i === 0,
}));

const semaineDe = (iso: string) =>
  RAPPORTS.find((r) => r.periode_debut <= iso && iso <= r.periode_fin)?.semaine_id;

/** Identifiant court et anonyme d'un avis, cité par l'assistant : AV-0001… */
export const INITIAL_REVIEWS: Review[] = donnees.avis
  .filter((a) => semaineDe(a.date_avis))
  .sort((a, b) => a.date_avis.localeCompare(b.date_avis))
  .map((a, i) => ({
    avis_id: a.review_id,
    date: `${a.date_avis}T12:00:00`,
    semaine_id: semaineDe(a.date_avis)!,
    client_id: `AV-${String(i + 1).padStart(4, '0')}`,
    etablissement_id: ETABLISSEMENT_ID,
    note_google: a.note ?? 0,
    texte: a.texte,
    sentiment: SENTIMENTS[a.sentiment],
    score: a.confiance,
    themes: a.themes.map((t) => t.libelle),
    themes_detail: a.themes.map((t) => ({ libelle: t.libelle, polarite: t.polarite })),
    humeur: a.humeur,
    a_verifier: a.a_verifier,
    source: a.source,
  }));

export const HISTORICAL_TRENDS_BY_BUSINESS: Record<string, WeeklyTrendPoint[]> = {
  [ETABLISSEMENT_ID]: [...RAPPORTS].reverse().map((r) => ({
    semaine_id: r.semaine_id,
    label: r.semaine_id.slice(5),
    pct_positifs: r.nb_avis ? r.pct_positif : null,
    pct_negatifs: r.nb_avis ? r.pct_negatif : null,
    nb_avis: r.nb_avis,
  })),
};

export const DERNIER_AVIS = donnees.avis.reduce(
  (max, a) => (a.date_avis > max ? a.date_avis : max),
  '',
);
