import React from 'react';
import { AlertCircle, CheckCircle, Bell, X } from 'lucide-react';
import { SentimentType } from '../types';

export interface NotificationToastData {
  id: string;
  sentiment: SentimentType;
  businessName: string;
  theme: string;
  clientId: string;
}

interface NotificationToastProps {
  toast: NotificationToastData | null;
  onDismiss: () => void;
  onViewReview: (clientId: string) => void;
}

export const NotificationToast: React.FC<NotificationToastProps> = ({
  toast,
  onDismiss,
  onViewReview,
}) => {
  if (!toast) return null;

  const isNeg = toast.sentiment === 'NEGATIVE';
  const isPos = toast.sentiment === 'POSITIVE';

  const config = isNeg
    ? {
        border: 'border-rose-400 dark:border-rose-700',
        bg: 'bg-rose-50/95 dark:bg-rose-950/90 text-rose-950 dark:text-rose-100',
        icon: AlertCircle,
        iconColor: 'text-rose-600',
        label: 'Nouvel avis négatif',
      }
    : isPos
    ? {
        border: 'border-emerald-400 dark:border-emerald-700',
        bg: 'bg-emerald-50/95 dark:bg-emerald-950/90 text-emerald-950 dark:text-emerald-100',
        icon: CheckCircle,
        iconColor: 'text-emerald-600',
        label: 'Nouvel avis positif',
      }
    : {
        border: 'border-slate-300 dark:border-slate-700',
        bg: 'bg-white/95 dark:bg-slate-900/90 text-slate-900 dark:text-slate-100',
        icon: Bell,
        iconColor: 'text-slate-500',
        label: 'Nouvel avis collecté',
      };

  const ToastIcon = config.icon;

  return (
    <aside
      aria-label="Notification d'avis"
      className={`fixed top-20 right-4 z-50 max-w-sm rounded-2xl p-3.5 border shadow-xl backdrop-blur-md transition-all duration-300 animate-in slide-in-from-top-6 ${config.border} ${config.bg}`}
    >
      <div className="flex items-start gap-3">
        <ToastIcon className={`w-5 h-5 shrink-0 mt-0.5 ${config.iconColor}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-extrabold uppercase tracking-wide">
              {config.label}
            </span>
            <button
              type="button"
              onClick={onDismiss}
              className="text-slate-400 hover:text-slate-600 p-0.5 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          <p className="text-xs font-semibold mt-0.5 truncate">
            {toast.businessName} · <span className="font-normal">{toast.theme}</span>
          </p>

          <div className="flex items-center justify-between gap-2 mt-2 pt-1 border-t border-slate-200/50 dark:border-slate-700/50">
            <span className="text-[10px] font-mono text-slate-500">
              ID: {toast.clientId}
            </span>
            <button
              type="button"
              onClick={() => {
                onViewReview(toast.clientId);
                onDismiss();
              }}
              className="text-xs font-bold underline hover:opacity-80 cursor-pointer"
            >
              Afficher l&apos;avis
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
};
