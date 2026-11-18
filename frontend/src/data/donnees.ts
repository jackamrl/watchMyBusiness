/**
 * Référentiels d'affichage. Les avis et rapports viennent de l'API BigQuery
 * (`src/services/api.ts` → Cloud Run `/api/...`).
 */
import { Business, Category } from '../types';

export const MODELE = {
  version: 'fallafel-v3+fallafel-v4',
  seuil_confiance: 0.92,
};

export const ETABLISSEMENT_ID = 'as-du-fallafel';

export const CATEGORIES: Category[] = [
  {
    id: 'restaurants',
    label: 'Restaurants',
    icon: 'utensils',
    description: 'Restauration rapide et tables',
    themes: [
      'Qualité de la cuisine',
      'Service et accueil',
      'Attente',
      'Prix',
      'Cadre et ambiance',
      'Hygiène',
    ],
  },
  {
    id: 'bars_pmu',
    label: 'Bars / PMU',
    icon: 'beer',
    description: 'Bars et points de jeu',
    themes: ['Service et accueil', 'Prix', 'Cadre et ambiance'],
  },
  {
    id: 'cafes_brasseries',
    label: 'Cafés',
    icon: 'coffee',
    description: 'Cafés et brasseries',
    themes: ['Service et accueil', 'Qualité de la cuisine', 'Cadre et ambiance'],
  },
  {
    id: 'boulangeries',
    label: 'Boulangeries',
    icon: 'croissant',
    description: 'Boulangeries et pâtisseries',
    themes: ['Qualité de la cuisine', 'Attente', 'Prix'],
  },
  {
    id: 'hotels',
    label: 'Hôtels',
    icon: 'bed',
    description: 'Hôtellerie',
    themes: ['Service et accueil', 'Hygiène', 'Cadre et ambiance'],
  },
];

export const BUSINESSES: Business[] = [
  {
    id: 'as-du-fallafel',
    name: "L'As du Fallafel",
    category: 'restaurants',
    city: 'Paris',
    rating: 4.3,
    totalReviews: 14741,
    address: '34 Rue des Rosiers, 75004 Paris',
  },
];

/** Conservé pour compatibilité d'import ; remplacé au chargement par l'API. */
export const WEEKS_LIST: { id: string; label: string; dates: string }[] = [];
export const DERNIER_AVIS = new Date().toISOString().slice(0, 10);
export const HISTORICAL_TRENDS_BY_BUSINESS: Record<string, unknown[]> = {};
