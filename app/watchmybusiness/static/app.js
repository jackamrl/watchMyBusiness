/* Tableau de bord WatchMyBusiness (GCP) — application statique, sans build.
 * L'API est servie par la même application Cloud Run : chemins relatifs, pas de CORS.
 */

const $ = (id) => document.getElementById(id);

const etat = {
  etablissement: null,
  rapports: [],
  rapportCourant: null,
  filtreSentiment: "",
  graphiques: {},
};

const LIBELLES_TENDANCE = {
  positive: "Tendance positive",
  negative: "Tendance négative",
  mitigee: "Tendance mitigée",
  aucune: "Aucun avis commenté",
};

const LIBELLES_SENTIMENT = {
  POSITIF: "Positif", NEGATIF: "Négatif", NEUTRE: "Neutre", MIXTE: "Mitigé",
};

/* ---------------------------------------------------------------------- */
/* Utilitaires                                                             */
/* ---------------------------------------------------------------------- */

async function appelApi(chemin) {
  const reponse = await fetch(`/api${chemin}`);
  if (!reponse.ok) throw new Error(`API ${reponse.status}`);
  return reponse.json();
}

function echapper(valeur) {
  const noeud = document.createElement("div");
  noeud.textContent = valeur ?? "";
  return noeud.innerHTML;
}

function formaterDate(iso) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("fr-FR", { day: "numeric", month: "long" });
}

function jourCourt(iso) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric" });
}

function etoiles(note) {
  if (note == null) return "";
  return "★".repeat(note) + "☆".repeat(5 - note);
}

/* Markdown minimal de la synthèse : titres ##, listes, gras. Le texte est
 * échappé AVANT la mise en forme : aucune balise venant du modèle n'est interprétée. */
function markdownVersHtml(texte) {
  const lignes = echapper(texte || "").split("\n");
  const sortie = [];
  let liste = null;

  const fermerListe = () => { if (liste) { sortie.push(`</${liste}>`); liste = null; } };
  const gras = (s) => s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  for (const brute of lignes) {
    const ligne = brute.trim();
    let m;
    if (!ligne) { fermerListe(); continue; }
    if ((m = ligne.match(/^#{1,3}\s+(.*)/))) { fermerListe(); sortie.push(`<h3>${gras(m[1])}</h3>`); continue; }
    if ((m = ligne.match(/^[-*]\s+(.*)/))) {
      if (liste !== "ul") { fermerListe(); sortie.push("<ul>"); liste = "ul"; }
      sortie.push(`<li>${gras(m[1])}</li>`); continue;
    }
    if ((m = ligne.match(/^\d+\.\s+(.*)/))) {
      if (liste !== "ol") { fermerListe(); sortie.push("<ol>"); liste = "ol"; }
      sortie.push(`<li>${gras(m[1])}</li>`); continue;
    }
    fermerListe();
    sortie.push(`<p>${gras(ligne)}</p>`);
  }
  fermerListe();
  return sortie.join("");
}

/* ---------------------------------------------------------------------- */
/* Rendu                                                                   */
/* ---------------------------------------------------------------------- */

function afficherRapport(rapport) {
  etat.rapportCourant = rapport;

  $("titre-semaine").textContent = `Semaine ${rapport.semaine_id}`;
  $("sous-titre-semaine").textContent =
    `Du ${formaterDate(rapport.periode_debut)} au ${formaterDate(rapport.periode_fin)}`;

  const badge = $("badge-tendance");
  badge.textContent = LIBELLES_TENDANCE[rapport.tendance] || rapport.tendance;
  badge.className = `badge ${rapport.tendance === "aucune" ? "indeterminee" : rapport.tendance}`;

  const comparaison = rapport.comparaison_semaine_precedente;
  $("comparaison").textContent = comparaison
    ? `${comparaison.delta_pct_positif >= 0 ? "+" : ""}${comparaison.delta_pct_positif} pts ` +
      `d'avis positifs vs ${comparaison.semaine_id}`
    : "Pas de rapport précédent pour comparer";

  $("kpi-total").textContent = rapport.nb_avis;
  $("kpi-total-detail").textContent =
    `${rapport.nb_analyses} commentés · note moyenne ${rapport.note_moyenne ?? "—"} / 5`;

  [["positif", rapport.pct_positif, rapport.nb_positif],
   ["negatif", rapport.pct_negatif, rapport.nb_negatif]].forEach(([cle, pct, nb]) => {
    $(`kpi-${cle}`).textContent = `${pct} %`;
    $(`kpi-${cle}-detail`).textContent = `${nb} avis`;
  });
  const nbNeutres = (rapport.nb_neutre || 0) + (rapport.nb_mixte || 0);
  const pctNeutres = Math.round(((rapport.pct_neutre || 0) + (rapport.pct_mixte || 0)) * 10) / 10;
  $("kpi-neutre").textContent = `${pctNeutres} %`;
  $("kpi-neutre-detail").textContent = `${nbNeutres} avis`;

  $("synthese").innerHTML = markdownVersHtml(rapport.synthese);
  $("synthese-source").textContent = `Rédigée par ${rapport.modele || "Gemini"}`;

  dessinerRepartition(rapport);
  dessinerVolume(rapport);
  dessinerEvolution();
  afficherThemes("themes-negatifs", rapport.top_negatifs, "rouge");
  afficherThemes("themes-positifs", rapport.top_positifs, "verte");
  chargerAvis();
}

function afficherThemes(idConteneur, themes, couleur) {
  const conteneur = $(idConteneur);
  conteneur.innerHTML = "";
  if (!themes || themes.length === 0) {
    conteneur.innerHTML = "<p class='vide'>Aucun thème récurrent identifié sur cette période.</p>";
    return;
  }
  const maximum = Math.max(...themes.map((t) => t.occurrences));
  themes.forEach((theme) => {
    const citations = (theme.exemples || [])
      .map((e) => `<p class="citation">« ${echapper(e.extrait)} »</p>`).join("");
    const bloc = document.createElement("div");
    bloc.className = "theme";
    bloc.innerHTML = `
      <div class="theme-entete">
        <span class="theme-titre">${echapper(theme.libelle)}</span>
        <span class="theme-compte">${theme.occurrences} avis · ${theme.part} %</span>
      </div>
      <div class="jauge ${couleur}">
        <span style="width:${Math.round((theme.occurrences / maximum) * 100)}%"></span>
      </div>
      ${citations}`;
    conteneur.appendChild(bloc);
  });
}

/* ---------------------------------------------------------------------- */
/* Graphiques                                                              */
/* ---------------------------------------------------------------------- */

Chart.defaults.font.family = "Inter, sans-serif";
Chart.defaults.color = "#6b7280";

function remplacerGraphique(cle, canvasId, configuration) {
  etat.graphiques[cle]?.destroy();
  etat.graphiques[cle] = new Chart($(canvasId), configuration);
}

function dessinerRepartition(r) {
  remplacerGraphique("repartition", "graphique-repartition", {
    type: "doughnut",
    data: {
      labels: ["Positifs", "Négatifs", "Neutres", "Mitigés"],
      datasets: [{
        data: [r.nb_positif, r.nb_negatif, r.nb_neutre, r.nb_mixte],
        backgroundColor: ["#15a34a", "#dc2626", "#94a3b8", "#f59e0b"],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: "62%",
      plugins: { legend: { position: "right", labels: { boxWidth: 10, padding: 14 } } },
    },
  });
}

function dessinerVolume(r) {
  const jours = r.volume_par_jour || [];
  remplacerGraphique("volume", "graphique-volume", {
    type: "bar",
    data: {
      labels: jours.map((j) => jourCourt(j.date)),
      datasets: [{ data: jours.map((j) => j.nb_avis), backgroundColor: "#111827",
                   borderRadius: 5, maxBarThickness: 34 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#f1f2f4" } },
        x: { grid: { display: false } },
      },
    },
  });
}

function dessinerEvolution() {
  const series = [...etat.rapports].reverse();
  const courbe = (label, cle, couleur, fond) => ({
    label, data: series.map((r) => r[cle]), borderColor: couleur,
    backgroundColor: fond, fill: true, tension: .35,
  });
  remplacerGraphique("evolution", "graphique-evolution", {
    type: "line",
    data: {
      labels: series.map((r) => r.semaine_id),
      datasets: [
        courbe("% positifs", "pct_positif", "#15a34a", "rgba(21,163,74,.08)"),
        courbe("% négatifs", "pct_negatif", "#dc2626", "rgba(220,38,38,.06)"),
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, padding: 14 } } },
      scales: {
        y: { beginAtZero: true, max: 100, grid: { color: "#f1f2f4" } },
        x: { grid: { display: false } },
      },
    },
  });
}

/* ---------------------------------------------------------------------- */
/* Avis unitaires                                                          */
/* ---------------------------------------------------------------------- */

async function chargerAvis() {
  const r = etat.rapportCourant;
  const conteneur = $("liste-avis");
  conteneur.innerHTML = "<p class='vide'>Chargement…</p>";

  const parametres = new URLSearchParams({
    etablissement: etat.etablissement, debut: r.periode_debut, fin: r.periode_fin,
  });
  if (etat.filtreSentiment) parametres.set("sentiment", etat.filtreSentiment);

  try {
    const donnees = await appelApi(`/avis?${parametres}`);
    conteneur.innerHTML = "";
    if (donnees.nb === 0) {
      conteneur.innerHTML = "<p class='vide'>Aucun avis pour ce filtre.</p>";
      return;
    }
    donnees.avis.forEach((avis) => {
      const themes = (avis.themes || []).map((t) => `<span class="mot">${echapper(t)}</span>`).join("");
      const lien = avis.url_avis
        ? `<a href="${encodeURI(avis.url_avis)}" target="_blank" rel="noopener">voir sur Maps</a>` : "";
      const sentiment = avis.sentiment || "";
      const ligne = document.createElement("article");
      ligne.className = "avis";
      ligne.innerHTML = `
        <div class="avis-meta">
          <strong>${formaterDate(avis.date_avis)}</strong>
          <span class="etoiles">${etoiles(avis.note)}</span><br>${lien}
        </div>
        <div>
          <p class="avis-texte">${echapper(avis.texte)}</p>
          ${avis.resume ? `<p class="avis-resume">${echapper(avis.resume)}</p>` : ""}
          <div class="avis-mots">${themes}</div>
        </div>
        <span class="etiquette ${echapper(sentiment)}">
          ${echapper(LIBELLES_SENTIMENT[sentiment] || "Non analysé")}
        </span>`;
      conteneur.appendChild(ligne);
    });
  } catch (erreur) {
    conteneur.innerHTML = `<p class='erreur'>Impossible de charger les avis : ${echapper(erreur.message)}</p>`;
  }
}

/* ---------------------------------------------------------------------- */
/* Orchestration                                                           */
/* ---------------------------------------------------------------------- */

async function chargerSemaine(semaineId) {
  const rapport = await appelApi(
    `/rapports/${encodeURIComponent(semaineId)}?etablissement=${encodeURIComponent(etat.etablissement)}`,
  );
  afficherRapport(rapport);
}

async function chargerEtablissement(etablissementId) {
  etat.etablissement = etablissementId;
  const donnees = await appelApi(`/rapports?etablissement=${encodeURIComponent(etablissementId)}&limite=12`);
  etat.rapports = donnees.rapports || [];

  const selecteur = $("selecteur-semaine");
  selecteur.innerHTML = "";
  if (etat.rapports.length === 0) {
    $("bandeau-vide").classList.remove("masque");
    return;
  }
  $("bandeau-vide").classList.add("masque");
  etat.rapports.forEach((r) => {
    const option = document.createElement("option");
    option.value = r.semaine_id;
    option.textContent = `Semaine ${r.semaine_id} (${r.nb_avis} avis)`;
    selecteur.appendChild(option);
  });
  await chargerSemaine(etat.rapports[0].semaine_id);
}

async function demarrer() {
  try {
    const { etablissements } = await appelApi("/etablissements");
    const selecteur = $("selecteur-etablissement");
    etablissements.forEach((e) => {
      const option = document.createElement("option");
      option.value = e.etablissement_id;
      option.textContent = e.nom;
      selecteur.appendChild(option);
    });
    if (etablissements.length <= 1) selecteur.classList.add("masque");
    if (etablissements.length === 0) {
      $("bandeau-vide").classList.remove("masque");
      return;
    }
    $("sous-marque").textContent = `${etablissements[0].nom} · rapport hebdomadaire`;
    await chargerEtablissement(etablissements[0].etablissement_id);
  } catch (erreur) {
    $("bandeau-vide").textContent = `Erreur de chargement : ${erreur.message}`;
    $("bandeau-vide").classList.remove("masque");
  }
}

$("selecteur-etablissement").addEventListener("change", (e) => {
  const nom = e.target.selectedOptions[0]?.textContent || "";
  $("sous-marque").textContent = `${nom} · rapport hebdomadaire`;
  chargerEtablissement(e.target.value);
});

$("selecteur-semaine").addEventListener("change", (e) => chargerSemaine(e.target.value));

$("filtres-sentiment").addEventListener("click", (evenement) => {
  const bouton = evenement.target.closest(".filtre");
  if (!bouton) return;
  document.querySelectorAll(".filtre").forEach((b) => b.classList.remove("actif"));
  bouton.classList.add("actif");
  etat.filtreSentiment = bouton.dataset.sentiment;
  chargerAvis();
});

demarrer();
