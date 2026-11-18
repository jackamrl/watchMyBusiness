import React, { useState } from 'react';
import { Lock, Mail, ArrowRight, ShieldCheck } from 'lucide-react';
import { WatchyEyeLogo } from './WatchyEyeLogo';

interface AuthModalProps {
  isOpen: boolean;
  onLogin: (email: string) => void;
  onClose?: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onLogin,
}) => {
  const [email, setEmail] = useState('gerant@watchmybusiness.fr');
  const [password, setPassword] = useState('••••••••••••');
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Veuillez renseigner votre e-mail et votre mot de passe.');
      return;
    }
    setError('');
    onLogin(email);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl p-6 sm:p-8 animate-in fade-in zoom-in-95 duration-200">
        <div className="text-center flex flex-col items-center">
          <WatchyEyeLogo size="lg" />
          <h2 className="text-xl font-extrabold text-slate-900 dark:text-white mt-4">
            Connexion à votre espace gérant
          </h2>
          <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 max-w-xs">
            Surveillez en continu vos avis Google Maps et bénéficiez de l&apos;analyse de notre modèle NLP et de l&apos;assistant Watchy.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
              Adresse e-mail
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3 pointer-events-none" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="gerant@commerce.fr"
                className="w-full pl-10 pr-3.5 py-2.5 text-xs sm:text-sm rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
              Mot de passe
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3 pointer-events-none" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-10 pr-3.5 py-2.5 text-xs sm:text-sm rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
              />
            </div>
          </div>

          {error && (
            <div className="p-2.5 rounded-xl bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-slate-900 text-white dark:bg-emerald-600 hover:bg-slate-800 dark:hover:bg-emerald-500 font-extrabold text-sm shadow-md transition cursor-pointer"
          >
            <span>Se connecter</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 text-center">
          <div className="flex items-center justify-center gap-1.5 text-[11px] text-slate-600 dark:text-slate-400">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>Prêt pour l&apos;authentification sécurisée AWS Cognito</span>
          </div>
          <p className="text-[10px] text-slate-600 dark:text-slate-400 mt-1">
            Démo active : vous pouvez vous connecter directement en un clic.
          </p>
        </div>
      </div>
    </div>
  );
};
