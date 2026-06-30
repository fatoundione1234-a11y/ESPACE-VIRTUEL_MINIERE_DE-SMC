# ⛏️ ESPACE VIRTUELLE MINIÈRE DE SMC — Phase 1

Dashboard d'exploration minière (Streamlit) — Module **Sections géologiques & Logs automatisés**.

## 📦 Contenu
- `app.py` — application Streamlit principale
- `parsers.py` — moteur de lecture/fusion de vos fichiers Excel de log + audit + rapport
- `pdf_report.py` — génération du rapport PDF
- `db.py` — persistance locale SQLite (multi-prospects)
- `requirements.txt` — dépendances Python
- `smc_dashboard.db` — base de données locale (créée automatiquement au premier lancement)

## 🚀 Installation et lancement

```bash
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre dans votre navigateur (http://localhost:8501).

## 🗂️ Comment l'utiliser

1. **Onglet "📥 Import des données"** : chargez vos fichiers Excel (Log RC, Log AC, Log DD,
   Log Géochimie Sols/Auger, Log Structural). Vous pouvez aussi cliquer sur
   **"🧪 Charger des données de démonstration"** pour voir le dashboard fonctionner immédiatement
   avec des données fictives, le temps que vos logs réels soient complétés.
2. **Onglet "📋 Logs automatisés"** : sélectionnez un type de sondage puis un trou — vous obtenez
   le log lithologique interactif (colonne stratigraphique colorée), les marqueurs de
   minéralisation/altération, le tableau complet, et un texte d'interprétation automatique.
3. **Onglet "📐 Sections géologiques"** : sélectionnez les trous à inclure, la section se construit
   automatiquement (légende, nord, échelle, ligne topographique, n° de trous, profondeurs,
   limites latérite/saprolite/saprock/socle, intervalles minéralisés en surbrillance).
4. **Onglet "📊 Synthèse / Collars"** : plan de position des collars, statistiques globales.

## ⚠️ Constat sur vos fichiers actuels

Vos 4 fichiers (RC, AC, DD, Auger) sont des **gabarits** très bien structurés mais quasiment vides
(seulement 1-2 lignes d'exemple, sans coordonnées ni intervalles From/To remplis). Le fichier
Structural ne contient que les en-têtes, aucune donnée.
➡️ Dès que vos données de terrain réelles seront saisies dans ces gabarits, le dashboard les
affichera automatiquement (aucune modification de code nécessaire) — la structure des colonnes est
déjà reconnue par `parsers.py`.

**Un point important** : aucun de vos fichiers RC/AC/DD n'a de colonne de teneur en or (Au). Seul
le fichier Géochimie Sols contient `Labo_Au_ppb`. Pour afficher les teneurs Au sur les sections
RC/AC/DD (comme demandé), il faudra un fichier d'analyses (assays) avec colonnes
`Sondage, From, To, Au_ppm` — dites-moi si vous l'avez, je l'intégrerai en Phase 2.

## 🛣️ État d'avancement

- ✅ Phase 1 : Sections géologiques & Logs automatisés
- ✅ Phase 2 : Cartes (lithologie/structurale/anomalie), graphiques structuraux
- ✅ Phase 3 : Modèle 3D, planification infill/extension, simulation déviation, Auger, teneurs
- ✅ Phase 4 : SGI/GSI vs minéralisation, tableau structural, géophysique
- ✅ Phase 5 : Ressources/JORC simplifié, Budget & Coûts, Gestion des échantillons
- ✅ Phase 6 : Métallurgie, HSE, SOP, Admin, Audit automatique des données, multi-prospects
- ✅ Phase 7 : Rapport géologique automatisé (PDF/Markdown), Documents, Commentaires & Réponses
- ✅ Phase 8 : Sections par orientation de forage (inclinés / subverticaux / slow drilling)
- ✅ Phase 9 : Base de données persistante (SQLite)

Le dashboard couvre maintenant **24 modules**, avec sauvegarde automatique locale.

## 🆕 Phase 8 — Sections par orientation de forage

- **📐 Sections par orientation de forage** : classe automatiquement les trous par pendage moyen
  (Subvertical ≥75°, Incliné 30-75°, Slow drilling/Subhorizontal <30°) et trace la **trajectoire
  réelle désurveyée** (pas juste une colonne verticale) projetée sur la section — utile pour les
  forages à fort déport ou les campagnes de corrélation lente en subhorizontal.

## 🆕 Phase 9 — Persistance des données (SQLite)

- Toutes les données de chaque prospect (logs, planification, budget, échantillons, métallurgie,
  HSE, admin, documents, commentaires) sont désormais **sauvegardées automatiquement** dans un
  fichier local `smc_dashboard.db` (SQLite), créé à côté de `app.py`.
- Sauvegarde déclenchée automatiquement à chaque interaction, + bouton **"💾 Sauvegarder maintenant"**
  dans la barre latérale, + horodatage de la dernière sauvegarde affiché.
- En relançant `streamlit run app.py` plus tard (même machine, même dossier), **vos prospects et
  données sont retrouvés tels quels** — fini la perte de données à la fermeture de l'app.
- Vous pouvez sauvegarder/transporter ce fichier `smc_dashboard.db` comme n'importe quel fichier
  (copie de sauvegarde, transfert vers un autre poste, etc.).

⚠️ **Limite à connaître** : si vous déployez ce dashboard sur un hébergement **éphémère** (par
exemple Streamlit Community Cloud sans volume persistant configuré), le système de fichiers est
réinitialisé à chaque redéploiement et la base sera vidée. Pour une persistance garantie en
production multi-utilisateurs, il faudrait soit (a) monter un volume disque persistant pour ce
fichier .db, soit (b) migrer vers un vrai serveur de base de données externe (PostgreSQL, etc.) —
dites-moi si votre infrastructure d'hébergement final nécessite cette évolution.



## 🆕 Phase 7 — Rapport, Documents, Commentaires

- **📄 Rapport géologique** : génère automatiquement un rapport argumenté (résumé exécutif, contexte
  géologique, altération/minéralisation, structures, géochimie, recommandations) à partir de toutes
  les données chargées. Export **PDF** et **Markdown**.
- **🗄️ Documents** : centralise les rapports PDF générés + tout document image/PDF importé manuellement.
- **💬 Commentaires & Réponses** : fil de discussion par prospect entre géologues (commentaire + réponses).

## ⚠️ Limites techniques à connaître

- **Pas de persistance** : tout vit en mémoire de la session Streamlit (y compris les documents et
  commentaires) ; fermer l'app efface tout. Une vraie base de données externe serait nécessaire pour
  un usage en production multi-utilisateurs durable.
- **Pas de visio/notes vocales temps réel** : non réalisable nativement en Streamlit, nécessiterait un
  service tiers (Zoom/Teams) lié en externe.
- Le PDF généré est un document texte structuré simple (pas de mise en page graphique avancée avec
  cartes intégrées) — pour un rapport illustré complet, exporter les graphiques individuellement
  (bouton de téléchargement intégré à chaque graphique Plotly) et les assembler dans Word/PowerPoint.





- **🧊 Modèle 3D** : trajectoires 3D colorées par lithologie (azimut/pendage issus du Structural si
  disponible, sinon trou vertical par défaut).
- **🛠️ Planification & Extension** : tableau éditable de programme de forage (infill/extension),
  carte par statut (🟦 Foré / 🟩 En cours / 🟥 Stoppé / ⬜ Planifié), calcul de coût automatique.
- **🎯 Simulation déviation** : comparaison trajectoire planifiée vs trajectoire simulée avec dérive
  d'azimut et aplatissement de pendage paramétrables — modèle simplifié, pas un calcul géodésique
  certifié (minimum curvature). À remplacer par les données réelles de déviomètre dès disponibles.
- **🌱 Auger & Géochimie** : table, carte d'anomalie Au (seuil 75e percentile), upload pXRF.
- **💰 Estimation des teneurs** : moyenne pondérée par longueur (Auger directement, RC/AC/DD via
  upload d'un fichier d'assays séparé puisque vos gabarits actuels n'ont pas de colonne Au).

⚠️ La simulation de déviation et le modèle 3D sont des **approximations pédagogiques/opérationnelles**
(formules de désurvey simplifiées), pas des calculs géodésiques certifiés type minimum-curvature —
suffisant pour visualiser et planifier, mais à recouper avec les leviers de déviomètre réels en forage.


