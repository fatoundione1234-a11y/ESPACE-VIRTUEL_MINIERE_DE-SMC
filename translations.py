"""
Traductions FR/EN pour l'interface générale du dashboard (navigation, sidebar, en-têtes).

⚠️ Portée assumée : ce module traduit la structure de l'interface (menu, boutons, libellés
de la barre latérale) — PAS le contenu détaillé de chaque page (tableaux de données,
interprétations automatiques générées en français, noms de colonnes des gabarits Excel).
Une traduction complète de tout le contenu dynamique serait un chantier bien plus lourd
(des dizaines de f-strings d'interprétation à dupliquer) ; ce module couvre ce qui est
réaliste et utile immédiatement : se repérer dans l'app dans les deux langues.
"""

NAV_TRANSLATIONS = {
    "📥 Import des données": {"EN": "📥 Data Import"},
    "📋 Logs automatisés": {"EN": "📋 Automated Logs"},
    "📐 Sections géologiques": {"EN": "📐 Geological Sections"},
    "🗺️ Cartes (lithologie / structurale / anomalie)": {"EN": "🗺️ Maps (lithology / structural / anomaly)"},
    "🧭 Graphiques structuraux": {"EN": "🧭 Structural Charts"},
    "🧊 Modèle 3D": {"EN": "🧊 3D Model"},
    "🛠️ Planification & Extension": {"EN": "🛠️ Planning & Extension"},
    "🎯 Simulation déviation": {"EN": "🎯 Deviation Simulation"},
    "🌱 Auger & Géochimie": {"EN": "🌱 Auger & Geochemistry"},
    "💰 Estimation des teneurs": {"EN": "💰 Grade Estimation"},
    "🪨 SGI & Structures": {"EN": "🪨 GSI & Structures"},
    "📡 Géophysique": {"EN": "📡 Geophysics"},
    "📦 Ressources & Réserves (JORC simplifié)": {"EN": "📦 Resources & Reserves (simplified JORC)"},
    "💵 Budget & Coûts": {"EN": "💵 Budget & Costs"},
    "🔗 Gestion des échantillons": {"EN": "🔗 Sample Management"},
    "⚗️ Métallurgie": {"EN": "⚗️ Metallurgy"},
    "🦺 Environnement & HSE": {"EN": "🦺 Environment & HSE"},
    "📜 SOP": {"EN": "📜 SOP"},
    "🛡️ Admin": {"EN": "🛡️ Admin"},
    "🤖 Audit automatique des données": {"EN": "🤖 Automated Data Audit"},
    "📄 Rapport géologique": {"EN": "📄 Geological Report"},
    "🗄️ Documents": {"EN": "🗄️ Documents"},
    "💬 Commentaires & Réponses": {"EN": "💬 Comments & Replies"},
    "📐 Sections par orientation de forage": {"EN": "📐 Sections by Drill Orientation"},
    "🗃️ Base de données centrale": {"EN": "🗃️ Central Database"},
    "📹 Réunion live": {"EN": "📹 Live Meeting"},
    "🛰️ Survey (déviomètre)": {"EN": "🛰️ Survey (downhole)"},
    "🔔 Notifications": {"EN": "🔔 Notifications"},
    "📧 Envoi Email": {"EN": "📧 Send Email"},
    "📊 Synthèse / Collars": {"EN": "📊 Summary / Collars"},
}

UI_TRANSLATIONS = {
    "Navigation": {"EN": "Navigation"},
    "🌍 Prospect actif": {"EN": "🌍 Active Prospect"},
    "Sélectionner un prospect": {"EN": "Select a prospect"},
    "➕ Créer / supprimer un prospect": {"EN": "➕ Create / delete a prospect"},
    "Nom du nouveau prospect": {"EN": "New prospect name"},
    "Créer ce prospect": {"EN": "Create this prospect"},
    "🗑️ Supprimer le prospect actif": {"EN": "🗑️ Delete active prospect"},
    "💾 Sauvegarder maintenant": {"EN": "💾 Save now"},
    "Nom du permis": {"EN": "Permit name"},
    "🌐 Langue / Language": {"EN": "🌐 Langue / Language"},
    "Aucune alerte active": {"EN": "No active alerts"},
    "voir 🔔 Notifications": {"EN": "see 🔔 Notifications"},
}

DASHBOARD_TITLE = {"FR": "ESPACE VIRTUELLE MINIÈRE DE SMC", "EN": "SMC VIRTUAL MINING SPACE"}
DASHBOARD_SUBTITLE = {
    "FR": "Dashboard d'exploration minière — 30 modules intégrés",
    "EN": "Mining exploration dashboard — 30 integrated modules",
}


def t_nav(label, lang):
    if lang == "FR":
        return label
    return NAV_TRANSLATIONS.get(label, {}).get(lang, label)


def t_ui(label, lang):
    if lang == "FR":
        return label
    return UI_TRANSLATIONS.get(label, {}).get(lang, label)
