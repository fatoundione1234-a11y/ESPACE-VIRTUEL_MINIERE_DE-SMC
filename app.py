import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io

from parsers import (
    parse_geologie_workbook, parse_auger_workbook, parse_structural_workbook,
    collar_table, build_litho_color_map, LITHO_PALETTE, WEATHERING_COLORS, generate_demo_data,
    hole_trajectory, length_weighted_grade, audit_dataframe, auto_fix_dataframe,
    generate_geological_report, report_to_markdown,
)
from pdf_report import build_pdf_report
import db

st.set_page_config(page_title="ESPACE VIRTUELLE MINIÈRE DE SMC", layout="wide", page_icon="⛏️")
db.init_db()


def safe_concat(keys):
    """Concatène les DataFrames non vides de st.session_state.data pour les clés données.
    Retourne un DataFrame vide (sans erreur) si aucune donnée n'est disponible — évite le
    ValueError de pandas ('No objects to concatenate') quand rien n'est encore chargé."""
    dfs = [st.session_state.data[k] for k in keys if not st.session_state.data[k].empty]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def _fresh_project_state():
    return {
        "data": {"RC": pd.DataFrame(), "AC": pd.DataFrame(), "DD": pd.DataFrame(),
                 "AUGER": pd.DataFrame(), "STRUCT": pd.DataFrame()},
        "litho_colors": {},
        "planning": pd.DataFrame(columns=[
            "Trou_ID", "Type", "Ligne", "Easting", "Northing", "Elevation",
            "Azimut", "Pendage", "Profondeur_prevue_m", "Statut", "Cout_unitaire_par_m", "Commentaire",
        ]),
        "budget": pd.DataFrame([
            {"Categorie": "Forage RC", "Description": "Coût mètre RC", "Quantite": 0, "Unite": "m", "Cout_unitaire": 0, "Devise": "USD"},
            {"Categorie": "Forage AC", "Description": "Coût mètre Aircore", "Quantite": 0, "Unite": "m", "Cout_unitaire": 0, "Devise": "USD"},
            {"Categorie": "Forage DD", "Description": "Coût mètre Diamond Drilling", "Quantite": 0, "Unite": "m", "Cout_unitaire": 0, "Devise": "USD"},
            {"Categorie": "Analyses labo", "Description": "Analyses Au (fire assay)", "Quantite": 0, "Unite": "échant.", "Cout_unitaire": 0, "Devise": "USD"},
            {"Categorie": "Logistique", "Description": "Transport / camp / carburant", "Quantite": 0, "Unite": "forfait", "Cout_unitaire": 0, "Devise": "USD"},
            {"Categorie": "Main d'œuvre", "Description": "Géologues / techniciens / ouvriers", "Quantite": 0, "Unite": "homme-mois", "Cout_unitaire": 0, "Devise": "USD"},
        ]),
        "samples": pd.DataFrame(columns=[
            "Echantillon_ID", "Sondage", "From", "To", "Type", "Date_prelevement", "Preleve_par",
            "Date_envoi_labo", "Laboratoire", "Date_reception_resultats", "Statut", "QAQC", "Commentaire",
        ]),
        "metallurgie": pd.DataFrame(columns=[
            "Test_ID", "Sondage", "Type_essai", "Tete_g_t", "Recuperation_pct", "Residu_g_t",
            "Reactif", "Consommation_kg_t", "Granulometrie_P80_um", "Commentaire",
        ]),
        "hse": pd.DataFrame(columns=[
            "Date", "Type", "Description", "Lieu", "Gravite", "Statut", "Responsable", "Actions_correctives",
        ]),
        "admin": pd.DataFrame(columns=[
            "Categorie", "Element", "Reference", "Date_emission", "Date_expiration", "Statut", "Commentaire",
        ]),
        "documents": [],
        "comments": [],
        "permis": "",
    }


LIVE_KEYS = ["data", "litho_colors", "planning", "budget", "samples", "metallurgie", "hse", "admin",
             "documents", "comments", "permis"]


def _save_active_to_db():
    state = {k: st.session_state[k] for k in LIVE_KEYS}
    db.save_project_state(st.session_state.active_project, state)


def _load_project(name):
    state = db.load_project_state(name)
    if state is None:
        state = _fresh_project_state()
        db.save_project_state(name, state)
    for k in LIVE_KEYS:
        st.session_state[k] = state.get(k, _fresh_project_state()[k])


if "active_project" not in st.session_state:
    existing = db.list_projects()
    if not existing:
        db.save_project_state("Prospect ND", _fresh_project_state())
        existing = ["Prospect ND"]
    st.session_state.active_project = existing[0]
    _load_project(st.session_state.active_project)

# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------
st.markdown("""
<div style="background:linear-gradient(90deg,#1B2631,#283747);padding:18px 24px;border-radius:10px;margin-bottom:6px;">
  <h1 style="color:#F4D03F;margin:0;font-size:32px;">⛏️ ESPACE VIRTUELLE MINIÈRE DE SMC</h1>
  <p style="color:#D6DBDF;margin:4px 0 0 0;font-size:15px;">Dashboard d'exploration minière — Sections géologiques & Logs automatisés (Phase 1)</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("### 🌍 Prospect actif")
proj_names = db.list_projects()
if st.session_state.active_project not in proj_names:
    proj_names.append(st.session_state.active_project)
chosen = st.sidebar.selectbox("Sélectionner un prospect", proj_names,
                               index=proj_names.index(st.session_state.active_project))
if chosen != st.session_state.active_project:
    _save_active_to_db()  # sauvegarde l'ancien prospect avant de changer
    st.session_state.active_project = chosen
    _load_project(chosen)
    st.rerun()

last_saved = db.last_saved(st.session_state.active_project)
if last_saved:
    st.sidebar.caption(f"💾 Dernière sauvegarde : {last_saved}")

with st.sidebar.expander("➕ Créer / supprimer un prospect"):
    new_name = st.text_input("Nom du nouveau prospect", key="new_proj_name")
    if st.button("Créer ce prospect") and new_name and new_name not in proj_names:
        _save_active_to_db()
        db.save_project_state(new_name, _fresh_project_state())
        st.session_state.active_project = new_name
        _load_project(new_name)
        st.rerun()
    if len(proj_names) > 1 and st.button("🗑️ Supprimer le prospect actif", type="secondary"):
        db.delete_project(st.session_state.active_project)
        remaining = db.list_projects()
        st.session_state.active_project = remaining[0]
        _load_project(remaining[0])
        st.rerun()

if st.sidebar.button("💾 Sauvegarder maintenant"):
    _save_active_to_db()
    st.sidebar.success("Sauvegardé.")

prospect = st.session_state.active_project
permis = st.sidebar.text_input("Nom du permis", value=st.session_state.get("permis", ""))
st.session_state["permis"] = permis
st.sidebar.caption("📁 Les données sont sauvegardées dans un fichier local (smc_dashboard.db). "
                    "Sur un hébergement éphémère (ex. cloud sans volume persistant), la base sera "
                    "réinitialisée à chaque redéploiement — héberger ce fichier sur un disque durable "
                    "pour une persistance garantie.")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["📥 Import des données", "📋 Logs automatisés", "📐 Sections géologiques",
     "🗺️ Cartes (lithologie / structurale / anomalie)", "🧭 Graphiques structuraux",
     "🧊 Modèle 3D", "🛠️ Planification & Extension", "🎯 Simulation déviation",
     "🌱 Auger & Géochimie", "💰 Estimation des teneurs",
     "🪨 SGI & Structures", "📡 Géophysique",
     "📦 Ressources & Réserves (JORC simplifié)", "💵 Budget & Coûts", "🔗 Gestion des échantillons",
     "⚗️ Métallurgie", "🦺 Environnement & HSE", "📜 SOP", "🛡️ Admin", "🤖 Audit automatique des données",
     "📄 Rapport géologique", "🗄️ Documents", "💬 Commentaires & Réponses",
     "📐 Sections par orientation de forage", "🗃️ Base de données centrale",
     "📊 Synthèse / Collars"],
)

st.sidebar.markdown("---")
st.sidebar.caption("Phase 1 du dashboard — module Sections géologiques & Logs automatisés. "
                    "D'autres modules (cartes, 3D, JORC, etc.) seront ajoutés en phases suivantes.")

# ===========================================================================
# PAGE 1 : IMPORT
# ===========================================================================
if page == "📥 Import des données":
    st.subheader("📥 Import des fichiers Excel de log")
    st.write("Chargez vos fichiers de log (gabarits SMC). Chaque fichier peut être mis à jour à tout moment ; "
             "les onglets Logs et Sections se recalculent automatiquement.")

    c1, c2, c3 = st.columns(3)
    with c1:
        f_rc = st.file_uploader("Log RC (Reverse Circulation)", type=["xlsx"], key="rc_up")
        f_ac = st.file_uploader("Log AC (Aircore)", type=["xlsx"], key="ac_up")
    with c2:
        f_dd = st.file_uploader("Log DD (Diamond Drilling)", type=["xlsx"], key="dd_up")
        f_auger = st.file_uploader("Log Géochimie Sols / Auger", type=["xlsx"], key="auger_up")
    with c3:
        f_struct = st.file_uploader("Log Structural", type=["xlsx"], key="struct_up")

    if st.button("🧪 Charger des données de démonstration (pour visualiser le dashboard)"):
        demo = generate_demo_data()
        for k, v in demo.items():
            st.session_state.data[k] = v
        all_labels = []
        for k in ["RC", "AC", "DD"]:
            d = st.session_state.data[k]
            if not d.empty and "Lithologie" in d.columns:
                all_labels += [x for x in d["Lithologie"].dropna().unique()]
        st.session_state.litho_colors = build_litho_color_map(sorted(set(all_labels)))
        st.success("Données de démonstration chargées (RC/AC/DD + Structural + Auger) ! "
                    "Explorez les autres onglets.")


    if st.button("🔄 Charger / Recharger toutes les données", type="primary"):
        msgs = []
        try:
            if f_rc:
                st.session_state.data["RC"] = parse_geologie_workbook(f_rc.read(), "RC")
                msgs.append(f"✅ RC : {len(st.session_state.data['RC'])} intervalles, "
                            f"{st.session_state.data['RC']['Sondage'].nunique() if not st.session_state.data['RC'].empty else 0} trous")
            if f_ac:
                st.session_state.data["AC"] = parse_geologie_workbook(f_ac.read(), "AC")
                msgs.append(f"✅ AC : {len(st.session_state.data['AC'])} intervalles, "
                            f"{st.session_state.data['AC']['Sondage'].nunique() if not st.session_state.data['AC'].empty else 0} trous")
            if f_dd:
                st.session_state.data["DD"] = parse_geologie_workbook(f_dd.read(), "DD")
                msgs.append(f"✅ DD : {len(st.session_state.data['DD'])} intervalles, "
                            f"{st.session_state.data['DD']['Sondage'].nunique() if not st.session_state.data['DD'].empty else 0} trous")
            if f_auger:
                st.session_state.data["AUGER"] = parse_auger_workbook(f_auger.read())
                msgs.append(f"✅ Auger/Géochimie sols : {len(st.session_state.data['AUGER'])} intervalles, "
                            f"{st.session_state.data['AUGER']['Sondage'].nunique() if not st.session_state.data['AUGER'].empty else 0} trous")
            if f_struct:
                st.session_state.data["STRUCT"] = parse_structural_workbook(f_struct.read())
                msgs.append(f"✅ Structural : {len(st.session_state.data['STRUCT'])} mesures, "
                            f"{st.session_state.data['STRUCT']['Sondage'].nunique() if not st.session_state.data['STRUCT'].empty else 0} trous")

            # construire la palette de couleurs lithologiques globale
            all_labels = []
            for k in ["RC", "AC", "DD"]:
                d = st.session_state.data[k]
                if not d.empty and "Lithologie" in d.columns:
                    all_labels += [x for x in d["Lithologie"].dropna().unique()]
            if all_labels:
                st.session_state.litho_colors = build_litho_color_map(sorted(set(all_labels)))

            if not msgs:
                st.warning("Aucun fichier n'a été sélectionné.")
            else:
                for m in msgs:
                    st.success(m)
        except Exception as e:
            st.error(f"Erreur de lecture : {e}")

    st.markdown("---")
    st.write("**État actuel des données chargées :**")
    status_cols = st.columns(5)
    labels = {"RC": "RC", "AC": "Aircore", "DD": "Diamond Drilling", "AUGER": "Auger/Géochimie", "STRUCT": "Structural"}
    for i, k in enumerate(labels):
        d = st.session_state.data[k]
        with status_cols[i]:
            if d.empty:
                st.metric(labels[k], "Vide")
            else:
                n_holes = d["Sondage"].nunique() if "Sondage" in d.columns else 0
                st.metric(labels[k], f"{n_holes} trous", f"{len(d)} interv.")

    if st.session_state.litho_colors:
        st.markdown("---")
        st.write("**Légende des lithologies (palette automatique, modifiable) :**")
        litho_cols = st.columns(6)
        new_map = {}
        for i, (litho, color) in enumerate(st.session_state.litho_colors.items()):
            with litho_cols[i % 6]:
                new_color = st.color_picker(litho, color, key=f"color_{litho}")
                new_map[litho] = new_color
        st.session_state.litho_colors = new_map

# ===========================================================================
# PAGE 2 : LOGS AUTOMATISÉS
# ===========================================================================
elif page == "📋 Logs automatisés":
    st.subheader("📋 Logs automatisés interactifs")
    drill_choice = st.selectbox("Type de sondage", ["RC", "AC", "DD", "AUGER"],
                                 format_func=lambda x: {"RC": "RC (Reverse Circulation)", "AC": "Aircore",
                                                         "DD": "Diamond Drilling", "AUGER": "Auger / Géochimie sols"}[x])
    df = st.session_state.data[drill_choice]

    if df.empty:
        st.info("Aucune donnée chargée pour ce type de sondage. Allez dans '📥 Import des données'.")
    else:
        holes = sorted(df["Sondage"].dropna().unique().tolist())
        hole = st.selectbox("Trou de forage", holes)
        sub = df[df["Sondage"] == hole].sort_values("From" if "From" in df.columns else df.columns[0])

        collar = collar_table(df)
        crow = collar[collar["Sondage"] == hole]
        cinfo = crow.iloc[0] if not crow.empty else None

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Easting", f"{cinfo['Easting']:.1f}" if cinfo is not None and pd.notna(cinfo.get("Easting")) else "N/A")
        c2.metric("Northing", f"{cinfo['Northing']:.1f}" if cinfo is not None and pd.notna(cinfo.get("Northing")) else "N/A")
        c3.metric("Élévation", f"{cinfo['Elevation']:.1f}" if cinfo is not None and pd.notna(cinfo.get("Elevation")) else "N/A")
        depth_max = sub["To"].max() if "To" in sub.columns and sub["To"].notna().any() else (
            sub["To_m"].max() if "To_m" in sub.columns and sub["To_m"].notna().any() else None)
        c4.metric("Profondeur totale", f"{depth_max:.1f} m" if depth_max is not None and pd.notna(depth_max) else "N/A")

        st.markdown("#### Log lithologique (colonne stratigraphique)")
        litho_col = "Lithologie" if "Lithologie" in sub.columns else None
        if litho_col and sub["From"].notna().any():
            fig = go.Figure()
            for _, r in sub.iterrows():
                f, t = r.get("From"), r.get("To")
                if pd.isna(f) or pd.isna(t):
                    continue
                litho = r.get("Lithologie") or "Indéterminé"
                color = st.session_state.litho_colors.get(litho, "#7F8C8D")
                fig.add_trace(go.Scatter(
                    x=[0, 1, 1, 0, 0], y=[-f, -f, -t, -t, -f],
                    fill="toself", fillcolor=color, line=dict(color="#222", width=0.5),
                    mode="lines", name=str(litho),
                    hovertemplate=f"<b>{litho}</b><br>De {f} à {t} m<br>Code: {r.get('Code_Litho','')}<br>"
                                  f"Formation: {r.get('Formation','')}<br>Texture: {r.get('Texture','')}<extra></extra>",
                    showlegend=False,
                ))
                # marqueur minéralisation
                if r.get("Has_Mineralisation"):
                    fig.add_shape(type="line", x0=1, x1=1.15, y0=-(f + t) / 2, y1=-(f + t) / 2,
                                  line=dict(color="gold", width=4))
                if r.get("Has_Alteration"):
                    fig.add_annotation(x=1.25, y=-(f + t) / 2, text="Alt", showarrow=False,
                                        font=dict(size=9, color="purple"))
            fig.update_layout(
                height=650, xaxis=dict(visible=False, range=[-0.1, 1.5]),
                yaxis=dict(title="Profondeur (m)"), margin=dict(l=40, r=20, t=20, b=20),
                plot_bgcolor="white",
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption("🟡 Trait doré = intervalle minéralisé (sulfures détectés) · violet 'Alt' = intervalle altéré")
        else:
            st.warning("Colonnes From/To/Lithologie manquantes ou vides pour ce trou.")

        st.markdown("#### Tableau de log complet")
        st.dataframe(sub, use_container_width=True, height=350)

        # Texte d'interprétation automatique
        st.markdown("#### 🧠 Interprétation automatique")
        litho_counts = sub["Lithologie"].dropna().value_counts() if "Lithologie" in sub.columns else pd.Series(dtype=int)
        n_mineral = int(sub["Has_Mineralisation"].sum()) if "Has_Mineralisation" in sub.columns else 0
        n_alt = int(sub["Has_Alteration"].sum()) if "Has_Alteration" in sub.columns else 0
        text = f"Le trou **{hole}** ({drill_choice}) a traversé **{depth_max if depth_max else 'N/A'} m**. "
        if not litho_counts.empty:
            text += f"La lithologie dominante est **{litho_counts.index[0]}** ({litho_counts.iloc[0]} intervalle(s)). "
        if n_mineral:
            text += f"**{n_mineral} intervalle(s)** présentent des indices de minéralisation sulfurée. "
        if n_alt:
            text += f"**{n_alt} intervalle(s)** montrent une altération hydrothermale. "
        if n_mineral == 0 and n_alt == 0:
            text += "Aucun indice de minéralisation ou d'altération n'a encore été renseigné pour ce trou — " \
                    "vérifier la saisie des feuilles M (Minéralisation) et Al (Altération)."
        st.info(text)

# ===========================================================================
# PAGE 3 : SECTIONS GÉOLOGIQUES
# ===========================================================================
elif page == "📐 Sections géologiques":
    st.subheader("📐 Sections géologiques interprétées")

    drill_types = st.multiselect("Types de sondage à inclure dans la section",
                                  ["RC", "AC", "DD"], default=["RC", "AC", "DD"])
    all_df = safe_concat(drill_types)

    if all_df.empty:
        st.info("Aucune donnée disponible. Importez d'abord des fichiers RC/AC/DD.")
    else:
        collars = collar_table(all_df)
        collars = collars.dropna(subset=["Easting", "Northing"])
        if collars.empty:
            st.warning("Aucune coordonnée (Easting/Northing) renseignée dans les fichiers chargés. "
                       "La section ne peut pas être positionnée — vérifiez les colonnes de coordonnées.")
        else:
            holes_sel = st.multiselect("Trous à inclure dans la section", collars["Sondage"].tolist(),
                                        default=collars["Sondage"].tolist()[:min(6, len(collars))])
            section_name = st.text_input("Numéro / nom de la section", value="Section A-A'")
            ech_v = st.slider("Exagération verticale", 0.5, 3.0, 1.0, 0.1)

            if holes_sel:
                sec = collars[collars["Sondage"].isin(holes_sel)].copy()
                # projection simple sur l'axe principal (régression des collars) -> distance le long de la section
                if len(sec) >= 2:
                    x = sec["Easting"].values
                    y = sec["Northing"].values
                    dx, dy = x.max() - x.min(), y.max() - y.min()
                    if abs(dx) > abs(dy):
                        order = np.argsort(x)
                    else:
                        order = np.argsort(y)
                    sec = sec.iloc[order].reset_index(drop=True)
                    # distance cumulée projetée
                    ref_x, ref_y = sec["Easting"].iloc[0], sec["Northing"].iloc[0]
                    sec["Dist_section"] = np.sqrt((sec["Easting"] - ref_x) ** 2 + (sec["Northing"] - ref_y) ** 2)
                else:
                    sec["Dist_section"] = 0

                fig = go.Figure()
                width = 12

                for _, hrow in sec.iterrows():
                    hole = hrow["Sondage"]
                    xpos = hrow["Dist_section"]
                    collar_elev = hrow["Elevation"] if pd.notna(hrow["Elevation"]) else 0
                    hdf = all_df[all_df["Sondage"] == hole].sort_values("From")
                    for _, r in hdf.iterrows():
                        f, t = r.get("From"), r.get("To")
                        if pd.isna(f) or pd.isna(t):
                            continue
                        litho = r.get("Lithologie") or "Indéterminé"
                        color = st.session_state.litho_colors.get(litho, "#7F8C8D")
                        z_top = collar_elev - f * ech_v
                        z_bot = collar_elev - t * ech_v
                        fig.add_trace(go.Scatter(
                            x=[xpos - width / 2, xpos + width / 2, xpos + width / 2, xpos - width / 2, xpos - width / 2],
                            y=[z_top, z_top, z_bot, z_bot, z_top],
                            fill="toself", fillcolor=color, line=dict(color="#222", width=0.4),
                            mode="lines", showlegend=False,
                            hovertemplate=f"<b>{hole}</b><br>{litho}<br>{f}-{t} m<extra></extra>",
                        ))
                        if r.get("Has_Mineralisation"):
                            fig.add_shape(type="line", x0=xpos + width / 2, x1=xpos + width / 2 + 3,
                                          y0=(z_top + z_bot) / 2, y1=(z_top + z_bot) / 2,
                                          line=dict(color="gold", width=3))
                        wc = r.get("Weathering_Class")
                        if wc in ("LAT", "SAP", "SAPROCK", "FRESH") and t == hdf[hdf["Weathering_Class"] == wc]["To"].max():
                            fig.add_annotation(x=xpos, y=z_bot, text=wc, showarrow=False,
                                                font=dict(size=8, color="black"), bgcolor="white", opacity=0.7)

                    # ligne topo / repère trou
                    total_depth = hdf["To"].max() if not hdf.empty and hdf["To"].notna().any() else 0
                    fig.add_annotation(x=xpos, y=collar_elev + 8, text=f"<b>{hole}</b>", showarrow=False,
                                        font=dict(size=11, color="black"))
                    fig.add_annotation(x=xpos, y=collar_elev + 3, text=f"{total_depth:.0f} m", showarrow=False,
                                        font=dict(size=9, color="gray"))

                # ligne topographique (reliant les collars)
                fig.add_trace(go.Scatter(x=sec["Dist_section"], y=sec["Elevation"], mode="lines",
                                          line=dict(color="saddlebrown", width=2, dash="dot"),
                                          name="Ligne topographique"))

                fig.update_layout(
                    title=f"{section_name} — {prospect}" + (f" / Permis {permis}" if permis else ""),
                    xaxis=dict(title="Distance le long de la section (m)"),
                    yaxis=dict(title=f"Élévation (m) — exag. verticale x{ech_v}"),
                    height=700, plot_bgcolor="#F8F9F9",
                    annotations=[dict(
                        x=0.99, y=0.99, xref="paper", yref="paper", showarrow=False,
                        text=f"N ↑<br>Échelle horiz. ≈ {int(sec['Dist_section'].max())} m<br>Réf: {sec['Sondage'].iloc[0]}",
                        align="right", bgcolor="white", bordercolor="black", borderwidth=1,
                    )],
                )
                st.plotly_chart(fig, use_container_width=True)

                # légende
                st.markdown("**Légende lithologique :**")
                leg_cols = st.columns(6)
                used = sorted(set(all_df[all_df["Sondage"].isin(holes_sel)]["Lithologie"].dropna().unique()))
                for i, l in enumerate(used):
                    c = st.session_state.litho_colors.get(l, "#7F8C8D")
                    with leg_cols[i % 6]:
                        st.markdown(f"<div style='display:flex;align-items:center;gap:6px;'>"
                                    f"<div style='width:16px;height:16px;background:{c};border:1px solid #222;'></div>"
                                    f"<span style='font-size:12px'>{l}</span></div>", unsafe_allow_html=True)

                st.markdown("#### 🧠 Interprétation de la section")
                n_holes = len(holes_sel)
                n_mineral_holes = sum(1 for h in holes_sel if all_df[(all_df["Sondage"] == h)]["Has_Mineralisation"].any())
                st.info(f"La section **{section_name}** regroupe **{n_holes} trou(s)** "
                        f"({', '.join(drill_types)}). **{n_mineral_holes}** trou(s) sur {n_holes} recoupent des "
                        f"intervalles minéralisés. Les limites d'altération météorique (latérite/saprolite/saprock/"
                        f"socle) sont annotées le long de chaque trou. Vérifiez la cohérence latérale des contacts "
                        f"lithologiques d'un trou à l'autre pour affiner la corrélation stratigraphique.")
            else:
                st.info("Sélectionnez au moins un trou.")

# ===========================================================================
# PAGE : CARTES (LITHOLOGIE / STRUCTURALE / ANOMALIE)
# ===========================================================================
elif page == "🗺️ Cartes (lithologie / structurale / anomalie)":
    st.subheader("🗺️ Cartes du prospect")
    tab_litho, tab_struct, tab_anom = st.tabs(["🎨 Carte lithologie", "🧱 Carte structurale", "🔥 Carte d'anomalie"])

    all_df = safe_concat(["RC", "AC", "DD"])

    # ---------------- CARTE LITHOLOGIE ----------------
    with tab_litho:
        if all_df.empty:
            st.info("Aucune donnée RC/AC/DD chargée.")
        else:
            niveau = st.radio("Affichage", ["Lithologie de surface (1er intervalle de chaque trou)",
                                             "Lithologie dominante sur toute la profondeur"], horizontal=True)
            collars = collar_table(all_df).dropna(subset=["Easting", "Northing"])
            if niveau.startswith("Lithologie de surface"):
                first_int = all_df.sort_values("From").groupby("Sondage").first().reset_index()
                plot_df = collars.merge(first_int[["Sondage", "Lithologie"]], on="Sondage", how="left")
            else:
                dom = all_df.groupby("Sondage")["Lithologie"].agg(lambda s: s.value_counts().idxmax() if s.notna().any() else None).reset_index()
                plot_df = collars.merge(dom, on="Sondage", how="left")

            fig = go.Figure()
            for litho in plot_df["Lithologie"].dropna().unique():
                sub = plot_df[plot_df["Lithologie"] == litho]
                color = st.session_state.litho_colors.get(litho, "#7F8C8D")
                fig.add_trace(go.Scatter(
                    x=sub["Easting"], y=sub["Northing"], mode="markers+text",
                    marker=dict(size=16, color=color, line=dict(width=1.5, color="black"), symbol="circle"),
                    text=sub["Sondage"], textposition="top center", name=str(litho),
                ))
            fig.add_annotation(x=0.97, y=0.97, xref="paper", yref="paper", showarrow=False,
                                text="N ↑", font=dict(size=18, color="black"))
            fig.update_layout(
                title=f"Carte lithologie — {prospect}" + (f" / {permis}" if permis else ""),
                xaxis_title="Easting", yaxis_title="Northing", height=650,
                yaxis=dict(scaleanchor="x", scaleratio=1), legend_title="Lithologie",
                plot_bgcolor="#FAFAFA",
            )
            st.plotly_chart(fig, use_container_width=True)
            n_litho = plot_df["Lithologie"].nunique()
            st.info(f"🧠 **Interprétation** : la carte affiche **{n_litho} lithologies distinctes** réparties sur "
                    f"**{len(plot_df)} trous**. Chaque couleur correspond à une lithologie unique (palette "
                    f"automatique, modifiable dans l'onglet Import). Une concentration spatiale d'une même "
                    f"lithologie peut indiquer une unité litho-stratigraphique continue ou un corps intrusif/"
                    f"volcanique localisé — à vérifier par corrélation de section.")

    # ---------------- CARTE STRUCTURALE ----------------
    with tab_struct:
        sdf = st.session_state.data["STRUCT"]
        if sdf.empty or "Azimut" not in sdf.columns or sdf["Azimut"].dropna().empty:
            st.info("Aucune donnée structurale (Azimut/Pendage) chargée.")
        else:
            agg = sdf.groupby("Sondage").agg(
                Easting=("Easting", "first"), Northing=("Northing", "first"),
                Azimut_moy=("Azimut", "mean"), Pendage_moy=("Pendage", "mean"), N_mesures=("Azimut", "count"),
            ).reset_index().dropna(subset=["Easting", "Northing"])

            fig = go.Figure()
            L = 30
            for _, r in agg.iterrows():
                az_rad = np.radians(r["Azimut_moy"])
                dx, dy = L * np.sin(az_rad), L * np.cos(az_rad)
                fig.add_trace(go.Scatter(x=[r["Easting"] - dx / 2, r["Easting"] + dx / 2],
                                          y=[r["Northing"] - dy / 2, r["Northing"] + dy / 2],
                                          mode="lines", line=dict(color="#922B21", width=3), showlegend=False,
                                          hovertemplate=f"<b>{r['Sondage']}</b><br>Az. moy: {r['Azimut_moy']:.0f}°<br>"
                                                        f"Pendage moy: {r['Pendage_moy']:.0f}°<br>{r['N_mesures']} mesures<extra></extra>"))
                fig.add_trace(go.Scatter(x=[r["Easting"]], y=[r["Northing"]], mode="markers+text",
                                          marker=dict(size=10, color="#922B21"), text=r["Sondage"],
                                          textposition="bottom center", showlegend=False))
            fig.add_annotation(x=0.97, y=0.97, xref="paper", yref="paper", showarrow=False,
                                text="N ↑", font=dict(size=18, color="black"))
            fig.update_layout(title=f"Carte structurale (azimut/pendage moyens par trou) — {prospect}",
                               xaxis_title="Easting", yaxis_title="Northing", height=650,
                               yaxis=dict(scaleanchor="x", scaleratio=1), plot_bgcolor="#FAFAFA")
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Chaque trait rouge représente l'azimut structural moyen mesuré dans le trou "
                       "(foliation/fracture/veine/faille selon OCTypes). Longueur = symbolique, non à l'échelle du pendage.")
            st.dataframe(agg, use_container_width=True)
            st.info(f"🧠 **Interprétation** : {len(agg)} trou(s) disposent de mesures structurales. "
                    f"L'azimut moyen global est de **{agg['Azimut_moy'].mean():.0f}°** et le pendage moyen de "
                    f"**{agg['Pendage_moy'].mean():.0f}°**. Une orientation structurale cohérente entre trous "
                    f"voisins suggère une fabrique tectonique régionale (foliation/schistosité) ou un système de "
                    f"failles/veines organisé — comparer avec la carte d'anomalie pour évaluer le contrôle structural "
                    f"de la minéralisation.")

    # ---------------- CARTE ANOMALIE ----------------
    with tab_anom:
        if all_df.empty:
            st.info("Aucune donnée RC/AC/DD chargée.")
        else:
            collars = collar_table(all_df).dropna(subset=["Easting", "Northing"])
            mineral_stats = all_df.groupby("Sondage").agg(
                N_intervalles=("Has_Mineralisation", "size"),
                N_mineralises=("Has_Mineralisation", "sum"),
            ).reset_index()
            mineral_stats["Pct_mineralise"] = (mineral_stats["N_mineralises"] / mineral_stats["N_intervalles"] * 100).round(1)
            plot_df = collars.merge(mineral_stats, on="Sondage", how="left").fillna(0)

            # roche/structure hôte de la minéralisation la plus fréquente
            min_rows = all_df[all_df["Has_Mineralisation"] == True]
            host_litho = min_rows["Lithologie"].value_counts().head(3) if not min_rows.empty and "Lithologie" in min_rows.columns else pd.Series(dtype=int)

            fig = go.Figure(go.Scatter(
                x=plot_df["Easting"], y=plot_df["Northing"], mode="markers+text",
                marker=dict(size=plot_df["Pct_mineralise"].clip(lower=8) + 8,
                            color=plot_df["Pct_mineralise"], colorscale="Hot", reversescale=True,
                            showscale=True, colorbar=dict(title="% intervalles<br>minéralisés"),
                            line=dict(width=1, color="black")),
                text=plot_df["Sondage"], textposition="top center",
                hovertemplate="<b>%{text}</b><br>%% minéralisé: %{marker.color:.1f}%<extra></extra>",
            ))
            fig.add_annotation(x=0.97, y=0.97, xref="paper", yref="paper", showarrow=False,
                                text="N ↑", font=dict(size=18, color="black"))
            fig.update_layout(title=f"Carte d'anomalie — potentiel minéralisé — {prospect}",
                               xaxis_title="Easting", yaxis_title="Northing", height=650,
                               yaxis=dict(scaleanchor="x", scaleratio=1), plot_bgcolor="#FAFAFA")
            st.plotly_chart(fig, use_container_width=True)

            top_holes = plot_df.sort_values("Pct_mineralise", ascending=False).head(5)
            st.markdown("**🎯 Trous à plus fort potentiel (priorité infill/extension) :**")
            st.dataframe(top_holes[["Sondage", "Pct_mineralise", "N_mineralises", "N_intervalles"]], use_container_width=True)

            host_text = ", ".join([f"**{l}** ({c} interv.)" for l, c in host_litho.items()]) if not host_litho.empty else "non déterminée (renseigner la feuille M)"
            st.info(f"🧠 **Interprétation** : les trous les plus prometteurs sont "
                    f"**{', '.join(top_holes['Sondage'].head(3).tolist())}**. La minéralisation est portée "
                    f"principalement par : {host_text}. Ces lithologies/structures hôtes devraient guider le "
                    f"ciblage des futurs forages d'extension et d'infill autour de ces secteurs à forte "
                    f"densité minéralisée.")

# ===========================================================================
# PAGE : GRAPHIQUES STRUCTURAUX
# ===========================================================================
elif page == "🧭 Graphiques structuraux":
    st.subheader("🧭 Graphiques structuraux classiques")
    sdf = st.session_state.data["STRUCT"]
    if sdf.empty or "Azimut" not in sdf.columns or sdf["Azimut"].dropna().empty:
        st.info("Aucune donnée structurale chargée. Importez un Log Structural ou chargez les données de démonstration.")
    else:
        sdf2 = sdf.dropna(subset=["Azimut", "Pendage"]).copy()
        tab_rose, tab_stereo, tab_tadpole = st.tabs(["🌹 Rosace", "🧊 Stéréonet (simplifié)", "🪱 Tadpole plot"])

        with tab_rose:
            bins = np.arange(0, 361, 10)
            counts, edges = np.histogram(sdf2["Azimut"], bins=bins)
            fig = go.Figure(go.Barpolar(r=counts, theta=edges[:-1] + 5, width=10,
                                         marker_color="#7B241C", marker_line_color="black", marker_line_width=0.5))
            fig.update_layout(title="Rosace des directions structurales (azimut)",
                               polar=dict(angularaxis=dict(direction="clockwise", rotation=90)), height=550)
            st.plotly_chart(fig, use_container_width=True)
            dom_az = edges[:-1][np.argmax(counts)]
            st.info(f"🧠 La direction structurale dominante se situe autour de **{dom_az:.0f}°–{dom_az+10:.0f}°**, "
                    f"sur {len(sdf2)} mesures. Cela peut traduire l'orientation principale de la foliation/"
                    f"schistosité ou d'un système de fractures/veines contrôlant la minéralisation.")

        with tab_stereo:
            st.caption("Projection simplifiée (pôle de plan : azimut = direction, rayon = 90° − pendage). "
                       "Ce n'est pas une projection stéréographique équiaire stricte (type logiciel Dips), "
                       "mais une approximation utile pour visualiser les familles structurales.")
            r = 90 - sdf2["Pendage"]
            fig = go.Figure(go.Scatterpolar(
                r=r, theta=sdf2["Azimut"], mode="markers",
                marker=dict(size=7, color=sdf2["Pendage"], colorscale="Turbo", showscale=True,
                            colorbar=dict(title="Pendage °"), line=dict(width=0.5, color="black")),
                text=sdf2.get("OCTypes", ""), hovertemplate="Az %{theta}°<br>%{text}<extra></extra>",
            ))
            fig.update_layout(polar=dict(radialaxis=dict(range=[0, 90], showticklabels=False),
                                          angularaxis=dict(direction="clockwise", rotation=90)),
                               title="Pseudo-stéréonet — pôles des structures", height=600)
            st.plotly_chart(fig, use_container_width=True)

        with tab_tadpole:
            holes = sorted(sdf2["Sondage"].dropna().unique().tolist())
            hole = st.selectbox("Trou", holes)
            hsub = sdf2[sdf2["Sondage"] == hole].sort_values("From_m")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hsub["Pendage"], y=-hsub["From_m"], mode="markers",
                                      marker=dict(size=9, color="#1B4F72"), name="Pendage"))
            for _, r in hsub.iterrows():
                az_rad = np.radians(r["Azimut"])
                dx, dy = 6 * np.sin(az_rad), 1.5 * np.cos(az_rad)
                fig.add_shape(type="line", x0=r["Pendage"], x1=r["Pendage"] + dx,
                              y0=-r["From_m"], y1=-r["From_m"] + dy, line=dict(color="#1B4F72", width=1.5))
            fig.update_layout(title=f"Tadpole plot — {hole} (pendage vs profondeur, queue = azimut)",
                               xaxis=dict(title="Pendage (°)", range=[0, 95]),
                               yaxis=dict(title="Profondeur (m)"), height=650)
            st.plotly_chart(fig, use_container_width=True)
            st.info(f"🧠 Le trou **{hole}** comporte **{len(hsub)} mesures structurales**. La dispersion du "
                    f"pendage en profondeur permet de repérer les zones de changement structural (zones de "
                    f"cisaillement, contacts) — une rupture nette de tendance est souvent corrélée à un contact "
                    f"lithologique ou une zone de faille.")

# ===========================================================================
# PAGE : MODÈLE 3D
# ===========================================================================
elif page == "🧊 Modèle 3D":
    st.subheader("🧊 Modèle 3D des trous de forage")
    drill_types = st.multiselect("Types de sondage", ["RC", "AC", "DD"], default=["RC", "AC", "DD"], key="m3d_types")
    all_df = safe_concat(drill_types)
    sdf = st.session_state.data["STRUCT"]

    if all_df.empty:
        st.info("Aucune donnée chargée. Utilisez les données de démonstration ou importez vos fichiers.")
    else:
        collars = collar_table(all_df).dropna(subset=["Easting", "Northing"])
        fig = go.Figure()
        for _, hrow in collars.iterrows():
            hole = hrow["Sondage"]
            hdf = all_df[all_df["Sondage"] == hole].sort_values("From")
            az, dip = 0.0, 90.0
            if not sdf.empty and "Azimut" in sdf.columns:
                hs = sdf[sdf["Sondage"] == hole]
                if not hs.empty and hs["Azimut"].notna().any():
                    az, dip = hs["Azimut"].mean(), hs["Pendage"].mean()
            depth = hdf["To"].max() if hdf["To"].notna().any() else 50
            traj = hole_trajectory(hrow["Easting"], hrow["Northing"], hrow["Elevation"], az, dip, depth, n_points=30)
            for _, r in hdf.iterrows():
                f, t = r.get("From"), r.get("To")
                if pd.isna(f) or pd.isna(t):
                    continue
                litho = r.get("Lithologie") or "Indéterminé"
                color = st.session_state.litho_colors.get(litho, "#7F8C8D")
                seg = traj[(traj["Depth"] >= f) & (traj["Depth"] <= t)]
                if seg.empty:
                    seg = traj.iloc[[(traj["Depth"] - f).abs().idxmin(), (traj["Depth"] - t).abs().idxmin()]]
                fig.add_trace(go.Scatter3d(x=seg["Easting"], y=seg["Northing"], z=seg["Elevation"],
                                            mode="lines", line=dict(color=color, width=8), showlegend=False,
                                            hovertemplate=f"<b>{hole}</b><br>{litho}<br>{f}-{t}m<extra></extra>"))
            fig.add_trace(go.Scatter3d(x=[hrow["Easting"]], y=[hrow["Northing"]], z=[hrow["Elevation"] + 2],
                                        mode="text", text=[hole], showlegend=False))
        fig.update_layout(height=750, scene=dict(xaxis_title="Easting", yaxis_title="Northing", zaxis_title="Élévation (m)",
                                                   aspectmode="data"),
                           title=f"Modèle 3D des trous — {prospect}")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Trajectoire calculée à partir de l'azimut/pendage moyen mesuré (Log Structural) si disponible, "
                   "sinon trou supposé vertical. Couleur = lithologie.")
        st.info("🧠 **Interprétation** : ce modèle 3D simplifié permet de visualiser la continuité spatiale des "
                "unités lithologiques entre trous. Pour un modèle de blocs géostatistique complet (krigeage, "
                "blocs de teneur), un export vers un logiciel spécialisé (Leapfrog, Datamine, Surpac) reste "
                "recommandé — ce module sert de pré-visualisation rapide et de contrôle qualité terrain.")

# ===========================================================================
# PAGE : PLANIFICATION & EXTENSION
# ===========================================================================
elif page == "🛠️ Planification & Extension":
    st.subheader("🛠️ Programme de forage — Infill / Extension")
    st.write("Ajoutez, modifiez ou supprimez des lignes directement dans le tableau ci-dessous. "
             "Statut : **Planifié** (gris), **Foré** (bleu), **En cours** (vert), **Stoppé** (rouge).")

    edited = st.data_editor(
        st.session_state.planning, num_rows="dynamic", use_container_width=True, key="planning_editor",
        column_config={
            "Statut": st.column_config.SelectboxColumn(options=["Planifié", "En cours", "Foré", "Stoppé"]),
            "Type": st.column_config.SelectboxColumn(options=["RC", "AC", "DD", "Auger"]),
        },
    )
    st.session_state.planning = edited

    if not edited.empty and edited["Easting"].notna().any():
        st.markdown("#### Carte de planification (par ligne de forage)")
        lignes = sorted(edited["Ligne"].dropna().unique().tolist())
        status_color = {"Foré": "#2471A3", "En cours": "#27AE60", "Stoppé": "#C0392B", "Planifié": "#909497"}
        plot_df = edited.dropna(subset=["Easting", "Northing"])
        fig = go.Figure()
        for statut, color in status_color.items():
            sub = plot_df[plot_df["Statut"] == statut]
            if sub.empty:
                continue
            fig.add_trace(go.Scatter(x=sub["Easting"], y=sub["Northing"], mode="markers+text",
                                      marker=dict(size=14, color=color, line=dict(width=1, color="black")),
                                      text=sub["Trou_ID"], textposition="top center", name=statut))
        fig.add_annotation(x=0.97, y=0.97, xref="paper", yref="paper", showarrow=False, text="N ↑",
                            font=dict(size=18, color="black"))
        fig.update_layout(title=f"Plan de forage — {prospect} (10 lignes max recommandées par campagne)",
                           xaxis_title="Easting", yaxis_title="Northing", height=600,
                           yaxis=dict(scaleanchor="x", scaleratio=1), plot_bgcolor="#FAFAFA")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"🟦 Foré · 🟩 En cours · 🟥 Stoppé · ⬜ Planifié — {len(lignes)} ligne(s) de forage définies.")

        st.markdown("#### 💰 Estimation des coûts du programme")
        edited["Cout_total"] = edited["Profondeur_prevue_m"].fillna(0) * edited["Cout_unitaire_par_m"].fillna(0)
        c1, c2, c3 = st.columns(3)
        c1.metric("Nb de trous planifiés", len(edited))
        c2.metric("Mètrage total prévu", f"{edited['Profondeur_prevue_m'].fillna(0).sum():.0f} m")
        c3.metric("Coût total estimé", f"{edited['Cout_total'].sum():,.0f}".replace(",", " "))
        st.dataframe(edited[["Trou_ID", "Type", "Ligne", "Statut", "Profondeur_prevue_m", "Cout_total"]],
                     use_container_width=True)

        n_fore = (edited["Statut"] == "Foré").sum()
        n_cours = (edited["Statut"] == "En cours").sum()
        n_stop = (edited["Statut"] == "Stoppé").sum()
        st.info(f"🧠 **Interprétation** : sur {len(edited)} trous planifiés, **{n_fore} forés**, "
                f"**{n_cours} en cours**, **{n_stop} stoppé(s)**. Les trous stoppés méritent une revue "
                f"(problème technique, terrain, ou cible atteinte) avant de valider la suite du programme "
                f"d'extension/infill.")
    else:
        st.info("Le tableau est vide — ajoutez des lignes (clic sur '+' en bas du tableau) pour démarrer "
                "votre programme de forage.")

# ===========================================================================
# PAGE : SIMULATION DÉVIATION
# ===========================================================================
elif page == "🎯 Simulation déviation":
    st.subheader("🎯 Simulation azimut / inclinaison — déviation de forage")
    st.write("Comparez la trajectoire **planifiée** (ligne droite théorique) à une trajectoire "
             "**simulée avec déviation** (dérive d'azimut et/ou aplatissement du pendage en profondeur), "
             "utile pour anticiper les écarts en forage profond (DD notamment).")

    c1, c2, c3 = st.columns(3)
    with c1:
        e0 = st.number_input("Easting collar", value=450000.0)
        n0 = st.number_input("Northing collar", value=850000.0)
        z0 = st.number_input("Élévation collar", value=320.0)
    with c2:
        az0 = st.number_input("Azimut planifié (°)", 0.0, 360.0, 45.0)
        dip0 = st.number_input("Pendage planifié (°, 90=vertical)", 1.0, 90.0, 60.0)
        depth = st.number_input("Profondeur prévue (m)", 10.0, 1000.0, 200.0)
    with c3:
        az_drift = st.slider("Dérive azimut cumulée (°)", -30.0, 30.0, 8.0, 0.5)
        dip_drift = st.slider("Aplatissement pendage cumulé (°)", -10.0, 30.0, 6.0, 0.5)

    planned = hole_trajectory(e0, n0, z0, az0, dip0, depth, az_drift=0, dip_drift=0, n_points=50)
    simulated = hole_trajectory(e0, n0, z0, az0, dip0, depth, az_drift=az_drift, dip_drift=dip_drift, n_points=50)

    fig = go.Figure()
    fig.add_trace(go.Scatter3d(x=planned["Easting"], y=planned["Northing"], z=planned["Elevation"],
                                mode="lines", line=dict(color="#2471A3", width=6), name="Trajectoire planifiée"))
    fig.add_trace(go.Scatter3d(x=simulated["Easting"], y=simulated["Northing"], z=simulated["Elevation"],
                                mode="lines", line=dict(color="#C0392B", width=6, dash="dash"), name="Trajectoire simulée (déviée)"))
    fig.update_layout(height=700, scene=dict(xaxis_title="Easting", yaxis_title="Northing", zaxis_title="Élévation (m)",
                                               aspectmode="data"),
                       title="Simulation de déviation de forage")
    st.plotly_chart(fig, use_container_width=True)

    ecart_final = np.sqrt((planned["Easting"].iloc[-1] - simulated["Easting"].iloc[-1]) ** 2 +
                           (planned["Northing"].iloc[-1] - simulated["Northing"].iloc[-1]) ** 2 +
                           (planned["Elevation"].iloc[-1] - simulated["Elevation"].iloc[-1]) ** 2)
    st.metric("Écart au fond de trou (planifié vs simulé)", f"{ecart_final:.1f} m")
    st.info(f"🧠 **Interprétation** : avec une dérive d'azimut de {az_drift:+.1f}° et un aplatissement de pendage "
            f"de {dip_drift:+.1f}° sur {depth:.0f} m, l'écart estimé au fond de trou est de **{ecart_final:.1f} m** "
            f"par rapport à la cible planifiée. " +
            ("Cet écart est significatif : un levé déviométrique (survey) régulier est recommandé tous les 30 à 50 m."
             if ecart_final > 10 else "Cet écart reste modéré, surveillance standard suffisante.") +
            " Un suivi de survey réel (gyroscopique ou magnétique) doit remplacer cette estimation dès que "
            "les données de déviomètre terrain sont disponibles.")

# ===========================================================================
# PAGE : AUGER & GÉOCHIMIE
# ===========================================================================
elif page == "🌱 Auger & Géochimie":
    st.subheader("🌱 Auger & Géochimie sols")
    df = st.session_state.data["AUGER"]
    if df.empty:
        st.info("Aucune donnée Auger/Géochimie chargée.")
    else:
        tab_table, tab_map, tab_pxrf = st.tabs(["📋 Données", "🔥 Carte d'anomalie Au", "🧪 pXRF"])

        with tab_table:
            holes = sorted(df["Sondage"].dropna().unique().tolist())
            hole = st.selectbox("Trou Auger", ["Tous"] + holes)
            show = df if hole == "Tous" else df[df["Sondage"] == hole]
            st.dataframe(show, use_container_width=True, height=400)

        with tab_map:
            if "Au_ppb" in df.columns and df["Au_ppb"].notna().any():
                agg = df.groupby("Sondage").agg(Easting=("Easting", "first"), Northing=("Northing", "first"),
                                                  Au_max=("Au_ppb", "max")).dropna(subset=["Easting", "Northing"])
                seuil = agg["Au_max"].quantile(0.75)
                fig = go.Figure(go.Scatter(x=agg["Easting"], y=agg["Northing"], mode="markers+text",
                                            marker=dict(size=(agg["Au_max"] / agg["Au_max"].max() * 25 + 8),
                                                        color=agg["Au_max"], colorscale="Hot", reversescale=True,
                                                        showscale=True, colorbar=dict(title="Au (ppb)"),
                                                        line=dict(width=1, color="black")),
                                            text=agg.index, textposition="top center"))
                fig.add_annotation(x=0.97, y=0.97, xref="paper", yref="paper", showarrow=False, text="N ↑",
                                    font=dict(size=18, color="black"))
                fig.update_layout(title="Carte d'anomalie Au — Auger/sols", xaxis_title="Easting",
                                   yaxis_title="Northing", height=600, yaxis=dict(scaleanchor="x", scaleratio=1))
                st.plotly_chart(fig, use_container_width=True)
                top = agg[agg["Au_max"] >= seuil].sort_values("Au_max", ascending=False)
                st.info(f"🧠 **Interprétation** : seuil anomal (75e percentile) = **{seuil:.1f} ppb Au**. "
                        f"{len(top)} point(s) Auger dépassent ce seuil : {', '.join(top.index.tolist())}. "
                        f"Ces zones sont prioritaires pour un suivi par forage RC/AC d'extension.")
            else:
                st.warning("Pas de colonne Au_ppb renseignée.")

        with tab_pxrf:
            st.write("Chargez un fichier pXRF (colonnes libres : Sondage, From, To, éléments en ppm).")
            f_pxrf = st.file_uploader("Fichier pXRF (xlsx/csv)", type=["xlsx", "csv"], key="pxrf_up")
            if f_pxrf:
                pxrf_df = pd.read_csv(f_pxrf) if f_pxrf.name.endswith(".csv") else pd.read_excel(f_pxrf)
                st.dataframe(pxrf_df, use_container_width=True)
                num_cols = pxrf_df.select_dtypes(include=[np.number]).columns.tolist()
                if num_cols:
                    elem = st.selectbox("Élément à visualiser", num_cols)
                    fig = go.Figure(go.Histogram(x=pxrf_df[elem], nbinsx=30, marker_color="#7B241C"))
                    fig.update_layout(title=f"Distribution pXRF — {elem}", height=400)
                    st.plotly_chart(fig, use_container_width=True)

# ===========================================================================
# PAGE : ESTIMATION DES TENEURS
# ===========================================================================
elif page == "💰 Estimation des teneurs":
    st.subheader("💰 Estimation des teneurs en or")
    auger = st.session_state.data["AUGER"]
    st.write("Estimation simplifiée (moyenne pondérée par longueur d'intervalle), à partir des teneurs Au "
             "disponibles. ⚠️ Vos fichiers RC/AC/DD ne contiennent pas de colonne de teneur — seule la "
             "géochimie sols/Auger en a une pour le moment. Uploadez un fichier d'assays (Sondage, From, To, "
             "Au_ppm ou Au_ppb) pour étendre l'estimation aux RC/AC/DD.")

    f_assay = st.file_uploader("Fichier d'analyses (assays) RC/AC/DD — optionnel", type=["xlsx", "csv"], key="assay_up")
    assay_df = None
    if f_assay:
        assay_df = pd.read_csv(f_assay) if f_assay.name.endswith(".csv") else pd.read_excel(f_assay)
        st.dataframe(assay_df.head(20), use_container_width=True)
        val_col = st.selectbox("Colonne de teneur Au", [c for c in assay_df.columns if assay_df[c].dtype != object] or assay_df.columns.tolist())
        from_col = st.selectbox("Colonne From", assay_df.columns.tolist(), index=min(1, len(assay_df.columns) - 1))
        to_col = st.selectbox("Colonne To", assay_df.columns.tolist(), index=min(2, len(assay_df.columns) - 1))
        hole_col = st.selectbox("Colonne Sondage", assay_df.columns.tolist(), index=0)
        g = length_weighted_grade(assay_df.rename(columns={val_col: "Au_ppb", from_col: "From", to_col: "To", hole_col: "Sondage"}))
        if not g.empty:
            st.dataframe(g, use_container_width=True)
            fig = go.Figure(go.Bar(x=g["Sondage"], y=g["Teneur_moy_g_t"], marker_color="#B7950B"))
            fig.update_layout(title="Teneur moyenne pondérée par trou", yaxis_title="g/t (équiv.)", height=400)
            st.plotly_chart(fig, use_container_width=True)

    if not auger.empty and "Au_ppb" in auger.columns and auger["Au_ppb"].notna().any():
        st.markdown("#### Estimation à partir des données Auger/sols")
        g = length_weighted_grade(auger)
        st.dataframe(g, use_container_width=True)
        fig = go.Figure(go.Bar(x=g["Sondage"], y=g["Teneur_moy_g_t"], marker_color="#D4AC0D"))
        fig.update_layout(title="Teneur moyenne pondérée Au — Auger/sols", yaxis_title="g/t (équiv.)", height=400)
        st.plotly_chart(fig, use_container_width=True)
        best = g.sort_values("Teneur_moy_g_t", ascending=False).iloc[0]
        st.info(f"🧠 **Interprétation** : la teneur moyenne pondérée la plus élevée est observée en "
                f"**{best['Sondage']}** (~{best['Teneur_moy_g_t']:.3f} g/t équiv. sur {best['Longueur_totale_m']:.1f} m). "
                f"Ces valeurs Auger restent indicatives (échantillons de sol, pas de carotte) — elles orientent "
                f"le ciblage des forages RC/AC de confirmation en profondeur.")
    elif assay_df is None:
        st.info("Aucune donnée de teneur disponible pour l'instant (ni assays RC/AC/DD, ni Auger).")


elif page == "🪨 SGI & Structures":
    st.subheader("🪨 Indice de qualité du massif (GSI) & synthèse structurale")
    sdf = st.session_state.data["STRUCT"]
    auger = st.session_state.data["AUGER"]
    all_df = safe_concat(["RC", "AC", "DD"])

    tab_gsi, tab_struct_table = st.tabs(["🪨 Tableau GSI / SGI vs Minéralisation & teneur", "🧭 Tableau directions / pendages / sens de pendage"])

    with tab_gsi:
        st.write("Le **GSI (Geological Strength Index)** qualifie la qualité géomécanique du massif rocheux "
                 "(0 = très fracturé/altéré, 100 = roche massive intacte). On le croise ici avec la "
                 "minéralisation et la teneur en or pour identifier si les zones minéralisées correspondent "
                 "à des zones de faiblesse structurale (souvent le cas en contexte orogénique/orpaillage).")
        if sdf.empty or "GSI_auto" not in sdf.columns or sdf["GSI_auto"].dropna().empty:
            st.info("Aucune valeur de GSI renseignée dans le Log Structural (colonne GSI_auto). "
                    "Cette colonne existe dans votre gabarit mais n'est pas encore remplie sur le terrain.")
        else:
            gsi_tbl = sdf.groupby("Sondage").agg(
                GSI_moyen=("GSI_auto", "mean"), RQD_moyen=("RQD_auto", "mean") if "RQD_auto" in sdf.columns else ("GSI_auto", "count"),
                N_mesures=("GSI_auto", "count"),
            ).reset_index()
            if not all_df.empty and "Has_Mineralisation" in all_df.columns:
                min_pct = all_df.groupby("Sondage")["Has_Mineralisation"].mean().rename("Pct_mineralise") * 100
                gsi_tbl = gsi_tbl.merge(min_pct, on="Sondage", how="left")
            if not auger.empty and "Au_ppb" in auger.columns:
                au_max = auger.groupby("Sondage")["Au_ppb"].max().rename("Au_max_ppb")
                gsi_tbl = gsi_tbl.merge(au_max, left_on="Sondage", right_index=True, how="left")
            st.dataframe(gsi_tbl, use_container_width=True)

            if "Pct_mineralise" in gsi_tbl.columns and gsi_tbl["Pct_mineralise"].notna().any():
                fig = go.Figure(go.Scatter(x=gsi_tbl["GSI_moyen"], y=gsi_tbl["Pct_mineralise"], mode="markers+text",
                                            text=gsi_tbl["Sondage"], textposition="top center",
                                            marker=dict(size=12, color="#7B241C")))
                fig.update_layout(title="GSI moyen vs % d'intervalles minéralisés", xaxis_title="GSI moyen",
                                   yaxis_title="% intervalles minéralisés", height=450)
                st.plotly_chart(fig, use_container_width=True)
                corr = gsi_tbl[["GSI_moyen", "Pct_mineralise"]].dropna().corr().iloc[0, 1] if len(gsi_tbl.dropna(subset=["GSI_moyen", "Pct_mineralise"])) > 2 else None
                if corr is not None:
                    tendance = "négative (zones plus fracturées/altérées = plus minéralisées)" if corr < -0.2 else (
                        "positive (roche plus saine = plus minéralisée)" if corr > 0.2 else "faible / peu concluante")
                    st.info(f"🧠 **Interprétation** : corrélation GSI / % minéralisé ≈ **{corr:.2f}** — tendance "
                            f"{tendance}. " +
                            ("Cela suggère un contrôle structural de la minéralisation par les zones de "
                             "faiblesse/altération du massif." if corr < -0.2 else
                             "Une corrélation positive ou nulle suggère un contrôle plutôt lithologique/"
                             "géochimique que structural — à confirmer avec plus de données."))

    with tab_struct_table:
        if sdf.empty or "Azimut" not in sdf.columns or sdf["Azimut"].dropna().empty:
            st.info("Aucune donnée structurale chargée.")
        else:
            type_col = "OCTypes" if "OCTypes" in sdf.columns else None
            group_cols = ["Sondage"] + ([type_col] if type_col else [])
            summary = sdf.dropna(subset=["Azimut", "Pendage"]).groupby(group_cols).agg(
                Azimut_moyen=("Azimut", "mean"), Pendage_moyen=("Pendage", "mean"), N_mesures=("Azimut", "count"),
            ).reset_index()

            def dip_direction(az):
                sectors = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
                idx = int((az % 360) / 22.5 + 0.5) % 16
                return sectors[idx]
            summary["Sens_de_pendage"] = summary["Azimut_moyen"].apply(dip_direction)
            st.dataframe(summary, use_container_width=True)
            st.download_button("📥 Télécharger ce tableau (CSV)", summary.to_csv(index=False).encode("utf-8"),
                                "tableau_structures.csv", "text/csv")
            if type_col:
                dom_type = sdf[type_col].value_counts().idxmax() if sdf[type_col].notna().any() else "N/A"
                st.info(f"🧠 **Interprétation** : le type de structure dominant relevé est **{dom_type}**. "
                        f"L'azimut moyen global est de **{summary['Azimut_moyen'].mean():.0f}°** avec un "
                        f"pendage moyen de **{summary['Pendage_moyen'].mean():.0f}°**, sens de pendage "
                        f"principal vers le **{summary['Sens_de_pendage'].mode().iloc[0] if not summary['Sens_de_pendage'].mode().empty else 'N/A'}**. "
                        f"Cette cohérence (ou dispersion) directionnelle doit être comparée à l'orientation "
                        f"régionale connue du prospect pour identifier d'éventuelles familles structurales "
                        f"secondaires (réactivation, structures tardives).")

# ===========================================================================
# PAGE : GÉOPHYSIQUE
# ===========================================================================
elif page == "📡 Géophysique":
    st.subheader("📡 Géophysique")
    st.write("Chargez vos données géophysiques (grille ou points : Easting, Northing, et une colonne de "
             "valeur — magnétisme, polarisation induite/résistivité, radiométrie, etc.).")
    f_geop = st.file_uploader("Fichier géophysique (xlsx/csv)", type=["xlsx", "csv"], key="geop_up")
    if f_geop:
        geop_df = pd.read_csv(f_geop) if f_geop.name.endswith(".csv") else pd.read_excel(f_geop)
        st.dataframe(geop_df.head(30), use_container_width=True)
        cols = geop_df.columns.tolist()
        c1, c2, c3 = st.columns(3)
        with c1:
            xcol = st.selectbox("Colonne Easting", cols, index=0)
        with c2:
            ycol = st.selectbox("Colonne Northing", cols, index=min(1, len(cols) - 1))
        with c3:
            num_cols = geop_df.select_dtypes(include=[np.number]).columns.tolist()
            vcol = st.selectbox("Colonne de valeur (ex: magnétisme nT, résistivité Ω·m)", num_cols or cols)

        fig = go.Figure(go.Scatter(
            x=geop_df[xcol], y=geop_df[ycol], mode="markers",
            marker=dict(size=8, color=geop_df[vcol], colorscale="RdYlBu", reversescale=True, showscale=True,
                        colorbar=dict(title=vcol)),
        ))
        fig.add_annotation(x=0.97, y=0.97, xref="paper", yref="paper", showarrow=False, text="N ↑",
                            font=dict(size=18, color="black"))
        fig.update_layout(title=f"Carte géophysique — {vcol}", xaxis_title=xcol, yaxis_title=ycol,
                           height=650, yaxis=dict(scaleanchor="x", scaleratio=1))
        st.plotly_chart(fig, use_container_width=True)

        seuil_haut = geop_df[vcol].quantile(0.85)
        n_anom = (geop_df[vcol] >= seuil_haut).sum()
        st.info(f"🧠 **Interprétation** : {n_anom} point(s) dépassent le 85e percentile "
                f"(**{seuil_haut:.1f}**) de {vcol}. Ces zones d'anomalie géophysique sont à superposer à la "
                f"carte d'anomalie géochimique (onglet Auger) et à la carte structurale pour prioriser les "
                f"cibles de forage — la coïncidence de plusieurs signatures (géophysique + géochimie + "
                f"structure) renforce significativement la confiance dans une cible.")
    else:
        st.info("Aucun fichier géophysique chargé pour le moment. Une fois chargé, la carte et l'analyse "
                "d'anomalie se génèrent automatiquement.")

elif page == "📦 Ressources & Réserves (JORC simplifié)":
    st.subheader("📦 Estimation de ressources — méthode simplifiée (polygones d'influence)")
    st.warning("⚠️ **Avertissement** : ceci est un outil d'estimation **indicative et pédagogique**, pas un "
               "rapport de ressources conforme au code JORC/NI 43-101. Une estimation certifiable nécessite "
               "une Personne Qualifiée (Competent Person), un modèle géostatistique validé (variographie, "
               "krigeage) et un audit indépendant.")

    auger = st.session_state.data["AUGER"]
    all_df = safe_concat(["RC", "AC", "DD"])

    source = st.radio("Source des teneurs", ["Auger / sols (Au_ppb)", "Fichier d'assays externe"], horizontal=True)
    grade_df = pd.DataFrame()
    if source.startswith("Auger") and not auger.empty and "Au_ppb" in auger.columns:
        grade_df = length_weighted_grade(auger)
    elif source.startswith("Fichier"):
        f_assay2 = st.file_uploader("Fichier d'assays (Sondage, From, To, Au_ppm/ppb)", type=["xlsx", "csv"], key="jorc_assay")
        if f_assay2:
            adf = pd.read_csv(f_assay2) if f_assay2.name.endswith(".csv") else pd.read_excel(f_assay2)
            cols = adf.columns.tolist()
            c1, c2, c3, c4 = st.columns(4)
            hole_col = c1.selectbox("Sondage", cols, index=0, key="j_h")
            from_col = c2.selectbox("From", cols, index=min(1, len(cols) - 1), key="j_f")
            to_col = c3.selectbox("To", cols, index=min(2, len(cols) - 1), key="j_t")
            val_col = c4.selectbox("Teneur Au", cols, index=min(3, len(cols) - 1), key="j_v")
            grade_df = length_weighted_grade(adf.rename(columns={val_col: "Au_ppb", from_col: "From", to_col: "To", hole_col: "Sondage"}))

    if grade_df.empty:
        st.info("Aucune donnée de teneur disponible pour l'estimation. Chargez des données Auger ou un fichier d'assays.")
    else:
        st.markdown("#### Paramètres d'estimation")
        c1, c2, c3, c4 = st.columns(4)
        density = c1.number_input("Densité (t/m³)", 1.5, 4.5, 2.7, 0.1)
        influence_area = c2.number_input("Surface d'influence par trou (m²)", 100, 50000, 2500, 100,
                                          help="Ex: maille 50x50 m = 2500 m²")
        epaisseur = c3.number_input("Épaisseur moyenne du corps minéralisé (m)", 1.0, 200.0, 10.0, 1.0)
        cutoff = c4.number_input("Cut-off (g/t)", 0.0, 5.0, 0.3, 0.05)

        grade_df["Volume_m3"] = influence_area * epaisseur
        grade_df["Tonnage_t"] = grade_df["Volume_m3"] * density
        grade_df["Au_contenu_g"] = grade_df["Tonnage_t"] * grade_df["Teneur_moy_g_t"]
        grade_df["Au_contenu_oz"] = grade_df["Au_contenu_g"] / 31.1035
        grade_df["Classe_JORC"] = np.where(grade_df["Teneur_moy_g_t"] >= cutoff, "Inferré (indicatif)", "Sous cut-off — exclu")

        above = grade_df[grade_df["Teneur_moy_g_t"] >= cutoff]
        st.dataframe(grade_df, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("Trous au-dessus du cut-off", f"{len(above)} / {len(grade_df)}")
        c2.metric("Tonnage total estimé (au-dessus cut-off)", f"{above['Tonnage_t'].sum():,.0f} t".replace(",", " "))
        c3.metric("Or contenu estimé", f"{above['Au_contenu_oz'].sum():,.0f} oz".replace(",", " "))

        fig = go.Figure(go.Bar(x=above["Sondage"], y=above["Au_contenu_oz"], marker_color="#B7950B"))
        fig.update_layout(title="Or contenu estimé par trou (oz, indicatif)", height=400)
        st.plotly_chart(fig, use_container_width=True)

        st.info(f"🧠 **Interprétation** : sur la base d'une maille d'influence de {influence_area} m² et d'une "
                f"épaisseur moyenne de {epaisseur} m, le tonnage indicatif au-dessus du cut-off de {cutoff} g/t "
                f"est de **{above['Tonnage_t'].sum():,.0f} t** pour **{above['Au_contenu_oz'].sum():,.0f} oz** "
                f"d'or contenu (estimation non classée JORC — catégorie 'Inferré' à titre indicatif "
                f"uniquement). Cette estimation est très sensible aux hypothèses de maille et d'épaisseur : "
                f"resserrer le maillage de forage (infill) réduira l'incertitude et permettra d'évoluer vers "
                f"une catégorie Indiqué/Mesuré avec une étude géostatistique complète.")

elif page == "💵 Budget & Coûts":
    st.subheader("💵 Budget & Coûts détaillé")
    st.write("Tableau de budget éditable par catégorie. Ajoutez vos lignes (forage, analyses, logistique, "
             "main d'œuvre, équipements, etc.).")
    edited_budget = st.data_editor(st.session_state.budget, num_rows="dynamic", use_container_width=True,
                                    key="budget_editor")
    edited_budget["Cout_total"] = edited_budget["Quantite"].fillna(0) * edited_budget["Cout_unitaire"].fillna(0)
    st.session_state.budget = edited_budget

    st.dataframe(edited_budget[["Categorie", "Description", "Quantite", "Unite", "Cout_unitaire", "Cout_total", "Devise"]],
                 use_container_width=True)
    total = edited_budget["Cout_total"].sum()
    st.metric("💰 Coût total du programme", f"{total:,.0f}".replace(",", " ") + " " +
              (edited_budget["Devise"].mode().iloc[0] if not edited_budget["Devise"].mode().empty else "USD"))

    by_cat = edited_budget.groupby("Categorie")["Cout_total"].sum().reset_index().sort_values("Cout_total", ascending=False)
    if not by_cat.empty and by_cat["Cout_total"].sum() > 0:
        fig = go.Figure(go.Pie(labels=by_cat["Categorie"], values=by_cat["Cout_total"], hole=0.4))
        fig.update_layout(title="Répartition du budget par catégorie", height=450)
        st.plotly_chart(fig, use_container_width=True)
        top_cat = by_cat.iloc[0]
        st.info(f"🧠 **Interprétation** : la catégorie la plus coûteuse est **{top_cat['Categorie']}** "
                f"({top_cat['Cout_total'] / total * 100:.0f}% du budget total). Si cette part dépasse 50%, "
                f"envisager une revue des coûts unitaires ou un phasage du programme pour lisser la trésorerie.")
    else:
        st.info("Renseignez les quantités et coûts unitaires pour voir la répartition budgétaire.")

elif page == "🔗 Gestion des échantillons":
    st.subheader("🔗 Gestion des échantillons — Chain of Custody")
    st.write("Suivi de la chaîne de traçabilité des échantillons, du prélèvement terrain à la réception des "
             "résultats du laboratoire. Inclut les échantillons QAQC (blancs, duplicatas, standards).")

    edited_samples = st.data_editor(
        st.session_state.samples, num_rows="dynamic", use_container_width=True, key="samples_editor",
        column_config={
            "Type": st.column_config.SelectboxColumn(options=["RC", "AC", "DD", "Auger", "QAQC-Blanc", "QAQC-Duplicata", "QAQC-Standard"]),
            "Statut": st.column_config.SelectboxColumn(options=["Prélevé (terrain)", "En transit", "Reçu au labo", "Résultats reçus", "Rejeté/à reprendre"]),
            "QAQC": st.column_config.CheckboxColumn(),
        },
    )
    st.session_state.samples = edited_samples

    if not edited_samples.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total échantillons", len(edited_samples))
        c2.metric("Résultats reçus", int((edited_samples["Statut"] == "Résultats reçus").sum()))
        c3.metric("En attente labo", int(edited_samples["Statut"].isin(["En transit", "Reçu au labo"]).sum()))
        c4.metric("Échantillons QAQC", int(edited_samples["QAQC"].fillna(False).sum()) if "QAQC" in edited_samples.columns else 0)

        statut_counts = edited_samples["Statut"].value_counts()
        fig = go.Figure(go.Bar(x=statut_counts.index, y=statut_counts.values, marker_color="#1B4F72"))
        fig.update_layout(title="Échantillons par statut", height=350)
        st.plotly_chart(fig, use_container_width=True)

        pct_qaqc = edited_samples["QAQC"].fillna(False).mean() * 100 if "QAQC" in edited_samples.columns else 0
        rejected = (edited_samples["Statut"] == "Rejeté/à reprendre").sum()
        st.info(f"🧠 **Interprétation** : le taux d'échantillons QAQC est de **{pct_qaqc:.1f}%** "
                f"(la pratique standard recommande 5-10% minimum : blancs + duplicatas + standards). " +
                (f"⚠️ {rejected} échantillon(s) sont marqués 'Rejeté/à reprendre' — à traiter en priorité."
                 if rejected else "Aucun échantillon rejeté actuellement.") +
                " Un suivi rigoureux de la chaîne de traçabilité est essentiel pour la défendabilité future "
                "d'une estimation de ressources.")
    else:
        st.info("Tableau vide — ajoutez des échantillons pour démarrer le suivi.")

elif page == "⚗️ Métallurgie":
    st.subheader("⚗️ Métallurgie — essais de traitement")
    edited = st.data_editor(st.session_state.metallurgie, num_rows="dynamic", use_container_width=True, key="metal_editor")
    st.session_state.metallurgie = edited
    if not edited.empty and edited["Recuperation_pct"].notna().any():
        c1, c2 = st.columns(2)
        c1.metric("Récupération moyenne", f"{edited['Recuperation_pct'].mean():.1f} %")
        c2.metric("Nombre d'essais", len(edited))
        fig = go.Figure(go.Bar(x=edited["Test_ID"], y=edited["Recuperation_pct"], marker_color="#1ABC9C"))
        fig.update_layout(title="Récupération métallurgique par essai (%)", height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.info(f"🧠 **Interprétation** : la récupération moyenne des essais est de "
                f"**{edited['Recuperation_pct'].mean():.1f}%**. Une récupération <85% suggère souvent un "
                f"minerai réfractaire (sulfures encapsulés, carbone organique préempteur — 'preg-robbing') "
                f"nécessitant un test de caractérisation complémentaire avant choix du procédé "
                f"(CIL/CIP standard vs grillage/oxydation sous pression/bio-oxydation).")
    else:
        st.info("Tableau vide — ajoutez vos résultats d'essais métallurgiques (tête, récupération, résidu...).")

elif page == "🦺 Environnement & HSE":
    st.subheader("🦺 Environnement, Santé & Sécurité (HSE)")
    edited = st.data_editor(
        st.session_state.hse, num_rows="dynamic", use_container_width=True, key="hse_editor",
        column_config={
            "Type": st.column_config.SelectboxColumn(options=["Incident", "Quasi-accident", "Inspection", "Formation", "Environnement"]),
            "Gravite": st.column_config.SelectboxColumn(options=["Faible", "Modérée", "Élevée", "Critique"]),
            "Statut": st.column_config.SelectboxColumn(options=["Ouvert", "En cours", "Clôturé"]),
        },
    )
    st.session_state.hse = edited
    if not edited.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total événements", len(edited))
        c2.metric("Incidents critiques/élevés", int(edited["Gravite"].isin(["Élevée", "Critique"]).sum()))
        c3.metric("Ouverts / en cours", int(edited["Statut"].isin(["Ouvert", "En cours"]).sum()))
        fig = go.Figure(go.Bar(x=edited["Type"].value_counts().index, y=edited["Type"].value_counts().values,
                                marker_color="#C0392B"))
        fig.update_layout(title="Répartition des événements HSE", height=350)
        st.plotly_chart(fig, use_container_width=True)
        n_crit_open = int(((edited["Gravite"].isin(["Élevée", "Critique"])) & (edited["Statut"] != "Clôturé")).sum())
        st.info(f"🧠 **Interprétation** : **{n_crit_open}** événement(s) de gravité élevée/critique sont "
                f"encore ouverts — à traiter en priorité absolue avant de poursuivre les opérations dans "
                f"la zone concernée. Un suivi hebdomadaire du taux de clôture des actions correctives est "
                f"recommandé (indicateur LTIFR à calculer si les heures travaillées sont disponibles).")
    else:
        st.info("Aucun événement HSE enregistré. Ajoutez vos incidents, inspections et formations.")

elif page == "📜 SOP":
    st.subheader("📜 SOP — Procédures standard d'exploration minière")
    st.write("Bibliothèque de procédures standard. Modifiez le texte ou ajoutez vos propres procédures internes.")
    default_sops = {
        "Forage RC": "1. Vérifier l'alignement et la verticalité de la foreuse.\n2. Échantillonner tous les "
                     "1 m via riffle splitter.\n3. Logger chaque intervalle immédiatement (lithologie, "
                     "altération, minéralisation).\n4. Insérer un échantillon QAQC tous les 20 échantillons "
                     "(blanc/duplicata/standard en alternance).\n5. Sceller et étiqueter chaque sac avant "
                     "envoi au laboratoire.",
        "Forage Diamond Drilling (DD)": "1. Orienter la carotte dès la sortie du carottier.\n2. Mesurer le "
                     "taux de récupération et le RQD par run.\n3. Photographier chaque caisse avant logging.\n"
                     "4. Logger lithologie, structure (alpha/bêta), GSI, minéralisation.\n5. Couper la "
                     "carotte le long de l'axe de moindre dimension pour échantillonnage (1/2 ou 1/4 carotte).",
        "Logging géologique": "1. Toujours compléter From/To sans lacune ni chevauchement.\n2. Renseigner "
                     "systématiquement Code_Strat et Formation pour la classification d'altération météorique.\n"
                     "3. Documenter toute incertitude dans le champ Commentaire plutôt que de laisser un "
                     "champ vide ambigu.",
        "QAQC échantillonnage": "1. Insertion standard : 1 blanc + 1 duplicata + 1 standard certifié pour "
                     "20 échantillons.\n2. Vérifier les résultats de standards à réception (alerte si écart "
                     "> 2 écarts-types).\n3. Conserver les pulpes et rejets selon la politique de rétention "
                     "du projet.",
        "Sécurité site de forage": "1. Port des EPI obligatoire (casque, lunettes, chaussures de sécurité, "
                     "gants).\n2. Périmètre de sécurité autour de la foreuse.\n3. Briefing sécurité quotidien "
                     "avant démarrage des opérations.\n4. Procédure d'arrêt d'urgence affichée et connue de "
                     "toute l'équipe.",
    }
    for title, text in default_sops.items():
        with st.expander(f"📄 {title}"):
            st.text_area("Contenu", value=text, height=160, key=f"sop_{title}", label_visibility="collapsed")
    with st.expander("➕ Ajouter une nouvelle procédure"):
        new_title = st.text_input("Titre de la procédure")
        new_text = st.text_area("Contenu de la procédure", height=160)
        if st.button("Enregistrer cette procédure") and new_title:
            st.success(f"Procédure '{new_title}' enregistrée pour la session en cours.")

elif page == "🛡️ Admin":
    st.subheader("🛡️ Administration du projet minier")
    st.write("Suivi administratif : permis, autorisations, contrats, conformité réglementaire, échéances.")
    edited = st.data_editor(
        st.session_state.admin, num_rows="dynamic", use_container_width=True, key="admin_editor",
        column_config={
            "Categorie": st.column_config.SelectboxColumn(options=["Permis d'exploration", "Permis environnemental",
                                                                     "Autorisation de forage", "Contrat foncier",
                                                                     "Assurance", "Contrat sous-traitant", "Autre"]),
            "Statut": st.column_config.SelectboxColumn(options=["Valide", "À renouveler", "Expiré", "En cours de demande"]),
        },
    )
    st.session_state.admin = edited
    if not edited.empty:
        n_expire = int((edited["Statut"] == "Expiré").sum())
        n_renew = int((edited["Statut"] == "À renouveler").sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Total éléments suivis", len(edited))
        c2.metric("⚠️ Expirés", n_expire)
        c3.metric("🔔 À renouveler", n_renew)
        if n_expire or n_renew:
            st.warning(f"**{n_expire} élément(s) expiré(s)** et **{n_renew} à renouveler** — vérifiez la "
                       f"conformité réglementaire avant toute nouvelle campagne de terrain.")
        st.info("🧠 Un permis d'exploration expiré rend toute activité de forage illégale dans la juridiction "
                "concernée — traiter ce point avant tout engagement de budget terrain (voir onglet Budget).")
    else:
        st.info("Aucun élément administratif suivi pour l'instant.")

elif page == "🤖 Audit automatique des données":
    st.subheader("🤖 Audit automatique des données")
    st.write("Analyse l'ensemble des onglets de données chargées et détecte les anomalies "
             "(coordonnées manquantes, intervalles invalides, chevauchements, lacunes...).")

    if st.button("🔍 Lancer l'audit complet", type="primary"):
        all_issues = []
        for key, label in [("RC", "Log RC"), ("AC", "Log AC"), ("DD", "Log DD")]:
            all_issues += audit_dataframe(st.session_state.data[key], label)
        all_issues += audit_dataframe(st.session_state.data["AUGER"], "Auger/Géochimie", from_col="From", to_col="To")
        all_issues += audit_dataframe(st.session_state.data["STRUCT"], "Structural", from_col="From_m", to_col="To_m")
        st.session_state["_audit_results"] = all_issues

    issues = st.session_state.get("_audit_results")
    if issues is None:
        st.info("Cliquez sur 'Lancer l'audit complet' pour scanner toutes les données chargées.")
    elif not issues:
        st.success("✅ Aucune anomalie détectée dans les données actuellement chargées.")
    else:
        idf = pd.DataFrame(issues)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total anomalies", len(idf))
        c2.metric("🔴 Critiques", int((idf["severite"] == "🔴 Critique").sum()))
        c3.metric("⚠️ Erreurs", int((idf["severite"] == "⚠️ Erreur").sum()))
        sev_filter = st.multiselect("Filtrer par sévérité", idf["severite"].unique().tolist(),
                                     default=idf["severite"].unique().tolist())
        st.dataframe(idf[idf["severite"].isin(sev_filter)], use_container_width=True, height=400)

        st.markdown("#### 🛠️ Correction automatique (sûre)")
        st.caption("Corrige uniquement les problèmes strictement mécaniques : tri des intervalles par "
                   "From, inversion From/To si From>To, suppression des doublons exacts. **Aucune valeur "
                   "n'est inventée** — les champs manquants (coordonnées, lithologie) doivent toujours être "
                   "complétés manuellement à la source.")
        fix_target = st.selectbox("Jeu de données à corriger", ["RC", "AC", "DD", "AUGER"])
        if st.button("✅ Appliquer la correction automatique"):
            before = len(st.session_state.data[fix_target])
            st.session_state.data[fix_target] = auto_fix_dataframe(st.session_state.data[fix_target])
            after = len(st.session_state.data[fix_target])
            st.success(f"Correction appliquée sur {fix_target} : {before} → {after} lignes (tri + "
                       f"suppression doublons + correction From/To inversés). Relancez l'audit pour vérifier.")

        top_holes = idf[idf["trou"] != "Plusieurs"]["trou"].value_counts().head(5)
        if not top_holes.empty:
            st.info(f"🧠 **Interprétation** : les trous les plus problématiques sont "
                    f"{', '.join(top_holes.index.tolist())}. Corrigez-les en priorité avant toute "
                    f"interprétation de section ou estimation de ressources, car les chevauchements et "
                    f"intervalles invalides faussent directement les calculs de teneur pondérée.")

elif page == "📄 Rapport géologique":
    st.subheader("📄 Rapport géologique automatisé")
    st.write("Génère un rapport synthétique argumenté (résumé exécutif, contexte géologique, "
             "altération/minéralisation, structures, géochimie, recommandations) à partir de toutes "
             "les données actuellement chargées pour ce prospect.")

    if st.button("📝 Générer le rapport", type="primary"):
        sections = generate_geological_report(st.session_state.data, st.session_state.litho_colors, prospect, permis)
        st.session_state["_report_sections"] = sections

    sections = st.session_state.get("_report_sections")
    if not sections:
        st.info("Cliquez sur 'Générer le rapport' pour produire la synthèse.")
    else:
        for title, text in sections.items():
            st.markdown(f"### {title}")
            st.write(text)
        st.markdown("---")
        md_text = report_to_markdown(sections, prospect, permis)
        pdf_bytes = build_pdf_report(sections, prospect, permis)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("📥 Télécharger en Markdown (.md)", md_text.encode("utf-8"),
                                f"rapport_{prospect.replace(' ', '_')}.md", "text/markdown")
        with c2:
            st.download_button("📥 Télécharger en PDF", pdf_bytes,
                                f"rapport_{prospect.replace(' ', '_')}.pdf", "application/pdf",
                                key="dl_report_pdf")
        if st.button("💾 Archiver ce rapport dans l'onglet Documents"):
            st.session_state.documents.append({
                "Nom": f"Rapport_{prospect}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.pdf",
                "Type": "PDF", "Date": str(pd.Timestamp.now()), "Contenu": pdf_bytes,
            })
            st.success("Rapport archivé dans l'onglet 🗄️ Documents.")

# ===========================================================================
# PAGE : DOCUMENTS
# ===========================================================================
elif page == "🗄️ Documents":
    st.subheader("🗄️ Documents du prospect (images, PDF générés)")
    st.write("Tous les documents générés (rapports PDF) ou importés manuellement pour ce prospect.")

    f_doc = st.file_uploader("Ajouter un document (image ou PDF)", type=["png", "jpg", "jpeg", "pdf"], key="doc_up")
    if f_doc and st.button("➕ Ajouter ce document"):
        st.session_state.documents.append({
            "Nom": f_doc.name, "Type": f_doc.type, "Date": str(pd.Timestamp.now()), "Contenu": f_doc.read(),
        })
        st.success(f"'{f_doc.name}' ajouté.")

    docs = st.session_state.documents
    if not docs:
        st.info("Aucun document archivé. Générez un rapport (onglet Rapport géologique) ou ajoutez un fichier ci-dessus.")
    else:
        for i, d in enumerate(docs):
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.write(f"📄 **{d['Nom']}**")
            c2.caption(d["Date"][:19])
            c3.download_button("⬇️", d["Contenu"], d["Nom"], key=f"dl_doc_{i}")
        if st.button("🗑️ Vider la liste des documents"):
            st.session_state.documents = []
            st.rerun()

# ===========================================================================
# PAGE : COMMENTAIRES & RÉPONSES
# ===========================================================================
elif page == "💬 Commentaires & Réponses":
    st.subheader("💬 Commentaires & Réponses de l'équipe")
    st.write("Espace d'échange entre géologues sur les observations de terrain, interprétations, "
             "ou points à clarifier — par prospect.")

    with st.form("new_comment_form", clear_on_submit=True):
        auteur = st.text_input("Votre nom")
        texte = st.text_area("Commentaire")
        submitted = st.form_submit_button("➕ Publier")
        if submitted and texte:
            st.session_state.comments.append({
                "auteur": auteur or "Anonyme", "texte": texte, "date": str(pd.Timestamp.now()), "reponses": [],
            })
            st.rerun()

    if not st.session_state.comments:
        st.info("Aucun commentaire pour l'instant.")
    else:
        for i, c in enumerate(reversed(st.session_state.comments)):
            idx = len(st.session_state.comments) - 1 - i
            with st.container(border=True):
                st.markdown(f"**{c['auteur']}** — _{c['date'][:19]}_")
                st.write(c["texte"])
                for r in c.get("reponses", []):
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ **{r['auteur']}** — _{r['date'][:19]}_ : {r['texte']}")
                with st.expander("Répondre"):
                    r_auteur = st.text_input("Votre nom", key=f"r_auteur_{idx}")
                    r_texte = st.text_input("Réponse", key=f"r_texte_{idx}")
                    if st.button("Envoyer la réponse", key=f"r_send_{idx}") and r_texte:
                        st.session_state.comments[idx]["reponses"].append({
                            "auteur": r_auteur or "Anonyme", "texte": r_texte, "date": str(pd.Timestamp.now()),
                        })
                        st.rerun()

elif page == "📐 Sections par orientation de forage":
    st.subheader("📐 Sections géologiques par orientation de forage")
    st.write("Classement automatique des trous selon leur pendage (issu du Log Structural, sinon "
             "supposé vertical par défaut) : **subvertical** (≥75°), **incliné** (30°-75°), "
             "**slow drilling / subhorizontal** (<30°, corrélation lente).")

    drill_types = st.multiselect("Types de sondage", ["RC", "AC", "DD"], default=["RC", "AC", "DD"], key="orient_types")
    all_df = safe_concat(drill_types)
    sdf = st.session_state.data["STRUCT"]

    if all_df.empty:
        st.info("Aucune donnée chargée.")
    else:
        collars = collar_table(all_df).dropna(subset=["Easting", "Northing"])
        dip_map = {}
        az_map = {}
        for h in collars["Sondage"]:
            if not sdf.empty and "Azimut" in sdf.columns:
                hs = sdf[sdf["Sondage"] == h]
                if not hs.empty and hs["Pendage"].notna().any():
                    dip_map[h] = hs["Pendage"].mean()
                    az_map[h] = hs["Azimut"].mean()
                    continue
            dip_map[h] = 90.0  # vertical par défaut si non renseigné
            az_map[h] = 0.0

        collars["Pendage_moyen"] = collars["Sondage"].map(dip_map)
        collars["Azimut_moyen"] = collars["Sondage"].map(az_map)
        collars["Categorie"] = pd.cut(collars["Pendage_moyen"], bins=[-1, 30, 75, 91],
                                       labels=["Slow drilling / Subhorizontal", "Incliné", "Subvertical"])

        tab_incl, tab_subv, tab_slow = st.tabs(["📏 Inclinés (30°-75°)", "📐 Subverticaux (≥75°)",
                                                  "🐌 Slow drilling / Subhorizontaux (<30°)"])
        cat_tab_map = {"Incliné": tab_incl, "Subvertical": tab_subv, "Slow drilling / Subhorizontal": tab_slow}

        for cat_name, tab in cat_tab_map.items():
            with tab:
                cat_holes = collars[collars["Categorie"] == cat_name]
                if cat_holes.empty:
                    st.info(f"Aucun trou classé '{cat_name}' (selon le pendage moyen disponible).")
                    continue
                st.dataframe(cat_holes[["Sondage", "Drill_Type", "Pendage_moyen", "Azimut_moyen"]],
                             use_container_width=True)
                sel = st.multiselect("Trous à inclure dans la section", cat_holes["Sondage"].tolist(),
                                      default=cat_holes["Sondage"].tolist()[:min(5, len(cat_holes))],
                                      key=f"sel_{cat_name}")
                ech_v = st.slider("Exagération verticale", 0.5, 3.0, 1.0, 0.1, key=f"ech_{cat_name}")

                if sel:
                    sub_collars = cat_holes[cat_holes["Sondage"].isin(sel)]
                    # axe de section = régression simple des collars sélectionnés
                    if len(sub_collars) >= 2:
                        ex, ny = sub_collars["Easting"].values, sub_collars["Northing"].values
                        dx, dy = ex.max() - ex.min(), ny.max() - ny.min()
                        order = np.argsort(ex) if abs(dx) > abs(dy) else np.argsort(ny)
                        ref_e, ref_n = ex[order[0]], ny[order[0]]
                    else:
                        ref_e, ref_n = sub_collars["Easting"].iloc[0], sub_collars["Northing"].iloc[0]

                    fig = go.Figure()
                    for _, hrow in sub_collars.iterrows():
                        hole = hrow["Sondage"]
                        hdf = all_df[all_df["Sondage"] == hole].sort_values("From")
                        depth = hdf["To"].max() if hdf["To"].notna().any() else 50
                        traj = hole_trajectory(hrow["Easting"], hrow["Northing"], hrow["Elevation"],
                                                hrow["Azimut_moyen"], hrow["Pendage_moyen"], depth, n_points=60)
                        traj["Dist"] = np.sqrt((traj["Easting"] - ref_e) ** 2 + (traj["Northing"] - ref_n) ** 2)
                        traj["Elevation_exag"] = hrow["Elevation"] - (hrow["Elevation"] - traj["Elevation"]) * ech_v

                        for _, r in hdf.iterrows():
                            f, t = r.get("From"), r.get("To")
                            if pd.isna(f) or pd.isna(t):
                                continue
                            litho = r.get("Lithologie") or "Indéterminé"
                            color = st.session_state.litho_colors.get(litho, "#7F8C8D")
                            seg = traj[(traj["Depth"] >= f) & (traj["Depth"] <= t)]
                            if len(seg) < 2:
                                continue
                            fig.add_trace(go.Scatter(x=seg["Dist"], y=seg["Elevation_exag"], mode="lines",
                                                      line=dict(color=color, width=10), showlegend=False,
                                                      hovertemplate=f"<b>{hole}</b><br>{litho}<br>{f}-{t}m<extra></extra>"))
                        fig.add_annotation(x=traj["Dist"].iloc[0], y=hrow["Elevation"] + 5, text=f"<b>{hole}</b>",
                                            showarrow=False, font=dict(size=10))

                    fig.update_layout(
                        title=f"Section ({cat_name}) — {prospect}", height=650,
                        xaxis_title="Distance projetée (m)", yaxis_title=f"Élévation (m) — exag. x{ech_v}",
                        plot_bgcolor="#F8F9F9",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption("Trajectoire réelle calculée à partir de l'azimut/pendage moyen (désurvey "
                               "simplifié) — contrairement à la section verticale standard, ici la "
                               "courbure/inclinaison réelle du trou est représentée.")
                    st.info(f"🧠 **Interprétation** : {len(sel)} trou(s) {cat_name.lower()} sont représentés. " +
                            ("Les trous subhorizontaux/slow drilling permettent une corrélation latérale fine "
                             "des unités, utile pour suivre un horizon stratigraphique ou un niveau "
                             "minéralisé tabulaire sur de longues distances." if cat_name.startswith("Slow") else
                             "Les trous inclinés visent généralement à recouper des structures minéralisées "
                             "à fort pendage perpendiculairement à leur orientation, maximisant l'intersection "
                             "vraie." if cat_name == "Incliné" else
                             "Les trous subverticaux donnent une image directe de l'empilement stratigraphique "
                             "mais peuvent sous-échantillonner les structures à fort pendage parallèles au "
                             "forage."))

elif page == "🗃️ Base de données centrale":
    st.subheader("🗃️ Base de données centrale")
    st.write("Vue d'ensemble de **tous les prospects sauvegardés** dans le fichier local "
             "`smc_dashboard.db` (SQLite) — c'est ici que vivent réellement vos données entre deux "
             "sessions.")

    if st.button("🔄 Rafraîchir"):
        st.rerun()

    stats = db.db_stats()
    if not stats:
        st.info("Aucun prospect sauvegardé pour l'instant.")
    else:
        for s in stats:
            s["Nb_trous_RC_AC_DD"] = db.collar_count(s["Prospect"])
            s["Taille_Ko"] = round(s["Taille_octets"] / 1024, 1)
        sdf_db = pd.DataFrame(stats)[["Prospect", "Nb_trous_RC_AC_DD", "Taille_Ko", "Derniere_sauvegarde"]]
        st.dataframe(sdf_db, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("Prospects enregistrés", len(stats))
        c2.metric("Total trous (tous prospects)", int(sdf_db["Nb_trous_RC_AC_DD"].sum()))
        c3.metric("Taille totale base", f"{sdf_db['Taille_Ko'].sum():.0f} Ko")

        fig = go.Figure(go.Bar(x=sdf_db["Prospect"], y=sdf_db["Nb_trous_RC_AC_DD"], marker_color="#1B4F72"))
        fig.update_layout(title="Nombre de trous par prospect", height=350)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 💾 Sauvegarde / Restauration complète")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Télécharger une copie de sauvegarde** de toute la base (tous prospects inclus).")
        db_bytes = db.get_db_file_bytes()
        st.download_button("📥 Télécharger smc_dashboard.db", db_bytes, "smc_dashboard_backup.db",
                            "application/octet-stream", disabled=(len(db_bytes) == 0))
    with col2:
        st.write("**Restaurer** depuis un fichier .db précédemment téléchargé (⚠️ remplace toute la base actuelle).")
        f_restore = st.file_uploader("Fichier .db à restaurer", type=["db"], key="db_restore_up")
        if f_restore and st.button("⚠️ Restaurer (remplace tout)"):
            db.restore_db_file(f_restore.read())
            st.success("Base restaurée. Rechargement...")
            _load_project(st.session_state.active_project if st.session_state.active_project in db.list_projects() else db.list_projects()[0])
            st.rerun()

    st.info("🧠 **Pourquoi cet onglet ?** La persistance fonctionne déjà automatiquement en arrière-plan "
            "(chaque action sauvegarde le prospect actif). Cet onglet la rend simplement **visible et "
            "manipulable** : vérifier ce qui est stocké, exporter une copie de sécurité régulièrement "
            "(recommandé avant tout redéploiement sur un hébergement cloud éphémère), ou restaurer une "
            "sauvegarde antérieure en cas de problème.")

elif page == "📊 Synthèse / Collars":


    st.subheader("📊 Synthèse des collars et statistiques")
    all_df = safe_concat(["RC", "AC", "DD"])
    if all_df.empty:
        st.info("Aucune donnée chargée.")
    else:
        collars = collar_table(all_df)
        st.dataframe(collars, use_container_width=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total trous", collars["Sondage"].nunique())
        c2.metric("Mètres forés (cumul)", f"{collars['Profondeur_totale'].sum():.0f} m" if "Profondeur_totale" in collars else "N/A")
        c3.metric("Trous minéralisés", int(all_df.groupby('Sondage')['Has_Mineralisation'].any().sum()) if "Has_Mineralisation" in all_df.columns else 0)

        if not collars.empty and collars["Easting"].notna().any():
            fig = go.Figure(go.Scatter(x=collars["Easting"], y=collars["Northing"], mode="markers+text",
                                        text=collars["Sondage"], textposition="top center",
                                        marker=dict(size=10, color=collars.get("Profondeur_totale", 50),
                                                    colorscale="Viridis", showscale=True,
                                                    colorbar=dict(title="Profondeur (m)"))))
            fig.update_layout(title="Plan de collars", xaxis_title="Easting", yaxis_title="Northing",
                               height=600, yaxis=dict(scaleanchor="x", scaleratio=1))
            st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
_save_active_to_db()
st.caption(f"ESPACE VIRTUELLE MINIÈRE DE SMC — Prospect actif : **{prospect}** "
           f"(sauvegarde automatique locale via SQLite). 24+ modules : sections, cartes, 3D, "
           f"planification, SGI, géochimie/pXRF, ressources JORC simplifié, budget, HSE, rapport "
           f"automatisé, etc.")
