/* Tableau de bord WatchMyBusiness — application statique, sans build.
 * L'API est servie par la même application Cloud Run : chemins relatifs, pas de CORS.
 * Chaque avis est classé par notre modèle NLP (sentiment, humeur, thèmes, confiance).
 */

const $ = (id) => document.getElementById(id);

const etat = {
  etablissement: null,
  nomEtablissement: "",
  rapports: [],
  rapportCourant: null,
  filtreSentiment: "",
  filtreVerifier: false,
  recherche: "",
  avis: [],
  nbAffiches: 20,
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

const HUMEURS = {
  joie: { libelle: "Joie", emoji: "😄", couleur: "var(--positif)" },
  satisfaction: { libelle: "Satisfaction", emoji: "🙂", couleur: "#22c55e" },
  neutre: { libelle: "Neutre", emoji: "😐", couleur: "var(--neutre)" },
  deception: { libelle: "Déception", emoji: "😕", couleur: "var(--mitige)" },
  frustration: { libelle: "Frustration", emoji: "😤", couleur: "#ea580c" },
  colere: { libelle: "Colère", emoji: "😠", couleur: "var(--negatif)" },
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

const nombreFr = (x) => (x == null ? "—" : String(x).replace(".", ","));

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

function couleurCss(variable) {
  return getComputedStyle(document.documentElement).getPropertyValue(variable).trim();
}

/* Markdown minimal de la synthèse : titres ##, listes, gras. Le texte est
 * échappé AVANT la mise en forme : aucune balise n'est interprétée. */
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
/* Rendu du rapport                                                        */
/* ---------------------------------------------------------------------- */

function afficherRapport(rapport) {
  etat.rapportCourant = rapport;

  $("nom-etablissement").textContent = etat.nomEtablissement;
  $("titre-semaine").textContent = `Semaine ${rapport.semaine_id}`;
  $("sous-titre-semaine").textContent =
    `Du ${formaterDate(rapport.periode_debut)} au ${formaterDate(rapport.periode_fin)}`;

  const badge = $("badge-tendance");
  badge.textContent = LIBELLES_TENDANCE[rapport.tendance] || rapport.tendance;
  badge.className = `badge ${rapport.tendance}`;

  const comparaison = rapport.comparaison_semaine_precedente;
  $("comparaison").textContent = comparaison
    ? `${comparaison.delta_pct_positif >= 0 ? "+" : ""}${nombreFr(comparaison.delta_pct_positif)} pts ` +
      `d'avis positifs vs ${comparaison.semaine_id}`
    : "Pas de semaine précédente pour comparer";

  $("kpi-total").textContent = rapport.nb_avis;
  $("kpi-total-detail").textContent = `note moyenne ${nombreFr(rapport.note_moyenne)} / 5`;
  [["positif", rapport.pct_positif, rapport.nb_positif],
   ["negatif", rapport.pct_negatif, rapport.nb_negatif]].forEach(([cle, pct, nb]) => {
    $(`kpi-${cle}`).textContent = `${nombreFr(pct)} %`;
    $(`kpi-${cle}-detail`).textContent = `${nb} avis`;
  });
  const nbMitiges = (rapport.nb_neutre || 0) + (rapport.nb_mixte || 0);
  const pctMitiges = Math.round(((rapport.pct_neutre || 0) + (rapport.pct_mixte || 0)) * 10) / 10;
  $("kpi-neutre").textContent = `${nombreFr(pctMitiges)} %`;
  $("kpi-neutre-detail").textContent = `${nbMitiges} avis`;
  $("kpi-verifier").textContent = rapport.nb_a_verifier ?? "—";

  $("synthese").innerHTML = markdownVersHtml(rapport.synthese);
  $("synthese-source").textContent = rapport.modele ? `analyse : ${rapport.modele}` : "";

  afficherHumeurs(rapport.humeurs || []);
  afficherMatrice(rapport.themes_matrice || []);
  dessinerRepartition(rapport);
  dessinerVolume(rapport);
  dessinerEvolution();
  afficherThemes("themes-negatifs", rapport.top_negatifs, "rouge");
  afficherThemes("themes-positifs", rapport.top_positifs, "verte");
  chargerAvis();
}

function afficherHumeurs(humeurs) {
  const conteneur = $("humeurs");
  if (!humeurs.length) {
    conteneur.innerHTML = "<p class='vide'>Pas d'humeur détectée cette semaine.</p>";
    return;
  }
  const total = humeurs.reduce((s, h) => s + h.nb, 0);
  const ordre = Object.keys(HUMEURS);
  conteneur.innerHTML = [...humeurs]
    .sort((a, b) => ordre.indexOf(a.humeur) - ordre.indexOf(b.humeur))
    .map((h) => {
      const info = HUMEURS[h.humeur] || { libelle: h.humeur, emoji: "•", couleur: "var(--neutre)" };
      const pct = Math.round((100 * h.nb) / total);
      return `
        <div class="humeur" title="${pct} % des avis">
          <span class="humeur-nom"><span class="emoji">${info.emoji}</span>${echapper(info.libelle)}</span>
          <span class="humeur-barre"><span style="width:${pct}%;background:${info.couleur}"></span></span>
          <span class="humeur-nb">${h.nb}</span>
        </div>`;
    }).join("");
}

function afficherMatrice(matrice) {
  const conteneur = $("matrice-themes");
  if (!matrice.length) {
    conteneur.innerHTML = "<p class='vide'>Aucun thème repéré cette semaine.</p>";
    return;
  }
  const lignes = [...matrice].sort((a, b) =>
    (b.positif + b.negatif + b.neutre) - (a.positif + a.negatif + a.neutre));
  const maximum = Math.max(...lignes.map((t) => Math.max(t.negatif + t.neutre / 2, t.positif + t.neutre / 2)), 1);
  const largeur = (n) => `${(100 * n) / maximum}%`;
  conteneur.innerHTML = lignes.map((t) => `
    <div class="matrice-ligne" title="${t.negatif} négatifs · ${t.neutre} neutres · ${t.positif} positifs">
      <span class="matrice-nom">${echapper(t.libelle)}</span>
      <span class="matrice-gauche">
        ${t.negatif ? `<span class="matrice-nb">${t.negatif}</span>` : ""}
        <span class="barre negatif" style="width:${largeur(t.negatif)}"></span>
        ${t.neutre ? `<span class="barre neutre" style="width:${largeur(t.neutre / 2)}"></span>` : ""}
      </span>
      <span class="matrice-droite">
        ${t.neutre ? `<span class="barre neutre" style="width:${largeur(t.neutre / 2)}"></span>` : ""}
        <span class="barre positif" style="width:${largeur(t.positif)}"></span>
        ${t.positif ? `<span class="matrice-nb">${t.positif}</span>` : ""}
      </span>
    </div>`).join("");
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
    const citations = (theme.exemples || []).slice(0, 1)
      .map((e) => `<p class="citation">« ${echapper(e.extrait)} »</p>`).join("");
    const bloc = document.createElement("div");
    bloc.className = "theme";
    bloc.innerHTML = `
      <div class="theme-entete">
        <span class="theme-titre">${echapper(theme.libelle)}</span>
        <span class="theme-compte">${theme.occurrences} avis · ${nombreFr(theme.part)} %</span>
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

function remplacerGraphique(cle, canvasId, configuration) {
  Chart.defaults.color = couleurCss("--texte-doux");
  etat.graphiques[cle]?.destroy();
  etat.graphiques[cle] = new Chart($(canvasId), configuration);
}

function dessinerRepartition(r) {
  remplacerGraphique("repartition", "graphique-repartition", {
    type: "doughnut",
    data: {
      labels: ["Positifs", "Négatifs", "Mitigés", "Neutres"],
      datasets: [{
        data: [r.nb_positif, r.nb_negatif, r.nb_mixte, r.nb_neutre],
        backgroundColor: [couleurCss("--positif"), couleurCss("--negatif"),
                          couleurCss("--mitige"), couleurCss("--neutre")],
        borderColor: couleurCss("--surface"), borderWidth: 2,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: "64%",
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
      datasets: [{ label: "Avis", data: jours.map((j) => j.nb_avis),
                   backgroundColor: couleurCss("--accent"), borderRadius: 6, maxBarThickness: 34 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: couleurCss("--bordure") } },
        x: { grid: { display: false } },
      },
    },
  });
}

function dessinerEvolution() {
  const series = [...etat.rapports].reverse();
  const courante = etat.rapportCourant?.semaine_id;
  const courbe = (label, cle, couleur) => ({
    label, data: series.map((r) => r[cle]), borderColor: couleur, backgroundColor: couleur,
    tension: .35, yAxisID: "y", borderWidth: 2,
    pointRadius: series.map((r) => (r.semaine_id === courante ? 5 : 2)),
  });
  remplacerGraphique("evolution", "graphique-evolution", {
    type: "line",
    data: {
      labels: series.map((r) => r.semaine_id),
      datasets: [
        courbe("% positifs", "pct_positif", couleurCss("--positif")),
        courbe("% négatifs", "pct_negatif", couleurCss("--negatif")),
        { label: "Note moyenne", data: series.map((r) => r.note_moyenne), yAxisID: "y2",
          borderColor: couleurCss("--texte-doux"), borderDash: [4, 4], borderWidth: 1.5,
          pointRadius: 0, tension: .35 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, padding: 14 } } },
      scales: {
        y: { beginAtZero: true, max: 100, grid: { color: couleurCss("--bordure") },
             ticks: { callback: (v) => `${v} %` } },
        y2: { position: "right", min: 1, max: 5, grid: { display: false },
              ticks: { callback: (v) => `${v} ★` } },
        x: { grid: { display: false } },
      },
      onClick: (_, elements) => {
        if (!elements.length) return;
        const semaine = series[elements[0].index].semaine_id;
        $("selecteur-semaine").value = semaine;
        chargerSemaine(semaine);
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
  if (etat.filtreVerifier) parametres.set("a_verifier", "true");

  try {
    const donnees = await appelApi(`/avis?${parametres}`);
    etat.avis = donnees.avis;
    etat.nbAffiches = 20;
    afficherAvis();
  } catch (erreur) {
    conteneur.innerHTML = `<p class='erreur'>Impossible de charger les avis : ${echapper(erreur.message)}</p>`;
  }
}

function afficherAvis() {
  const conteneur = $("liste-avis");
  const terme = etat.recherche.trim().toLowerCase();
  const avis = terme ? etat.avis.filter((a) => (a.texte || "").toLowerCase().includes(terme)) : etat.avis;
  $("compte-avis").textContent = avis.length;
  conteneur.innerHTML = "";
  if (avis.length === 0) {
    conteneur.innerHTML = "<p class='vide'>Aucun avis pour ce filtre.</p>";
    return;
  }
  avis.slice(0, etat.nbAffiches).forEach((a) => conteneur.appendChild(carteAvis(a)));
  if (avis.length > etat.nbAffiches) {
    const plus = document.createElement("div");
    plus.className = "plus";
    plus.innerHTML = `<button type="button">Afficher plus (${avis.length - etat.nbAffiches} restants)</button>`;
    plus.querySelector("button").addEventListener("click", () => {
      etat.nbAffiches += 20;
      afficherAvis();
    });
    conteneur.appendChild(plus);
  }
}

function carteAvis(avis) {
  const themes = (avis.themes || []).map((t) => {
    const theme = typeof t === "string" ? { libelle: t, polarite: "" } : t;
    return `<span class="mot ${echapper(theme.polarite)}">${echapper(theme.libelle)}</span>`;
  }).join("");
  const humeur = HUMEURS[avis.humeur];
  const motHumeur = humeur ? `<span class="mot humeur">${humeur.emoji} ${humeur.libelle}</span>` : "";
  const lien = avis.url_avis
    ? `<a href="${encodeURI(avis.url_avis)}" target="_blank" rel="noopener">voir l'avis</a>` : "";
  const sentiment = avis.sentiment || "";
  const confiance = avis.confiance != null ? Math.round(avis.confiance * 100) : null;

  const ligne = document.createElement("article");
  ligne.className = `avis${avis.a_verifier ? " a-verifier" : ""}`;
  ligne.innerHTML = `
    <div class="avis-meta">
      <strong>${formaterDate(avis.date_avis)}</strong>
      <span class="etoiles" aria-label="${avis.note} étoiles sur 5">${etoiles(avis.note)}</span>
      ${avis.source ? `<span class="source">${echapper(avis.source)}</span>` : ""}
      ${lien}
    </div>
    <div>
      <p class="avis-texte">${echapper(avis.texte)}</p>
      <div class="avis-mots">${motHumeur}${themes}</div>
    </div>
    <div class="avis-droite">
      <span class="etiquette ${echapper(sentiment)}">${echapper(LIBELLES_SENTIMENT[sentiment] || "Non analysé")}</span>
      ${confiance != null ? `
        <div class="confiance" title="Confiance du modèle">
          <span>confiance ${confiance} %</span>
          <span class="confiance-barre"><span style="width:${confiance}%"></span></span>
          ${avis.a_verifier ? "<span class='drapeau'>à vérifier</span>" : ""}
        </div>` : ""}
    </div>`;
  return ligne;
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
    option.textContent = `Semaine ${r.semaine_id} · ${r.nb_avis} avis`;
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
    etat.nomEtablissement = etablissements[0].nom;
    await chargerEtablissement(etablissements[0].etablissement_id);
  } catch (erreur) {
    $("bandeau-vide").textContent = `Erreur de chargement : ${erreur.message}`;
    $("bandeau-vide").classList.remove("masque");
  }
}

function choisirFiltre(bouton) {
  document.querySelectorAll(".filtre").forEach((b) => b.classList.remove("actif"));
  bouton.classList.add("actif");
  etat.filtreVerifier = bouton.dataset.verifier === "1";
  etat.filtreSentiment = etat.filtreVerifier ? "" : bouton.dataset.sentiment;
  chargerAvis();
}

$("selecteur-etablissement").addEventListener("change", (e) => {
  etat.nomEtablissement = e.target.selectedOptions[0]?.textContent || "";
  chargerEtablissement(e.target.value);
});

$("selecteur-semaine").addEventListener("change", (e) => chargerSemaine(e.target.value));

$("filtres-sentiment").addEventListener("click", (evenement) => {
  const bouton = evenement.target.closest(".filtre");
  if (bouton) choisirFiltre(bouton);
});

$("kpi-verifier-bouton").addEventListener("click", () => {
  choisirFiltre(document.querySelector(".filtre.verifier"));
  $("section-avis").scrollIntoView({ behavior: "smooth", block: "start" });
});

$("recherche-avis").addEventListener("input", (e) => {
  etat.recherche = e.target.value;
  etat.nbAffiches = 20;
  afficherAvis();
});

window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (etat.rapportCourant) afficherRapport(etat.rapportCourant);
});

demarrer();
