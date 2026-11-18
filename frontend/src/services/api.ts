import {
  WeeklyReport,
  Review,
  DailyVolume,
  BusinessLeaderboardEntry,
  ThemeMetric,
  SentimentType,
  Humeur,
} from '../types';
import { BUSINESSES } from '../data/donnees';
import { calculateAverageConfidence, determineBusinessWeather } from '../utils/metrics';

/** Base de l'API BigQuery (Cloud Run). Vide = même origine (prod) ou proxy Vite. */
const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? '';
const ETAB = 'as-du-fallafel';

export type MoteurAnalyse = 'maison' | 'gemini';

let moteurCourant: MoteurAnalyse = 'maison';

export function setMoteur(moteur: MoteurAnalyse) {
  moteurCourant = moteur;
}

export function getMoteur(): MoteurAnalyse {
  return moteurCourant;
}

const SENTIMENT_API: Record<string, SentimentType> = {
  POSITIF: 'POSITIVE',
  NEGATIF: 'NEGATIVE',
  NEUTRE: 'NEUTRAL',
  MIXTE: 'MIXED',
  POSITIVE: 'POSITIVE',
  NEGATIVE: 'NEGATIVE',
  NEUTRAL: 'NEUTRAL',
  MIXED: 'MIXED',
};

async function getJson<T>(chemin: string): Promise<T> {
  const sep = chemin.includes('?') ? '&' : '?';
  const url = `${API_BASE}${chemin}${sep}moteur=${moteurCourant}`;
  const reponse = await fetch(url);
  if (!reponse.ok) throw new Error(`API ${reponse.status} sur ${chemin}`);
  return reponse.json();
}

function formaterJour(iso: string): string {
  const nom = new Date(`${iso}T12:00:00`).toLocaleDateString('fr-FR', {
    weekday: 'short',
    day: 'numeric',
  });
  return nom.charAt(0).toUpperCase() + nom.slice(1).replace('.', '');
}

function formaterPlage(debut: string, fin: string): { debut: string; fin: string } {
  const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'long' };
  return {
    debut: new Date(`${debut}T12:00:00`).toLocaleDateString('fr-FR', opts),
    fin: new Date(`${fin}T12:00:00`).toLocaleDateString('fr-FR', opts),
  };
}

function clientId(reviewId: string, index: number): string {
  const hash = Math.abs(
    [...reviewId].reduce((a, c) => ((a << 5) - a + c.charCodeAt(0)) | 0, 0),
  );
  return `AV-${String((hash % 9000) + 1000 + index).padStart(4, '0')}`;
}

function themesClasses(themes: any[], precedent?: any[]): ThemeMetric[] {
  return (themes || []).map((t) => {
    const avant = precedent?.find((p) => p.theme === t.theme);
    const ecart =
      avant != null ? Math.round((t.part - (avant.part ?? 0)) * 10) / 10 : undefined;
    return {
      theme: t.libelle || t.theme,
      libelle: t.libelle || t.theme,
      occurrences: t.occurrences,
      pourcentage: t.part,
      variation_pts: ecart,
      tendance:
        ecart === undefined ? undefined : ecart > 0.5 ? 'hausse' : ecart < -0.5 ? 'baisse' : 'stable',
      citations: (t.exemples || []).map((e: { extrait: string }) => e.extrait),
    };
  });
}

function mapAvis(brut: any, semaineId: string, index: number): Review {
  return {
    avis_id: brut.review_id,
    date: `${brut.date_avis}T12:00:00`,
    semaine_id: semaineId,
    client_id: clientId(brut.review_id, index),
    etablissement_id: ETAB,
    note_google: brut.note ?? 0,
    texte: brut.texte || '',
    sentiment: SENTIMENT_API[brut.sentiment] || 'NEUTRAL',
    score: brut.confiance ?? Math.abs(brut.score ?? 0),
    themes: (brut.themes || []).map((t: any) => t.libelle || t.theme),
    themes_detail: (brut.themes || []).map((t: any) => ({
      libelle: t.libelle || t.theme,
      polarite: t.polarite,
    })),
    humeur: (brut.humeur as Humeur) || null,
    a_verifier: Boolean(brut.a_verifier),
    source: brut.review_id?.startsWith('tripadvisor-') ? 'TripAdvisor' : 'Google',
  };
}

export interface RapportsSummaryItem {
  semaine_id: string;
  debut: string;
  fin: string;
  nb_avis: number;
  pct_positifs: number;
  pct_negatifs: number;
  tendance: 'positive' | 'negative' | 'mitigee' | 'indeterminee';
}

export interface GetRapportsResponse {
  nb: number;
  rapports: RapportsSummaryItem[];
}

export interface GetAvisResponse {
  nb: number;
  avis: Review[];
}

export const apiService = {
  async getRapports(): Promise<GetRapportsResponse> {
    const data = await getJson<{ rapports: any[] }>(
      `/api/rapports?etablissement=${ETAB}&limite=26`,
    );
    const rapports = data.rapports.map((r) => {
      const plage = formaterPlage(r.periode_debut, r.periode_fin);
      const meteo = determineBusinessWeather(r.pct_positif, r.pct_negatif, null, r.nb_avis);
      return {
        semaine_id: r.semaine_id,
        debut: plage.debut,
        fin: plage.fin,
        nb_avis: r.nb_avis,
        pct_positifs: r.pct_positif,
        pct_negatifs: r.pct_negatif,
        tendance: meteo.tendance,
      };
    });
    return { nb: rapports.length, rapports };
  },

  async getRapportDetail(semaine_id: string): Promise<WeeklyReport> {
    const r = await getJson<any>(
      `/api/rapports/${encodeURIComponent(semaine_id)}?etablissement=${ETAB}`,
    );
    const plage = formaterPlage(r.periode_debut, r.periode_fin);
    const cmp = r.comparaison_semaine_precedente;
    const variationPts = cmp?.delta_pct_positif ?? null;
    const meteo = determineBusinessWeather(
      r.pct_positif,
      r.pct_negatif,
      variationPts,
      r.nb_avis,
    );

    const avisResp = await apiService.getAvis(semaine_id, r.periode_debut, r.periode_fin);
    const avis = avisResp.avis;

    const volume_par_jour: DailyVolume[] = (r.volume_par_jour || []).map((j: any) => {
      const duJour = avis.filter((a) => a.date.startsWith(j.date));
      return {
        date: j.date,
        jourNom: formaterJour(j.date),
        nb: j.nb_avis ?? j.nb ?? duJour.length,
        positifs: duJour.filter((a) => a.sentiment === 'POSITIVE').length,
        negatifs: duJour.filter((a) => a.sentiment === 'NEGATIVE').length,
        neutres: duJour.filter((a) => a.sentiment === 'NEUTRAL').length,
        mitiges: duJour.filter((a) => a.sentiment === 'MIXED').length,
      };
    });

    return {
      semaine_id: r.semaine_id,
      debut: plage.debut,
      fin: plage.fin,
      nb_avis: r.nb_avis,
      repartition: {
        POSITIVE: r.nb_positif,
        NEGATIVE: r.nb_negatif,
        NEUTRAL: r.nb_neutre,
        MIXED: r.nb_mixte,
      },
      pct_positifs: r.pct_positif,
      pct_negatifs: r.pct_negatif,
      pct_neutres_mitiges: Math.round(((r.pct_neutre || 0) + (r.pct_mixte || 0)) * 10) / 10,
      score_confiance_moyen: calculateAverageConfidence(avis),
      tendance: meteo.tendance,
      variation_pts: variationPts,
      meteo: meteo.meteo,
      meteo_libelle: meteo.meteoLibelle,
      volume_par_jour,
      themes_negatifs: themesClasses(r.top_negatifs),
      themes_positifs: themesClasses(r.top_positifs),
      humeurs: r.humeurs || [],
      nb_a_verifier: r.nb_a_verifier || 0,
      note_moyenne: r.note_moyenne,
      synthese: r.synthese || '',
    };
  },

  async getAvis(
    semaine_id: string,
    debut?: string,
    fin?: string,
  ): Promise<GetAvisResponse> {
    let d = debut;
    let f = fin;
    if (!d || !f) {
      const detail = await getJson<any>(
        `/api/rapports/${encodeURIComponent(semaine_id)}?etablissement=${ETAB}`,
      );
      d = detail.periode_debut;
      f = detail.periode_fin;
    }
    const data = await getJson<{ nb: number; avis: any[] }>(
      `/api/avis?etablissement=${ETAB}&debut=${d}&fin=${f}`,
    );
    return {
      nb: data.nb,
      avis: data.avis.map((a, i) => mapAvis(a, semaine_id, i)),
    };
  },

  async getLeaderboard(_categoryId: string, semaine_id: string): Promise<BusinessLeaderboardEntry[]> {
    const report = await apiService.getRapportDetail(semaine_id);
    return BUSINESSES.map((business) => ({
      business,
      nb_avis: report.nb_avis,
      pct_positifs: report.pct_positifs,
      pct_negatifs: report.pct_negatifs,
      tendance: report.tendance,
      variation_pts: report.variation_pts,
      top_probleme: report.themes_negatifs[0]?.libelle || 'Aucun problème majeur',
      top_force: report.themes_positifs[0]?.libelle || 'Satisfaction globale',
      score_confiance: report.score_confiance_moyen,
    }));
  },

  async chatWithWatchy(
    prompt: string,
    context: {
      businessName: string;
      category: string;
      weekLabel: string;
      report: WeeklyReport;
      reviews: Review[];
    },
  ): Promise<{ text: string; citations: string[]; recommendedActions?: string[] }> {
    return repondre(prompt, context);
  },

  async draftReply(
    review: Review,
    tone: 'professionnel' | 'chaleureux' | 'commercial',
    businessName: string,
  ): Promise<string> {
    return brouillonReponse(review, tone, businessName);
  },
};

/* ---------------------------------------------------------------------- */
/* Assistant Watchy : agent à règles, sans modèle externe                  */
/* ---------------------------------------------------------------------- */

const fr = (x: number | null | undefined) => (x == null ? '—' : String(x).replace('.', ','));

const ACTIONS: Record<string, string> = {
  Attente:
    "Renforcer le service aux heures de pointe et afficher le temps d'attente estimé dans la file.",
  'Service et accueil':
    "Faire un point d'équipe sur l'accueil : sourire, explication du fonctionnement de la file.",
  Prix: 'Rendre les prix plus visibles avant la commande et valoriser les portions.',
  'Qualité de la cuisine':
    'Vérifier la régularité des recettes et la fraîcheur des ingrédients sur les créneaux chargés.',
  'Cadre et ambiance':
    'Améliorer le confort de la salle (bruit, places assises) aux heures de pointe.',
  Hygiène: 'Renforcer la fréquence de nettoyage des tables et de la salle pendant le service.',
  Régularité: 'Standardiser les portions et la préparation entre les équipes.',
  'Vente à emporter': "Vérifier l'emballage et la rapidité de la vente à emporter.",
};

function avisSur(reviews: Review[], libelle: string, polarite: 'negatif' | 'positif'): Review[] {
  return reviews.filter((r) =>
    r.themes_detail?.some((t) => t.libelle === libelle && t.polarite === polarite),
  );
}

function repondre(
  prompt: string,
  ctx: { businessName: string; weekLabel: string; report: WeeklyReport; reviews: Review[] },
): { text: string; citations: string[]; recommendedActions?: string[] } {
  const q = prompt
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
  const r = ctx.report;
  const neg = r.themes_negatifs[0];
  const pos = r.themes_positifs[0];
  const citations: string[] = [];
  const citer = (liste: Review[]) => {
    const a = liste[0];
    if (a) citations.push(a.client_id);
    return a ? ` (voir [${a.client_id}])` : '';
  };
  const variation =
    r.variation_pts == null
      ? 'pas de semaine précédente pour comparer'
      : `${r.variation_pts > 0 ? '+' : ''}${fr(r.variation_pts)} pts d'avis positifs par rapport à la semaine précédente`;

  if (r.nb_avis === 0) {
    return { text: `Aucun avis n'a été collecté sur la ${ctx.weekLabel}.`, citations };
  }

  const themeDemande = [...r.themes_negatifs, ...r.themes_positifs]
    .map((t) => t.libelle)
    .find((l) =>
      q.includes(
        l
          .toLowerCase()
          .normalize('NFD')
          .replace(/[\u0300-\u036f]/g, '')
          .split(' ')[0],
      ),
    );
  if (themeDemande && !q.includes('resume')) {
    const n = avisSur(ctx.reviews, themeDemande, 'negatif');
    const p = avisSur(ctx.reviews, themeDemande, 'positif');
    return {
      text:
        `Sur la ${ctx.weekLabel}, le thème **« ${themeDemande} »** apparaît dans **${n.length} avis négatifs**` +
        `${citer(n)} et **${p.length} avis positifs**${citer(p)}.` +
        (n.length > p.length
          ? "\n\nC'est un point d'effort cette semaine."
          : "\n\nC'est plutôt un point fort cette semaine."),
      citations,
      recommendedActions: n.length && ACTIONS[themeDemande] ? [ACTIONS[themeDemande]] : undefined,
    };
  }

  if (q.includes('pourquoi') || q.includes('negati') || q.includes('probleme') || q.includes('priorit')) {
    if (!neg) {
      return {
        text: `Aucun thème négatif récurrent sur la ${ctx.weekLabel} : ${fr(r.pct_negatifs)} % d'avis négatifs seulement.`,
        citations,
      };
    }
    const n = avisSur(ctx.reviews, neg.libelle, 'negatif');
    return {
      text:
        `Le problème n°1 de la ${ctx.weekLabel} est **« ${neg.libelle} »** : ${neg.occurrences} avis négatifs, ` +
        `soit ${fr(neg.pourcentage)} % des critiques classées par thème${citer(n)}.` +
        (neg.citations[0] ? `\n\nUn client écrit : « ${neg.citations[0]} »` : '') +
        (r.themes_negatifs[1]
          ? `\n\nViennent ensuite « ${r.themes_negatifs[1].libelle} » (${r.themes_negatifs[1].occurrences} avis).`
          : ''),
      citations,
      recommendedActions: r.themes_negatifs
        .slice(0, 2)
        .map((t) => ACTIONS[t.libelle])
        .filter(Boolean),
    };
  }

  if (q.includes('compar') || q.includes('precedente') || q.includes('evolu')) {
    return {
      text:
        `Sur la ${ctx.weekLabel} : **${fr(r.pct_positifs)} %** d'avis positifs, ${variation}.` +
        `\n\nVolume : ${r.nb_avis} avis, note moyenne ${fr(r.note_moyenne)} / 5.`,
      citations,
    };
  }

  if (q.includes('verifier') || q.includes('doute') || q.includes('confiance') || q.includes('hesit')) {
    const doutes = ctx.reviews.filter((a) => a.a_verifier);
    return {
      text:
        `Notre modèle hésite sur **${doutes.length} avis** cette semaine${citer(doutes)} : sa confiance est sous ` +
        `son seuil. Ils sont marqués « à vérifier » dans le fil d'avis, à relire avant d'agir.`,
      citations,
    };
  }

  return {
    text:
      `Sur la ${ctx.weekLabel}, **${ctx.businessName}** reçoit **${r.nb_avis} avis** (note moyenne ${fr(r.note_moyenne)} / 5) : ` +
      `**${fr(r.pct_positifs)} % positifs**, ${fr(r.pct_negatifs)} % négatifs, ${variation}.` +
      (pos
        ? `\n\nPoint fort : **« ${pos.libelle} »** (${pos.occurrences} avis positifs${citer(avisSur(ctx.reviews, pos.libelle, 'positif'))}).`
        : '') +
      (neg
        ? `\n\nPoint d'effort : **« ${neg.libelle} »** (${neg.occurrences} avis négatifs${citer(avisSur(ctx.reviews, neg.libelle, 'negatif'))}).`
        : ''),
    citations,
    recommendedActions: neg && ACTIONS[neg.libelle] ? [ACTIONS[neg.libelle]] : undefined,
  };
}

function brouillonReponse(
  review: Review,
  tone: 'professionnel' | 'chaleureux' | 'commercial',
  businessName: string,
): string {
  const theme = (
    review.themes_detail?.find((t) => t.polarite === 'negatif')?.libelle ||
    review.themes[0] ||
    'votre expérience'
  ).toLowerCase();
  if (tone === 'chaleureux') {
    return `Bonjour,\n\nUn grand merci d'avoir pris le temps de partager votre retour sur votre passage chez ${businessName}.\n\nNous sommes sincèrement désolés que votre expérience n'ait pas été à la hauteur concernant ${theme}. Toute l'équipe a lu votre message et nous en tenons compte pour nous améliorer.\n\nAu plaisir de vous accueillir à nouveau,\nL'équipe de ${businessName}`;
  }
  if (tone === 'commercial') {
    return `Bonjour,\n\nNous vous remercions pour votre avis sur ${businessName}.\n\nNous regrettons ce qui s'est passé concernant ${theme} : ce n'est pas le niveau que nous visons. Lors de votre prochaine visite, présentez-vous au comptoir en mentionnant cet avis : nous serons heureux de vous offrir une boisson.\n\nCordialement,\nLa direction de ${businessName}`;
  }
  return `Bonjour,\n\nNous vous remercions d'avoir partagé votre retour sur votre venue chez ${businessName}.\n\nNous prenons bonne note de votre remarque concernant ${theme} et l'avons transmise à l'équipe afin d'y remédier.\n\nNous espérons vous accueillir à nouveau dans de meilleures conditions.\n\nSincères salutations,\nLa gérance de ${businessName}`;
}
