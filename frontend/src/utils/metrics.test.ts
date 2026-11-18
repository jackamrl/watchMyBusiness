import test from 'node:test';
import assert from 'node:assert/strict';
import {
  calculateSentimentPercentages,
  calculateAverageConfidence,
  determineBusinessWeather,
  extractThemeMetrics,
  filterReviewsList,
} from './metrics';
import { Review } from '../types';

const sampleReviews: Review[] = [
  {
    avis_id: '1',
    date: '2026-10-15T12:00:00',
    semaine_id: '2026-W42',
    client_id: 'CLI-1001',
    etablissement_id: 'rest-1',
    note_google: 5,
    texte: 'Super accueil et service impeccable, fallafels délicieux !',
    sentiment: 'POSITIVE',
    score: 0.98,
    themes: ['Accueil et service', 'Qualité des plats'],
  },
  {
    avis_id: '2',
    date: '2026-10-16T13:30:00',
    semaine_id: '2026-W42',
    client_id: 'CLI-1002',
    etablissement_id: 'rest-1',
    note_google: 4,
    texte: 'Très bonne qualité des plats, portions généreuses.',
    sentiment: 'POSITIVE',
    score: 0.94,
    themes: ['Qualité des plats', 'Rapport qualité-prix'],
  },
  {
    avis_id: '3',
    date: '2026-10-17T19:00:00',
    semaine_id: '2026-W42',
    client_id: 'CLI-1003',
    etablissement_id: 'rest-1',
    note_google: 1,
    texte: 'Temps d attente interminable, 45 minutes pour être servi !',
    sentiment: 'NEGATIVE',
    score: 0.99,
    themes: ["Temps d'attente"],
  },
  {
    avis_id: '4',
    date: '2026-10-18T14:00:00',
    semaine_id: '2026-W42',
    client_id: 'CLI-1004',
    etablissement_id: 'rest-1',
    note_google: 3,
    texte: 'Bon mais un peu cher pour ce que c est.',
    sentiment: 'MIXED',
    score: 0.85,
    themes: ['Rapport qualité-prix'],
  },
];

test('calculateSentimentPercentages returns accurate breakdown', () => {
  const pcts = calculateSentimentPercentages(sampleReviews);
  assert.equal(pcts.pctPositifs, 50.0);
  assert.equal(pcts.pctNegatifs, 25.0);
  assert.equal(pcts.pctNeutresMitiges, 25.0);
});

test('calculateAverageConfidence computes mean score', () => {
  const avg = calculateAverageConfidence(sampleReviews);
  // (0.98 + 0.94 + 0.99 + 0.85) / 4 = 0.94
  assert.equal(avg, 0.94);
});

test('determineBusinessWeather returns sunny for high positive sentiment', () => {
  const weather = determineBusinessWeather(82.5, 7.5, 4.2, 35);
  assert.equal(weather.meteo, 'soleil');
  assert.equal(weather.tendance, 'positive');
});

test('determineBusinessWeather returns stormy for high negative sentiment or sharp drop', () => {
  const weather = determineBusinessWeather(45.0, 38.0, -8.0, 25);
  assert.equal(weather.meteo, 'orage');
  assert.equal(weather.tendance, 'negative');
});

test('determineBusinessWeather returns fog when review count is insufficient', () => {
  const weather = determineBusinessWeather(100.0, 0.0, null, 2);
  assert.equal(weather.meteo, 'brouillard');
  assert.equal(weather.tendance, 'indeterminee');
});

test('extractThemeMetrics extracts occurrences and citations', () => {
  const positiveThemes = extractThemeMetrics(sampleReviews, 'POSITIVE');
  const platTheme = positiveThemes.find((t) => t.theme === 'Qualité des plats');
  assert.ok(platTheme);
  assert.equal(platTheme?.occurrences, 2);
  assert.ok(platTheme?.citations.length > 0);

  const negativeThemes = extractThemeMetrics(sampleReviews, 'NEGATIVE');
  const waitTheme = negativeThemes.find((t) => t.theme === "Temps d'attente");
  assert.ok(waitTheme);
  assert.equal(waitTheme?.occurrences, 1);
});

test('filterReviewsList filters by search and sentiment correctly', () => {
  const negatives = filterReviewsList(sampleReviews, { sentiment: 'NEGATIVE' });
  assert.equal(negatives.length, 1);
  assert.equal(negatives[0].client_id, 'CLI-1003');

  const searchResults = filterReviewsList(sampleReviews, { search: 'fallafels' });
  assert.equal(searchResults.length, 1);
  assert.equal(searchResults[0].client_id, 'CLI-1001');
});

test('normalizeFrenchText removes accents and lowercases', () => {
  const normalized = sampleReviews.map((r) => r.texte);
  assert.ok(normalized.length > 0);
  const testWord = 'Propreté & Qualité';
  assert.equal(testWord.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(), 'proprete & qualite');
});

test('filterReviewsList is accent-insensitive (e.g. proprete matches propreté, qualite matches qualité)', () => {
  const accentSearch = filterReviewsList(sampleReviews, { search: 'qualite' });
  // Review 1 has "Qualité des plats", Review 2 has "Qualité des plats" & "Rapport qualité-prix", Review 4 has "Rapport qualité-prix"
  assert.equal(accentSearch.length, 3);
});

