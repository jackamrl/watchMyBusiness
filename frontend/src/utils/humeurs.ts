import { Humeur } from '../types';

/** Les 6 humeurs prédites par notre modèle, de la plus positive à la plus négative. */
export const HUMEURS: Record<Humeur, { libelle: string; emoji: string; couleur: string }> = {
  joie: { libelle: 'Joie', emoji: '😄', couleur: '#16a34a' },
  satisfaction: { libelle: 'Satisfaction', emoji: '🙂', couleur: '#4ade80' },
  neutre: { libelle: 'Neutre', emoji: '😐', couleur: '#94a3b8' },
  deception: { libelle: 'Déception', emoji: '😕', couleur: '#f59e0b' },
  frustration: { libelle: 'Frustration', emoji: '😤', couleur: '#ea580c' },
  colere: { libelle: 'Colère', emoji: '😠', couleur: '#dc2626' },
};

export const ORDRE_HUMEURS: Humeur[] = ['joie', 'satisfaction', 'neutre', 'deception', 'frustration', 'colere'];
