import React from 'react';
import { FileText } from 'lucide-react';

interface SyntheseCardProps {
  synthese: string;
  semaineId: string;
}

/** Synthèse factuelle de la semaine (markdown simple : ##, listes, gras), construite
 * à partir des indicateurs calculés : aucun chiffre n'est rédigé par un modèle. */
export const SyntheseCard: React.FC<SyntheseCardProps> = ({ synthese, semaineId }) => {
  const gras = (texte: string) =>
    texte.split(/(\*\*.*?\*\*)/g).map((p, i) =>
      p.startsWith('**') && p.endsWith('**') ? (
        <strong key={i} className="font-bold text-slate-900 dark:text-white">{p.slice(2, -2)}</strong>
      ) : (
        <React.Fragment key={i}>{p}</React.Fragment>
      ),
    );

  const blocs: React.ReactNode[] = [];
  let liste: string[] = [];
  const fermer = () => {
    if (liste.length) {
      blocs.push(
        <ul key={`l${blocs.length}`} className="space-y-1 pl-4 list-disc marker:text-slate-300 dark:marker:text-slate-600">
          {liste.map((l, i) => <li key={i}>{gras(l)}</li>)}
        </ul>,
      );
      liste = [];
    }
  };
  for (const brute of synthese.split('\n')) {
    const ligne = brute.trim();
    if (!ligne) continue;
    if (ligne.startsWith('## ')) {
      fermer();
      blocs.push(
        <h3 key={`h${blocs.length}`} className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500 dark:text-slate-400 pt-2 first:pt-0">
          {ligne.slice(3)}
        </h3>,
      );
    } else if (ligne.startsWith('- ')) {
      liste.push(ligne.slice(2));
    } else {
      fermer();
      blocs.push(<p key={`p${blocs.length}`}>{gras(ligne)}</p>);
    }
  }
  fermer();

  return (
    <section className="h-full rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-xs p-4 sm:p-5">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          <h2 className="text-base font-extrabold text-slate-900 dark:text-white">Rapport du lundi</h2>
        </div>
        <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">{semaineId}</span>
      </div>
      <div className="space-y-2 text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{blocs}</div>
      <p className="mt-4 text-[11px] text-slate-500 dark:text-slate-400">
        Chiffres calculés à partir des avis classés par notre modèle · envoyé par e-mail chaque lundi à 8 h
      </p>
    </section>
  );
};
