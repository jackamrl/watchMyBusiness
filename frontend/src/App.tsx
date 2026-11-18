/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
  HelpCircle,
  BarChart3,
  Bot,
  LayoutDashboard,
  Layers,
} from 'lucide-react';
import {
  CategoryId,
  WeeklyReport,
  Review,
  BusinessLeaderboardEntry,
  WeeklyTrendPoint,
} from './types';
import { BUSINESSES, CATEGORIES, MODELE } from './data/donnees';
import { apiService, getMoteur, setMoteur, MoteurAnalyse } from './services/api';
import { WeekOption } from './components/WeekSelector';
import { TopBar } from './components/TopBar';
import { BusinessWeather } from './components/BusinessWeather';
import { KpiCard } from './components/KpiCard';
import { SentimentDonut } from './components/SentimentDonut';
import { DailyVolumeChart } from './components/DailyVolumeChart';
import { WeeklyTrendChart } from './components/WeeklyTrendChart';
import { ThemeColumn } from './components/ThemeColumn';
import { ReviewFeed } from './components/ReviewFeed';
import { ComparisonTable } from './components/ComparisonTable';
import { WatchyAgentPanel } from './components/WatchyAgentPanel';
import { NotificationToast, NotificationToastData } from './components/NotificationToast';
import { AuthModal } from './components/AuthModal';
import { HumeursPanel } from './components/HumeursPanel';
import { SyntheseCard } from './components/SyntheseCard';

export default function App() {
  // Navigation & selection state
  const [selectedCategory, setSelectedCategory] = useState<CategoryId>('restaurants');
  const [selectedBusinessId, setSelectedBusinessId] = useState<string>('as-du-fallafel');
  const [selectedWeekId, setSelectedWeekId] = useState<string>('');
  const [weeks, setWeeks] = useState<WeekOption[]>([]);
  const [moteur, setMoteurState] = useState<MoteurAnalyse>(getMoteur());
  const [onlyToVerify, setOnlyToVerify] = useState<boolean>(false);

  // Active filters and UI state
  const [activeThemeFilter, setActiveThemeFilter] = useState<string | null>(null);
  const [highlightedClientId, setHighlightedClientId] = useState<string | null>(null);
  const [isWatchyOpen, setIsWatchyOpen] = useState<boolean>(true);
  const [activeDraftReview, setActiveDraftReview] = useState<Review | null>(null);
  const [toast, setToast] = useState<NotificationToastData | null>(null);
  const [lastCollectTime, setLastCollectTime] = useState<string>('—');
  const [isDarkMode, setIsDarkMode] = useState<boolean>(false);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(true);
  const [userEmail, setUserEmail] = useState<string>('gerant@watchmybusiness.fr');
  const [mobileTab, setMobileTab] = useState<'dashboard' | 'reviews' | 'watchy'>('dashboard');

  // Loaded data state
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [leaderboard, setLeaderboard] = useState<BusinessLeaderboardEntry[]>([]);
  const [historicalTrends, setHistoricalTrends] = useState<WeeklyTrendPoint[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const handleSelectMoteur = (m: MoteurAnalyse) => {
    setMoteur(m);
    setMoteurState(m);
  };

  // Apply dark mode class to document
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  // Semaines disponibles selon le moteur (maison / Gemini)
  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const liste = await apiService.getRapports();
        if (ignore) return;
        const options: WeekOption[] = liste.rapports.map((r) => ({
          id: r.semaine_id,
          label: `Semaine ${r.semaine_id}`,
          dates: `Du ${r.debut} au ${r.fin}`,
        }));
        setWeeks(options);
        setHistoricalTrends(
          liste.rapports
            .slice()
            .reverse()
            .map((r) => ({
              semaine_id: r.semaine_id,
              label: r.semaine_id.replace(/^\d{4}-/, ''),
              pct_positifs: r.pct_positifs,
              pct_negatifs: r.pct_negatifs,
              nb_avis: r.nb_avis,
            })),
        );
        if (options.length && (!selectedWeekId || !options.some((w) => w.id === selectedWeekId))) {
          setSelectedWeekId(options[0].id);
        }
        if (liste.rapports[0]) setLastCollectTime(liste.rapports[0].fin);
      } catch (err) {
        console.error('Erreur chargement semaines:', err);
      }
    })();
    return () => {
      ignore = true;
    };
  }, [moteur]);

  // Load report and reviews
  const loadData = useCallback(async () => {
    if (!selectedWeekId) return;
    setIsLoading(true);
    try {
      const rep = await apiService.getRapportDetail(selectedWeekId);
      setReport(rep);
      const avisRes = await apiService.getAvis(selectedWeekId);
      setReviews(avisRes.avis);
      if (selectedBusinessId === 'all') {
        const lb = await apiService.getLeaderboard(selectedCategory, selectedWeekId);
        setLeaderboard(lb);
      }
    } catch (err) {
      console.error('Erreur chargement données:', err);
    } finally {
      setIsLoading(false);
    }
  }, [selectedWeekId, selectedBusinessId, selectedCategory, moteur]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // When category changes, auto-select first business of that category unless 'all'
  const handleSelectCategory = (catId: CategoryId) => {
    setSelectedCategory(catId);
    setActiveThemeFilter(null);
    const catBusinesses = BUSINESSES.filter((b) => b.category === catId);
    if (selectedBusinessId !== 'all') {
      setSelectedBusinessId(catBusinesses[0]?.id || 'all');
    }
  };

  // Handle clicking a citation in Watchy
  const handleCitationClick = (clientId: string) => {
    setHighlightedClientId(clientId);
    setMobileTab('reviews');
    setTimeout(() => {
      const el = document.getElementById(`review-${clientId}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 150);

    // Remove highlight after 4 seconds
    setTimeout(() => {
      setHighlightedClientId((current) => (current === clientId ? null : current));
    }, 4500);
  };

  // Handle click on "Répondre avec Watchy"
  const handleRespondWithWatchy = (review: Review) => {
    setActiveDraftReview(review);
    setIsWatchyOpen(true);
    setMobileTab('watchy');
  };

  const currentBusiness = BUSINESSES.find((b) => b.id === selectedBusinessId);
  const currentCategory = CATEGORIES.find((c) => c.id === selectedCategory);
  const isAllMode = selectedBusinessId === 'all';
  const businessDisplayName = isAllMode
    ? `Tous les établissements (${currentCategory?.label})`
    : currentBusiness?.name || 'Établissement';

  // Compute sparklines for the 4 KPI cards from the 8 historical trend weeks
  const sparklineAvis = historicalTrends.map((t) => t.nb_avis);
  const sparklinePositifs = historicalTrends.map((t) => t.pct_positifs);
  const sparklineNegatifs = historicalTrends.map((t) => t.pct_negatifs);
  const sparklineNeutres = historicalTrends.map((t) =>
    t.pct_positifs !== null && t.pct_negatifs !== null
      ? Math.max(0, 100 - t.pct_positifs - t.pct_negatifs)
      : null
  );

  return (
    <div className="min-h-screen flex flex-col font-sans transition-colors duration-200">
      {/* Real-time Toast Notification */}
      <NotificationToast
        toast={toast}
        onDismiss={() => setToast(null)}
        onViewReview={handleCitationClick}
      />

      {/* Authentication Modal */}
      <AuthModal
        isOpen={!isAuthenticated}
        onLogin={(email) => {
          setUserEmail(email);
          setIsAuthenticated(true);
        }}
      />

      {/* Top Bar */}
      <TopBar
        selectedCategory={selectedCategory}
        onSelectCategory={handleSelectCategory}
        selectedBusinessId={selectedBusinessId}
        onSelectBusiness={(id) => {
          setSelectedBusinessId(id);
          setActiveThemeFilter(null);
        }}
        selectedWeekId={selectedWeekId}
        onSelectWeek={(id) => {
          setSelectedWeekId(id);
          setActiveThemeFilter(null);
        }}
        weeks={weeks}
        reviewCount={report?.nb_avis ?? reviews.length}
        lastCollectTime={lastCollectTime}
        isDarkMode={isDarkMode}
        onToggleDarkMode={() => setIsDarkMode(!isDarkMode)}
        userEmail={userEmail}
        onLogout={() => setIsAuthenticated(false)}
        moteur={moteur}
        onSelectMoteur={handleSelectMoteur}
      />

      {/* Main Workspace Layout */}
      <div className="flex-1 flex max-w-7xl w-full mx-auto px-3 sm:px-6 py-5 gap-6">
        {/* Central Dashboard & Review Stream */}
        <main
          className={`flex-1 min-w-0 space-y-6 pb-20 lg:pb-8 transition-all duration-300 ${
            isWatchyOpen ? 'lg:mr-[390px]' : ''
          }`}
        >
          {/* Mobile Tabs Switcher (< lg) */}
          <div className="flex lg:hidden bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-1 shadow-xs">
            <button
              type="button"
              onClick={() => setMobileTab('dashboard')}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
                mobileTab === 'dashboard'
                  ? 'bg-slate-900 text-white dark:bg-emerald-600'
                  : 'text-slate-600 dark:text-slate-400'
              }`}
            >
              <LayoutDashboard className="w-3.5 h-3.5" />
              <span>Tableau de bord</span>
            </button>
            <button
              type="button"
              onClick={() => setMobileTab('reviews')}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
                mobileTab === 'reviews'
                  ? 'bg-slate-900 text-white dark:bg-emerald-600'
                  : 'text-slate-600 dark:text-slate-400'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span>Avis ({reviews.length})</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setMobileTab('watchy');
                setIsWatchyOpen(true);
              }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
                mobileTab === 'watchy'
                  ? 'bg-slate-900 text-white dark:bg-emerald-600'
                  : 'text-slate-600 dark:text-slate-400'
              }`}
            >
              <Bot className="w-3.5 h-3.5 text-emerald-500" />
              <span>Watchy IA</span>
            </button>
          </div>

          {/* Comparative Mode or Single Business Mode */}
          {isAllMode ? (
            <div className="space-y-6">
              {/* Comparative Leaderboard */}
              <ComparisonTable
                entries={leaderboard}
                weekLabel={selectedWeekId}
                categoryLabel={currentCategory?.label || 'Commerces'}
                onSelectBusiness={(bizId) => setSelectedBusinessId(bizId)}
              />

              {/* Aggregated reviews across the category */}
              <ReviewFeed
                reviews={reviews}
                activeThemeFilter={activeThemeFilter}
                onClearThemeFilter={() => setActiveThemeFilter(null)}
                highlightedClientId={highlightedClientId}
                onRespondWithWatchy={handleRespondWithWatchy}
              />
            </div>
          ) : (
            <>
              {/* Dashboard Tab Content */}
              <div
                className={`space-y-6 ${
                  mobileTab === 'reviews' || mobileTab === 'watchy' ? 'hidden lg:block' : 'block'
                }`}
              >
                {/* 1. Week Header & Business Weather Widget */}
                {report && (
                  <BusinessWeather
                    weekId={report.semaine_id}
                    dates={`Du ${report.debut} au ${report.fin} 2026`}
                    businessName={businessDisplayName}
                    meteo={report.meteo}
                    meteoLibelle={report.meteo_libelle}
                    variationPts={report.variation_pts}
                    tendance={report.tendance}
                    nbAvis={report.nb_avis}
                  />
                )}

                {/* 2. 4 KPI Cards */}
                {report && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {/* KPI 1: Total reviews analyzed */}
                    <KpiCard
                      title="Avis analysés"
                      value={report.nb_avis}
                      subtitle={`Note moyenne ${report.note_moyenne != null ? String(report.note_moyenne).replace('.', ',') : '—'} / 5`}
                      badge={{
                        text: `Confiance du modèle : ${Math.round(
                          report.score_confiance_moyen * 100
                        )}%`,
                        variant: 'info',
                      }}
                      sparklineData={sparklineAvis}
                      color="indigo"
                      icon={MessageSquare}
                    />

                    {/* KPI 2: % Positifs */}
                    <KpiCard
                      title="Avis Positifs"
                      value={`${String(report.pct_positifs).replace('.', ',')}%`}
                      subtitle={`${report.repartition.POSITIVE} avis favorables`}
                      badge={{
                        text:
                          report.variation_pts !== null
                            ? `${report.variation_pts > 0 ? '+' : ''}${String(report.variation_pts).replace('.', ',')} pts vs préc.`
                            : 'Stable',
                        variant: 'positive',
                      }}
                      sparklineData={sparklinePositifs}
                      color="emerald"
                      icon={ThumbsUp}
                    />

                    {/* KPI 3: % Négatifs */}
                    <KpiCard
                      title="Avis Négatifs"
                      value={`${String(report.pct_negatifs).replace('.', ',')}%`}
                      subtitle={`${report.repartition.NEGATIVE} avis défavorables`}
                      badge={{
                        text:
                          report.pct_negatifs > 25
                            ? 'Point d effort élevé'
                            : 'Niveau modéré',
                        variant: 'negative',
                      }}
                      sparklineData={sparklineNegatifs}
                      color="coral"
                      icon={ThumbsDown}
                    />

                    {/* KPI 4: % Neutres & Mitigés */}
                    <KpiCard
                      title="Neutres & mitigés"
                      value={`${String(report.pct_neutres_mitiges).replace('.', ',')}%`}
                      subtitle={`${report.repartition.NEUTRAL + report.repartition.MIXED} avis nuancés`}
                      badge={{
                        text: `${report.repartition.MIXED} mitigés / ${report.repartition.NEUTRAL} neutres`,
                        variant: 'neutral',
                      }}
                      sparklineData={sparklineNeutres}
                      color="amber"
                      icon={HelpCircle}
                    />
                  </div>
                )}

                {/* Rapport du lundi + humeurs + avis à vérifier */}
                {report && (
                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                    <div className="lg:col-span-7">
                      <SyntheseCard synthese={report.synthese} semaineId={report.semaine_id} />
                    </div>
                    <div className="lg:col-span-5">
                      <HumeursPanel
                        humeurs={report.humeurs}
                        nbAVerifier={report.nb_a_verifier}
                        nbAvis={report.nb_avis}
                        onShowToVerify={() => {
                          setOnlyToVerify(true);
                          setMobileTab('reviews');
                          setTimeout(() => {
                            document.getElementById('flux-avis')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                          }, 100);
                        }}
                      />
                    </div>
                  </div>
                )}

                {/* 3. Sentiment Donut & Daily Volume Chart */}
                {report && (
                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                    <div className="lg:col-span-5">
                      <SentimentDonut
                        repartition={report.repartition}
                        totalAvis={report.nb_avis}
                      />
                    </div>
                    <div className="lg:col-span-7">
                      <DailyVolumeChart data={report.volume_par_jour} />
                    </div>
                  </div>
                )}

                {/* 4. Weekly Trend Evolution Chart (with strict gap handling) */}
                <WeeklyTrendChart
                  data={historicalTrends}
                  currentWeekId={selectedWeekId}
                />

                {/* 5. Two Theme Columns: "Ce qui a posé problème" & "Ce qui a bien fonctionné" */}
                {report && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    {/* Problems */}
                    <ThemeColumn
                      type="negative"
                      themes={report.themes_negatifs}
                      activeFilterTheme={activeThemeFilter}
                      onSelectThemeFilter={(theme) => setActiveThemeFilter(theme)}
                    />

                    {/* Successes */}
                    <ThemeColumn
                      type="positive"
                      themes={report.themes_positifs}
                      activeFilterTheme={activeThemeFilter}
                      onSelectThemeFilter={(theme) => setActiveThemeFilter(theme)}
                    />
                  </div>
                )}
              </div>

              {/* Review Feed */}
              <div
                id="flux-avis"
                className={`scroll-mt-24 ${
                  mobileTab === 'dashboard' || mobileTab === 'watchy' ? 'hidden lg:block' : 'block'
                }`}
              >
                <ReviewFeed
                  reviews={reviews}
                  activeThemeFilter={activeThemeFilter}
                  onClearThemeFilter={() => setActiveThemeFilter(null)}
                  highlightedClientId={highlightedClientId}
                  onRespondWithWatchy={handleRespondWithWatchy}
                  onlyToVerify={onlyToVerify}
                  onToggleOnlyToVerify={() => setOnlyToVerify(!onlyToVerify)}
                />
              </div>
            </>
          )}
        </main>

        {/* 3. Right Panel: The "Watchy" Agent */}
        {report && (
          <WatchyAgentPanel
            businessName={businessDisplayName}
            categoryLabel={currentCategory?.label || 'Commerce'}
            currentWeekLabel={selectedWeekId}
            report={report}
            reviews={reviews}
            isOpen={isWatchyOpen}
            onToggleOpen={() => setIsWatchyOpen(!isWatchyOpen)}
            activeDraftReview={activeDraftReview}
            onClearActiveDraftReview={() => setActiveDraftReview(null)}
            onCitationClick={handleCitationClick}
          />
        )}
      </div>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-200/80 dark:border-slate-800 bg-white/60 dark:bg-slate-900/60 backdrop-blur-xs py-4 text-center text-xs text-slate-600 dark:text-slate-400">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-bold text-slate-800 dark:text-slate-200">WatchMyBusiness</span>
            <span>• Satisfaction client, semaine après semaine</span>
          </div>
          <div className="flex items-center gap-4 text-[11px] text-slate-600 dark:text-slate-400">
            <span>
              Analyse : {moteur === 'maison' ? `notre modèle NLP ${MODELE.version}` : 'Gemini 3.5 Flash'}
            </span>
            <span>•</span>
            <span>Collecte : Apify</span>
            <span>•</span>
            <span>Google Cloud</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
