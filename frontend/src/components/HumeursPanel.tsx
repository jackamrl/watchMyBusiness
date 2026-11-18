import React from 'react';
import { Smile, ShieldQuestion } from 'lucide-react';
import { HumeurCount } from '../types';
import { HUMEURS, ORDRE_HUMEURS } from '../utils/humeurs';

interface HumeursPanelProps {
  humeurs: HumeurCount[];
  nbAVerifier: number;
  nbAvis: number;
  onShowToVerify: () => void;
}

/** Humeur des clients détectée par notre modèle, et avis sur lesquels il hésite. */
export const HumeursPanel: React.FC<HumeursPanelProps> = ({ humeurs, nbAVerifier, nbAvis, onShowToVerify }) => {
  const total = humeurs.reduce((s, h) => s + h.nb, 0) || 1;
  const parHumeur = new Map(humeurs.map((h) => [h.humeur, h.nb]));

  return (
    <section className="h-full rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-xs p-4 sm:p-5 flex flex-col gap-4">
      <div>
        <div className="flex items-center gap-2">
          <Smile className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          <h2 className="text-base font-extrabold text-slate-900 dark:text-white">Humeur des clients</h2>
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
          Détectée par notre modèle dans chaque avis
        </p>
      </div>

      <div className="space-y-2.5">
        {ORDRE_HUMEURS.map((cle) => {
          const nb = parHumeur.get(cle) || 0;
          const pct = Math.round((100 * nb) / total);
          const info = HUMEURS[cle];
          return (
            <div key={cle} className="grid grid-cols-[120px_1fr_32px] items-center gap-3" title={`${pct} % des avis`}>
              <span className="text-xs sm:text-sm text-slate-800 dark:text-slate-200 flex items-center gap-2">
                <span className="text-base w-5 text-center">{info.emoji}</span>
                {info.libelle}
              </span>
              <span className="h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                <span
                  className="block h-full rounded-full transition-all duration-500"
                  style={{ width: `${pct}%`, background: info.couleur }}
                />
              </span>
              <span className="text-xs text-right tabular-nums text-slate-600 dark:text-slate-400">{nb}</span>
            </div>
          );
        })}
      </div>

      <button
        type="button"
        onClick={onShowToVerify}
        disabled={nbAVerifier === 0}
        className="mt-auto flex items-center justify-between gap-3 p-3 rounded-xl bg-violet-50 dark:bg-violet-950/40 border border-violet-200/70 dark:border-violet-800/60 text-left hover:bg-violet-100 dark:hover:bg-violet-950/70 transition cursor-pointer disabled:cursor-default disabled:opacity-70"
      >
        <span className="flex items-center gap-2.5">
          <ShieldQuestion className="w-5 h-5 text-violet-600 dark:text-violet-400 shrink-0" />
          <span>
            <span className="block text-sm font-extrabold text-violet-900 dark:text-violet-200">
              {nbAVerifier} avis à vérifier
            </span>
            <span className="block text-[11px] text-violet-700 dark:text-violet-300">
              le modèle hésite sur {nbAvis ? Math.round((100 * nbAVerifier) / nbAvis) : 0} % des avis de la semaine
            </span>
          </span>
        </span>
        {nbAVerifier > 0 && <span className="text-xs font-bold text-violet-700 dark:text-violet-300">Voir →</span>}
      </button>
    </section>
  );
};
