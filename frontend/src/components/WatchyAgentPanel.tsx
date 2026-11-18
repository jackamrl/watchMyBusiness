import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Sparkles,
  Bot,
  ChevronRight,
  ChevronLeft,
  Copy,
  Check,
  RefreshCw,
  Lightbulb,
  ExternalLink,
  MessageSquareReply,
  HelpCircle,
} from 'lucide-react';
import { WatchyEyeLogo } from './WatchyEyeLogo';
import { Review, WeeklyReport, WatchyMessage } from '../types';
import { apiService } from '../services/api';

interface WatchyAgentPanelProps {
  businessName: string;
  categoryLabel: string;
  currentWeekLabel: string;
  report: WeeklyReport;
  reviews: Review[];
  isOpen: boolean;
  onToggleOpen: () => void;
  activeDraftReview: Review | null;
  onClearActiveDraftReview: () => void;
  onCitationClick: (clientId: string) => void;
}

export const WatchyAgentPanel: React.FC<WatchyAgentPanelProps> = ({
  businessName,
  categoryLabel,
  currentWeekLabel,
  report,
  reviews,
  isOpen,
  onToggleOpen,
  activeDraftReview,
  onClearActiveDraftReview,
  onCitationClick,
}) => {
  const [messages, setMessages] = useState<WatchyMessage[]>([
    {
      id: 'welcome',
      sender: 'watchy',
      text: `Bonjour ! Je suis **Watchy**, votre analyste dédié. J'ai lu les ${report.nb_avis} avis de **${businessName}** sur la **${currentWeekLabel}**, tels que notre modèle les a classés.\n\nJe réponds uniquement à partir de ces chiffres et je cite les avis concernés. Posez une question ou choisissez une suggestion ci-dessous.`,
      timestamp: 'À l instant',
    },
  ]);

  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Draft review reply states
  const [draftTone, setDraftTone] = useState<'professionnel' | 'chaleureux' | 'commercial'>('professionnel');
  const [draftText, setDraftText] = useState('');
  const [isDraftLoading, setIsDraftLoading] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const suggestions = [
    'Résume ma semaine',
    'Quel est mon problème n°1 ?',
    "Que disent les clients sur l'attente ?",
    'Compare avec la semaine précédente',
    'Quels avis dois-je vérifier ?',
  ];

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // When active draft review changes, generate initial draft
  useEffect(() => {
    if (activeDraftReview) {
      generateDraft(activeDraftReview, draftTone);
    }
  }, [activeDraftReview, draftTone]);

  const generateDraft = async (
    review: Review,
    tone: 'professionnel' | 'chaleureux' | 'commercial'
  ) => {
    setIsDraftLoading(true);
    try {
      const text = await apiService.draftReply(review, tone, businessName);
      setDraftText(text);
    } catch {
      setDraftText(`Bonjour,\n\nMerci pour votre retour sur ${businessName}. Nous prenons bien note de vos remarques et mettons tout en œuvre pour nous améliorer.\n\nCordialement,\nLa direction.`);
    } finally {
      setIsDraftLoading(false);
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const prompt = textToSend || inputValue;
    if (!prompt.trim() || isLoading) return;

    const userMsg: WatchyMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: prompt,
      timestamp: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInputValue('');
    setIsLoading(true);

    try {
      const res = await apiService.chatWithWatchy(prompt, {
        businessName,
        category: categoryLabel,
        weekLabel: currentWeekLabel,
        report,
        reviews,
      });

      const watchyMsg: WatchyMessage = {
        id: `watchy-${Date.now()}`,
        sender: 'watchy',
        text: res.text,
        timestamp: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
        citations: res.citations,
        recommendedActions: res.recommendedActions,
      };

      setMessages((prev) => [...prev, watchyMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'watchy',
          text: "Désolé, je n'ai pas pu analyser cette question. Les données de la semaine restent consultables.",
          timestamp: 'À l instant',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = () => {
    if (!draftText) return;
    navigator.clipboard.writeText(draftText);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  // Citations cliquables [AV-xxxx] vers l'avis dans le flux
  const renderMessageContent = (text: string) => {
    const parts = text.split(/(\[AV-\d{4}\]|AV-\d{4})/g);

    return (
      <div className="space-y-2 whitespace-pre-wrap">
        {parts.map((part, index) => {
          const match = part.match(/AV-\d{4}/);
          if (match) {
            const clientId = match[0];
            return (
              <button
                key={index}
                type="button"
                onClick={() => onCitationClick(clientId)}
                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded font-mono font-bold text-xs bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200 hover:underline cursor-pointer border border-emerald-300 dark:border-emerald-700"
                title={`Cliquer pour afficher l'avis de ${clientId} dans le flux`}
              >
                <span>[{clientId}]</span>
                <ExternalLink className="w-2.5 h-2.5 ml-0.5 opacity-70" />
              </button>
            );
          }

          // Simple bold formatting
          const boldParts = part.split(/(\*\*.*?\*\*)/g);
          return (
            <span key={index}>
              {boldParts.map((sub, sIdx) => {
                if (sub.startsWith('**') && sub.endsWith('**')) {
                  return <strong key={sIdx} className="font-extrabold">{sub.slice(2, -2)}</strong>;
                }
                return sub;
              })}
            </span>
          );
        })}
      </div>
    );
  };

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={onToggleOpen}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2.5 px-4 py-3 rounded-2xl bg-slate-900 dark:bg-emerald-600 text-white shadow-2xl hover:scale-105 transition-all cursor-pointer border border-slate-700/80 group"
        aria-label="Ouvrir l'assistant Watchy"
      >
        <WatchyEyeLogo size="sm" showText={false} />
        <span className="font-bold text-sm">Parler à Watchy</span>
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
      </button>
    );
  }

  return (
    <aside
      className="fixed inset-y-0 right-0 z-40 w-full sm:w-[380px] lg:w-[400px] bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col transition-all duration-300"
      aria-label="Panneau assistant Watchy"
    >
      {/* Header */}
      <div className="p-4 border-b border-slate-200/90 dark:border-slate-800 flex items-center justify-between bg-slate-50/80 dark:bg-slate-800/60 backdrop-blur-xs">
        <div className="flex items-center gap-2.5">
          <WatchyEyeLogo size="sm" showText={false} />
          <div>
            <div className="flex items-center gap-1.5">
              <h2 className="font-extrabold text-sm text-slate-900 dark:text-white">
                Agent Watchy
              </h2>
              <span className="px-1.5 py-0.2 rounded-full text-[9px] font-extrabold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                agent maison
              </span>
            </div>
            <div className="flex items-center gap-1 text-[11px] text-slate-600 dark:text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
              <span>Analyse la semaine {report.semaine_id}</span>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={onToggleOpen}
          aria-label="Réduire le panneau Watchy"
          className="p-1.5 rounded-xl hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition cursor-pointer"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      {/* Draft Reply Modal / Drawer Mode (when an active review is selected) */}
      {activeDraftReview && (
        <div className="p-4 bg-indigo-50/90 dark:bg-indigo-950/60 border-b border-indigo-200 dark:border-indigo-800 flex flex-col gap-2.5 animate-in slide-in-from-top duration-200">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-extrabold text-indigo-900 dark:text-indigo-200">
              <MessageSquareReply className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              Brouillon de réponse · {activeDraftReview.client_id}
            </span>
            <button
              type="button"
              onClick={onClearActiveDraftReview}
              className="text-xs text-indigo-700 dark:text-indigo-300 hover:underline cursor-pointer font-semibold"
            >
              Fermer
            </button>
          </div>

          <div className="text-[11px] text-slate-700 dark:text-slate-300 bg-white/80 dark:bg-slate-900/80 p-2.5 rounded-xl border border-indigo-200/80 dark:border-indigo-900/80 italic leading-snug">
            « {activeDraftReview.texte.slice(0, 110)}... »
          </div>

          {/* Tone Selector */}
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase text-slate-600 dark:text-slate-400">
              Ton :
            </span>
            {(['professionnel', 'chaleureux', 'commercial'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setDraftTone(t)}
                className={`text-[10px] font-bold px-2 py-0.5 rounded-md capitalize transition cursor-pointer ${
                  draftTone === t
                    ? 'bg-indigo-700 text-white shadow-xs'
                    : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700'
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Text Area for editing */}
          <div className="relative">
            {isDraftLoading ? (
              <div className="h-32 flex items-center justify-center bg-white dark:bg-slate-900 rounded-xl border border-indigo-200 dark:border-indigo-800">
                <RefreshCw className="w-5 h-5 text-indigo-600 animate-spin" />
                <span className="text-xs text-slate-600 dark:text-slate-400 ml-2">
                  Génération par Watchy...
                </span>
              </div>
            ) : (
              <textarea
                value={draftText}
                onChange={(e) => setDraftText(e.target.value)}
                rows={5}
                className="w-full text-xs p-2.5 rounded-xl bg-white dark:bg-slate-900 border border-indigo-200 dark:border-indigo-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 leading-relaxed font-sans"
              />
            )}
          </div>

          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => generateDraft(activeDraftReview, draftTone)}
              className="text-[11px] font-bold text-indigo-700 dark:text-indigo-300 hover:underline flex items-center gap-1 cursor-pointer"
            >
              <RefreshCw className="w-3 h-3" />
              Régénérer
            </button>

            <button
              type="button"
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 text-xs font-bold transition cursor-pointer shadow-xs"
            >
              {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-300" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{isCopied ? 'Copié !' : 'Copier la réponse'}</span>
            </button>
          </div>
        </div>
      )}

      {/* Suggested prompts chips */}
      <div className="p-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
        <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-600 dark:text-slate-400 block mb-1.5">
          Suggestions rapides :
        </span>
        <div className="flex flex-wrap gap-1.5">
          {suggestions.map((s, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleSendMessage(s)}
              disabled={isLoading}
              className="text-[11px] text-left px-2.5 py-1 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 hover:border-emerald-500 hover:text-emerald-700 dark:hover:text-emerald-300 transition cursor-pointer disabled:opacity-50"
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => {
          const isUser = msg.sender === 'user';

          return (
            <div
              key={msg.id}
              className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`max-w-[90%] p-3.5 rounded-2xl text-xs sm:text-sm leading-relaxed ${
                  isUser
                    ? 'bg-slate-900 text-white dark:bg-emerald-600 rounded-br-xs shadow-xs'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-bl-xs border border-slate-200/60 dark:border-slate-700/60'
                }`}
              >
                {!isUser && (
                  <div className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-800 dark:text-emerald-300 mb-1.5">
                    <Bot className="w-3.5 h-3.5" />
                    <span>Watchy</span>
                  </div>
                )}

                {renderMessageContent(msg.text)}

                {/* Recommended Actions Card */}
                {msg.recommendedActions && msg.recommendedActions.length > 0 && (
                  <div className="mt-3 pt-2.5 border-t border-slate-200/80 dark:border-slate-700/80">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-amber-800 dark:text-amber-300 mb-2">
                      <Lightbulb className="w-3.5 h-3.5 text-amber-500" />
                      <span>Actions recommandées pour la semaine suivante :</span>
                    </div>
                    <ol className="space-y-1.5 text-xs">
                      {msg.recommendedActions.map((action, aIdx) => (
                        <li
                          key={aIdx}
                          className="flex items-start gap-2 bg-white/70 dark:bg-slate-900/60 p-2 rounded-lg border border-slate-200/50 dark:border-slate-700/50"
                        >
                          <span className="w-4 h-4 rounded-full bg-amber-500 text-white font-bold text-[10px] flex items-center justify-center shrink-0 mt-0.5">
                            {aIdx + 1}
                          </span>
                          <span className="text-slate-800 dark:text-slate-200">{action}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>

              <span className="text-[10px] text-slate-600 dark:text-slate-400 mt-1 px-1">
                {msg.timestamp}
              </span>
            </div>
          );
        })}

        {isLoading && (
          <div className="flex items-center gap-2 p-3 bg-slate-100 dark:bg-slate-800 rounded-2xl w-fit">
            <RefreshCw className="w-4 h-4 text-emerald-600 animate-spin" />
            <span className="text-xs text-slate-600 dark:text-slate-400">
              Watchy analyse les données...
            </span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSendMessage();
        }}
        className="p-3 border-t border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900"
      >
        <div className="relative flex items-center">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Posez une question à Watchy..."
            className="w-full pl-3.5 pr-10 py-2.5 text-xs sm:text-sm rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isLoading}
            aria-label="Envoyer le message"
            className="absolute right-2 p-1.5 rounded-lg bg-emerald-600 text-white disabled:opacity-40 hover:bg-emerald-700 transition cursor-pointer"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
      </form>
    </aside>
  );
};
