import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime
from io import BytesIO
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Sellams Edimo Fashion", page_icon="📊", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# DONNÉES STATIQUES (mode cloud + local)
# ============================================================
DONNEES = {
    'ca_total': 236374825, 'produits': 1649, 'fournisseurs': 13,
    'stock': 50118994, 'factures': 4441,
    'ca_boutiques': {'GRAND MALL - DOUALA': 154299827, 'DJEUGA PALACE - YAOUNDE': 73786498},
    'panier_douala': 69500, 'panier_yaounde': 137000,
    'ca_mensuel': {
        '2023': [0,0,0,0,7525600,7221800,9690200,7559800,13037600,6087400,8959500,9721000],
        '2024': [76059100,7418700,2327000,1242500,2027400,8055200,3484800,5660000,4175101,2929600,4258000,6327500],
        '2025': [2361645,4481183,3752000,6935000,3064000,3061000,2376000,2656000,1195000,1727898,790000,5902998],
        '2026': [3060300,478000,308000,458000,0,0,0,0,0,0,0,0],
    },
    'top_fournisseurs': [
        ('GLOBAL', 1506386329), ('INTERNE', 365346647), ('ONE ALL SPORT', 188655793),
        ('AUTRE', 77707783), ('ATELIER COUTURE EDIMO', 61706995), ('DUBAI', 16843780),
        ('BANTU INTERNATIONAL GROUP', 6843281), ('ZOLEKO', 6380500)
    ],
    'stock_magasins': [
        ('Magasin Djeuga Palace - Yaounde', 35882830, 298),
        ('Magasin Boutique Grand Mall Douala', 11719500, 5124),
        ('Magasin de stockage de produits finis', 1319001, 17),
        ('Magasin de stockage de matiere premiere', 1197663, 25234)
    ],
    'ventes_categories': [
        ('COMMANDE CLIENT', 16992653), ('CAMEROONIAN MAMA', 6728150),
        ('BOUBOU HAUT DE GAMME', 7793000), ('AUTRE', 5010514),
        ('CAMEROONIAN DJARABI', 4050000), ('CHEMISE LIN', 3580180),
        ('CAMEROONIAN ABROAD', 2888744), ('CHEMISES AFRICAINES', 1848704),
        ('ENSEMBLE LIN FEMME', 1560000), ('CHEMISE', 1231000)
    ],
    'top_produits': [
        ('MAILLOT OFFICIEL - VERT - L', 29735000, 1446),
        ('MAILLOT OFFICIEL - VERT - XL', 25395000, 1214),
        ('MAILLOT OFFICIEL - VERT - M', 23615000, 1136),
        ('MAILLOT OFFICIEL - VERT - S', 11540000, 560),
        ('FRAIS CONFECTION VETEMENT + MAIN D\'OEUVRE', 4965514, 31),
        ('CASQUETTE ONE FECAFOOT', 2770000, 187),
        ('MAILLOT OFFICIEL - VERT - XXL', 2020000, 77),
        ('MAILLOT OFFICIEL - ROUGE - L', 1970000, 84),
        ('SUNU-CAMEROON BAS DE GAMME 2XL', 1859000, 11),
        ('MAILLOT OFFICIEL - ROUGE - S', 1710000, 79)
    ],
    'predictions': {
        'dates': ['2026-05','2026-06','2026-07','2026-08','2026-09','2026-10'],
        'valeurs': [4896628, 4479739, 4062850, 3645960, 3229071, 2812182],
    },
    'productions_mensuelles': [
        ('2025-08', 25, 6), ('2025-09', 5, 5), ('2025-10', 34, 30),
        ('2025-11', 64, 63), ('2025-12', 23, 23), ('2026-01', 27, 7),
        ('2026-02', 43, 39), ('2026-03', 5, 4), ('2026-04', 1, 1)
    ],
    'couleurs': {'BLEU':170,'NOIR':151,'BLANC':142,'VERT':96,'GRIS':74,'ROUGE':61,'JAUNE':57,'ROSE':47,'MARRON':43,'ORANGE':34,'CIEL':32,'BEIGE':27,'BORDEAU':26,'VIOLET':21,'OLIVE':11},
    'tissus': {'LIN':358,'TISSU':174,'SOIE':70,'DOUBLURE':46,'PAGNE':43,'BOUTON':41,'COTON':37,'FERMETURE':35,'BROKA':34,'BRODERIE':25},
    'tailles': {'TU':253,'XL':170,'S':157,'T.42':71,'T.44':58,'T.46':31,'T.48':28,'T.U':22,'ENFANT':15,'3XL':14},
}

mois_noms = ['Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre']

# ============================================================
# FONCTIONS DE DONNÉES
# ============================================================
@st.cache_data(ttl=3600)
def get_kpi():
    return (DONNEES['ca_total'], DONNEES['produits'], DONNEES['fournisseurs'], DONNEES['stock'], DONNEES['factures'])

def get_ventes_mensuelles():
    data = []
    for annee, ca_mois in DONNEES['ca_mensuel'].items():
        for i, ca in enumerate(ca_mois):
            if ca > 0:
                for boutique in DONNEES['ca_boutiques']:
                    ratio = DONNEES['ca_boutiques'][boutique] / DONNEES['ca_total']
                    data.append({'annee': int(annee), 'mois': i+1, 'boutique': boutique, 'ca': ca*ratio, 'nb_factures': max(1, int(ca*ratio/50000)), 'articles': max(1, int(ca*ratio/30000))})
    return pd.DataFrame(data)

@st.cache_data(ttl=3600)
def get_predictions():
    return (DONNEES['predictions']['dates'], DONNEES['predictions']['valeurs'], sum(DONNEES['predictions']['valeurs']), -416889)

def get_productions_detail():
    data = []
    for mois, qte, nb in DONNEES['productions_mensuelles']:
        data.append({'date_production': pd.Timestamp(f"{mois}-01"), 'quantite': qte, 'produit': f'Production {mois}', 'magasin': 'Atelier Couture', 'valide': 1, 'REF_PRODUCTION': f'PROD-{mois}'})
    return pd.DataFrame(data)

def telecharger_pdf(fig):
    buffer = BytesIO()
    fig.write_image(buffer, format="pdf")
    buffer.seek(0)
    return buffer

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.title("🏢 SELLAMS EDIMO")
    st.caption("Portail d'Analyse Stratégique")
    st.divider()
    st.subheader("🔍 Filtres")
    df_ventes = get_ventes_mensuelles()
    annees_dispo = sorted(df_ventes['annee'].unique())
    filtre_annee = st.selectbox("📅 Année", ["Toutes"] + [str(a) for a in annees_dispo])
    filtre_mois = st.selectbox("📆 Mois", ["Tous"] + mois_noms)
    st.divider()
    page = st.radio("📋 Navigation", ["🏠 Accueil", "📊 Analyses Ciblées", "📈 Galerie Graphiques", "📁 Exports & Rapports", "🔮 Prédictions", "🧵 Tissus & Caractéristiques"])
    st.divider()
    st.caption(f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    st.caption("© 2026 Sellams Edimo Fashion")

# Appliquer filtres
if filtre_annee != "Toutes":
    df_ventes_filtre = df_ventes[df_ventes['annee'] == int(filtre_annee)]
else:
    df_ventes_filtre = df_ventes.copy()
if filtre_mois != "Tous":
    mois_num = mois_noms.index(filtre_mois) + 1
    df_ventes_filtre = df_ventes_filtre[df_ventes_filtre['mois'] == mois_num]

# ============================================================
# KPI
# ============================================================
ca, produits, fournisseurs, stock, factures = get_kpi()
future_dates, predictions, total_6m, tendance_coeff = get_predictions()
ca_filtre = df_ventes_filtre['ca'].sum()
factures_filtre = df_ventes_filtre['nb_factures'].sum()

cols = st.columns(6)
cols[0].metric("💰 CA Total", f"{ca/1e6:.1f}M")
cols[1].metric("📦 Stock", f"{stock/1e6:.1f}M")
cols[2].metric("🏷️ Produits", f"{produits:,}")
cols[3].metric("🔮 Prévision 6M", f"{total_6m/1e6:.1f}M")
cols[4].metric("📅 CA Filtré", f"{ca_filtre/1e6:.1f}M")
cols[5].metric("🧾 Factures", f"{factures_filtre:,}")
st.divider()

# ============================================================
# ACCUEIL
# ============================================================
if page == "🏠 Accueil":
    st.header("🏠 Tableau de Bord Général")
    col1, col2, col3 = st.columns(3)
    col1.metric("📊 Marge Globale", "82,3%", delta="Excellente")
    col2.metric("🏪 Boutiques", "2", delta="Douala + Yaoundé")
    col3.metric("🗄️ Tables BDD", "109", delta="Analysées")
    
    st.subheader("📈 Comparaison CA Mensuel par Année")
    df_pivot = df_ventes.groupby(['annee','mois'])['ca'].sum().reset_index()
    fig = go.Figure()
    couleurs = {2023:'#3498DB', 2024:'#E74C3C', 2025:'#2ECC71', 2026:'#F39C12'}
    for annee in sorted(df_pivot['annee'].unique()):
        data = df_pivot[df_pivot['annee']==annee]
        fig.add_trace(go.Scatter(x=[mois_noms[m-1] for m in data['mois']], y=data['ca']/1e6, mode='lines+markers', name=str(annee), line=dict(width=3, color=couleurs.get(annee, '#95A5A6')), marker=dict(size=8)))
    fig.update_layout(title='Comparaison CA Mensuel', yaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=450, hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("🔮 Prévisions 6 Mois")
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=future_dates, y=[p/1e6 for p in predictions], marker_color=['#E74C3C' if p>5e6 else '#4ECDC4' for p in predictions], text=[f"{p/1e6:.1f}M" for p in predictions], textposition='outside'))
    fig2.update_layout(title='Prévisions CA', yaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=350)
    st.plotly_chart(fig2, use_container_width=True)

# ============================================================
# ANALYSES CIBLEES
# ============================================================
elif page == "📊 Analyses Ciblées":
    st.header("📊 Analyses Ciblées")
    tabs = st.tabs(["🏭 Fournisseurs", "📦 Stocks", "💰 Ventes", "🏪 Boutiques", "🏭 Production"])
    
    with tabs[0]:
        st.subheader("🏭 Fournisseurs")
        fig = go.Figure()
        noms = [f[0] for f in DONNEES['top_fournisseurs']]
        vals = [f[1] for f in DONNEES['top_fournisseurs']]
        fig.add_trace(go.Bar(y=noms, x=[v/1e6 for v in vals], orientation='h', marker_color='#E17055', text=[f"{v/1e6:.1f}M" for v in vals], textposition='outside'))
        fig.update_layout(title='Achats par Fournisseur', xaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.warning("⚠️ **RECO :** GLOBAL = 65% des achats. Diversifier avec ATELIER COUTURE EDIMO.")
    
    with tabs[1]:
        st.subheader("📦 Stocks")
        fig = make_subplots(rows=1, cols=2, specs=[[{'type':'pie'}, {'type':'bar'}]])
        noms_mag = [s[0] for s in DONNEES['stock_magasins']]
        vals_mag = [s[1] for s in DONNEES['stock_magasins']]
        fig.add_trace(go.Pie(labels=noms_mag, values=[v/1e6 for v in vals_mag], hole=0.4), row=1, col=1)
        fig.add_trace(go.Bar(x=[n[:20] for n in noms_mag], y=[v/1e6 for v in vals_mag], marker_color=['#FDCB6E','#00B894','#E17055','#6C5CE7'], text=[f'{v/1e6:.1f}M' for v in vals_mag], textposition='outside'), row=1, col=2)
        fig.update_layout(height=400, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
        st.warning("⚠️ **RECO :** 10 produits dormants (~5,2M FCFA). Organiser vente flash -30%.")
    
    with tabs[2]:
        st.subheader("💰 Ventes par Catégorie")
        top_n = st.slider("Top N", 5, 10, 10, key="ventes_n")
        cats = [v[0] for v in DONNEES['ventes_categories'][:top_n]]
        vals_c = [v[1] for v in DONNEES['ventes_categories'][:top_n]]
        fig = go.Figure()
        fig.add_trace(go.Bar(y=cats, x=[v/1e6 for v in vals_c], orientation='h', marker_color='#3498DB', text=[f"{v/1e6:.1f}M" for v in vals_c], textposition='outside'))
        fig.update_layout(title=f'Top {top_n} Catégories', xaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.info("💡 **RECO :** Pic Janvier (27M) et Décembre (7M). Renforcer stocks dès Octobre.")
    
    with tabs[3]:
        st.subheader("🏪 Boutiques")
        col1, col2 = st.columns(2)
        col1.metric("🏬 Grand Mall Douala", "154,3M FCFA", "65,3%")
        col1.metric("🛒 Panier Moyen", "69 500 FCFA")
        col2.metric("🏬 Djeuga Palace Yaoundé", "73,8M FCFA", "31,2%")
        col2.metric("🛒 Panier Moyen", "137 000 FCFA")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=['Grand Mall Douala','Djeuga Palace Yaoundé'], y=[154.3,73.8], marker_color=['#FF6B6B','#4ECDC4'], text=['154,3M','73,8M'], textposition='outside'))
        fig.update_layout(title='CA par Boutique (MFCFA)', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=350)
        st.plotly_chart(fig, use_container_width=True)
        st.info("💡 **RECO :** Yaoundé panier 2x supérieur. Dupliquer pratiques à Douala.")
    
    with tabs[4]:
        st.subheader("🏭 Production")
        prods = DONNEES['productions_mensuelles']
        fig = go.Figure()
        fig.add_trace(go.Bar(x=[p[0] for p in prods], y=[p[1] for p in prods], name='Quantité', marker_color='#6C5CE7'))
        fig.add_trace(go.Scatter(x=[p[0] for p in prods], y=[p[2] for p in prods], name='Nb Productions', mode='lines+markers', yaxis='y2', line=dict(color='#E74C3C', width=3)))
        fig.update_layout(title='Production Mensuelle', yaxis=dict(title='Quantité'), yaxis2=dict(title='Nb Productions', overlaying='y', side='right'), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400, hovermode='x unified', legend=dict(x=0.01, y=0.99))
        st.plotly_chart(fig, use_container_width=True)
        st.info("💡 **RECO :** Production concentrée sur ensembles/chemises. Automatiser suivi matières premières.")

# ============================================================
# GALERIE GRAPHIQUES
# ============================================================
elif page == "📈 Galerie Graphiques":
    st.header("📈 Galerie de Graphiques Interactifs")
    
    for i, (titre, col1_content, col2_content) in enumerate([
        ("1. Évolution du CA Mensuel",
         lambda: (fig := go.Figure(), [fig.add_trace(go.Scatter(x=[mois_noms[m-1] for m in data['mois']], y=data['ca']/1e6, mode='lines+markers', name=str(annee), line=dict(width=2.5))) for annee, data in [(annee, df_ventes[df_ventes['annee']==annee].groupby('mois')['ca'].sum().reset_index()) for annee in sorted(df_ventes['annee'].unique())]], fig.update_layout(title='CA Mensuel par Année', yaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400), fig)[-1],
         "**Pic Janvier 2024** : 76M (anormal). Tendance baisse depuis 2024. Janvier/Décembre = pics. **RECO :** Vérifier pic 2024."),
        
        ("2. Répartition CA par Boutique",
         lambda: (fig := make_subplots(rows=1, cols=2, specs=[[{'type':'pie'},{'type':'bar'}]]), fig.add_trace(go.Pie(labels=list(DONNEES['ca_boutiques'].keys()), values=[v/1e6 for v in DONNEES['ca_boutiques'].values()], hole=0.4), row=1, col=1), fig.add_trace(go.Bar(x=list(DONNEES['ca_boutiques'].keys()), y=[v/1e6 for v in DONNEES['ca_boutiques'].values()], marker_color=['#FF6B6B','#4ECDC4'], text=[f'{v/1e6:.1f}M' for v in DONNEES['ca_boutiques'].values()], textposition='outside'), row=1, col=2), fig.update_layout(height=400, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'), fig)[-1],
         "**Douala** : 65,3% (volume). **Yaoundé** : 31,2% (valeur unitaire +élevée). Panier Yaoundé 2x Douala. **RECO :** Former Douala au premium."),
        
        ("3. Top 10 Produits",
         lambda: (fig := go.Figure(), fig.add_trace(go.Bar(y=[p[0][:40] for p in DONNEES['top_produits']], x=[p[1]/1e6 for p in DONNEES['top_produits']], orientation='h', marker_color='#6C5CE7', text=[f"{p[1]/1e6:.1f}M" for p in DONNEES['top_produits']], textposition='outside')), fig.update_layout(title='Top 10 Produits', xaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400), fig)[-1],
         "**Maillots FECAFOOT** dominent. Produits mode faible en CA. **RECO :** Développer ligne mode (marges +élevées)."),
        
        ("4. Stock par Magasin",
         lambda: (fig := go.Figure(), fig.add_trace(go.Bar(x=[s[0][:30] for s in DONNEES['stock_magasins']], y=[s[1]/1e6 for s in DONNEES['stock_magasins']], marker_color=['#FDCB6E','#00B894','#E17055','#6C5CE7'], text=[f'{s[1]/1e6:.1f}M' for s in DONNEES['stock_magasins']], textposition='outside')), fig.update_layout(title='Stock par Magasin', yaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=350), fig)[-1],
         "**Djeuga Palace** : 35,9M (72%). **Grand Mall** : 11,7M. **RECO :** Rééquilibrer stock entre boutiques."),
        
        ("5. Top Fournisseurs",
         lambda: (fig := go.Figure(), fig.add_trace(go.Bar(y=[f[0] for f in DONNEES['top_fournisseurs']], x=[f[1]/1e6 for f in DONNEES['top_fournisseurs']], orientation='h', marker_color='#E17055', text=[f"{f[1]/1e6:.1f}M" for f in DONNEES['top_fournisseurs']], textposition='outside')), fig.update_layout(title='Top Fournisseurs', xaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400), fig)[-1],
         "**GLOBAL** = 65% des achats. Risque dépendance. **RECO URGENTE :** Diversifier. Objectif GLOBAL < 40%."),
        
        ("6. Saisonnalité",
         lambda: (df_m := df_ventes.groupby('mois')['ca'].mean().reset_index(), fig := go.Figure(), colors_s := ['#E74C3C' if v>df_m['ca'].mean() else '#3498DB' for v in df_m['ca']], fig.add_trace(go.Bar(x=[mois_noms[int(m)-1] for m in df_m['mois']], y=df_m['ca']/1e6, marker_color=colors_s, text=[f'{v/1e6:.1f}M' for v in df_m['ca']], textposition='outside')), fig.add_hline(y=df_m['ca'].mean()/1e6, line_dash='dash', line_color='gray'), fig.update_layout(title='CA Moyen par Mois', yaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400), fig)[-1],
         "**Haute saison** : Janvier (27M), Décembre. **Basse** : Mars-Avril (2-3M). Écart x10. **RECO :** Promotions Mars-Avril.")
    ]):
        with st.expander(titre, expanded=(i==0)):
            col1, col2 = st.columns([2, 1])
            with col1:
                try:
                    fig_result = col1_content()
                    if fig_result is not None:
                        st.plotly_chart(fig_result, use_container_width=True)
                except Exception as e:
                    st.error(f"Erreur graphique: {e}")
            with col2:
                st.markdown("### 📋 Analyse")
                st.markdown(col2_content)

# ============================================================
# EXPORTS
# ============================================================
elif page == "📁 Exports & Rapports":
    st.header("📁 Exports & Rapports")
    tab_exports = st.tabs(["📊 Excel", "📄 PDF", "📋 CSV"])
    
    with tab_exports[0]:
        st.subheader("📊 Exports Excel")
        exports_path = os.path.join(BASE_DIR, "04_exports")
        if os.path.exists(exports_path):
            for f in sorted(os.listdir(exports_path)):
                if f.endswith('.xlsx'):
                    with open(os.path.join(exports_path, f), 'rb') as file:
                        st.download_button(f"⬇ {f}", file, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        else:
            st.info("Exports Excel disponibles uniquement en local.")
    
    with tab_exports[1]:
        st.subheader("📄 Export PDF")
        fig_pdf = go.Figure()
        df_pivot = df_ventes.groupby(['annee','mois'])['ca'].sum().reset_index()
        for annee in sorted(df_pivot['annee'].unique()):
            data = df_pivot[df_pivot['annee']==annee]
            fig_pdf.add_trace(go.Scatter(x=[mois_noms[m-1] for m in data['mois']], y=data['ca']/1e6, mode='lines+markers', name=str(annee)))
        fig_pdf.update_layout(title='CA Mensuel Comparatif', yaxis_title='Millions FCFA')
        buf = BytesIO()
        fig_pdf.write_image(buf, format='pdf', width=1200, height=600)
        buf.seek(0)
        st.download_button("⬇ Télécharger CA Comparatif (PDF)", buf, "CA_Comparatif.pdf", "application/pdf")
    
    with tab_exports[2]:
        st.subheader("📋 CSV Prédictions")
        pred_path = os.path.join(BASE_DIR, "06_predictions")
        if os.path.exists(pred_path):
            for f in sorted(os.listdir(pred_path)):
                if f.endswith('.csv'):
                    with open(os.path.join(pred_path, f), 'rb') as file:
                        st.download_button(f"⬇ {f}", file, f, 'text/csv')
        else:
            st.info("Fichiers CSV disponibles uniquement en local.")

# ============================================================
# PRÉDICTIONS
# ============================================================
elif page == "🔮 Prédictions":
    st.header("🔮 Prédictions de Ventes")
    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(pd.DataFrame({'Mois':future_dates, 'Prévision':[f"{p:,.0f} FCFA" for p in predictions], 'Niveau':['🔴 Élevé' if p>5e6 else ('🟠 Moyen' if p>2e6 else '🟢 Faible') for p in predictions]}), use_container_width=True, hide_index=True)
        st.metric("💰 Total 6 Mois", f"{total_6m:,.0f} FCFA")
    with col2:
        fig = go.Figure()
        fig.add_trace(go.Bar(y=future_dates, x=[p/1e6 for p in predictions], orientation='h', marker_color=['#E74C3C' if p>5e6 else '#4ECDC4' for p in predictions], text=[f'{p/1e6:.1f}M' for p in predictions], textposition='outside'))
        fig.update_layout(title='Prévisions CA', xaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
        st.plotly_chart(fig, use_container_width=True)
    st.info("💡 **Méthodologie :** 3 méthodes combinées (Tendance + Saisonnalité + Holt-Winters). Données 2023-2024.")

# ============================================================
# TISSUS
# ============================================================
elif page == "🧵 Tissus & Caractéristiques":
    st.header("🧵 Analyse Tissus & Caractéristiques")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🧵 Matières", "779"); col2.metric("🌿 LIN", "358"); col3.metric("🎨 Couleurs", "18"); col4.metric("🧶 Tissus", "15")
    
    tab1, tab2, tab3 = st.tabs(["🎨 Couleurs", "🧵 Tissus", "📏 Tailles"])
    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=list(DONNEES['couleurs'].keys()), y=list(DONNEES['couleurs'].values()), marker_color=['#3498DB','#2C3E50','#ECF0F1','#2ECC71','#95A5A6','#E74C3C','#F1C40F','#FD79A8','#795548','#E67E22','#87CEEB','#D4C5A9','#C0392B','#9B59B6','#808000'], text=list(DONNEES['couleurs'].values()), textposition='outside'))
        fig.update_layout(title='Palette de Couleurs', yaxis_title='Nb Produits', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=450)
        st.plotly_chart(fig, use_container_width=True)
        st.info("💡 **RECO :** BLEU, NOIR, BLANC = 46%. Développer collection ROUGE/JAUNE pour l'été.")
    with tab2:
        fig = go.Figure()
        fig.add_trace(go.Bar(y=list(DONNEES['tissus'].keys()), x=list(DONNEES['tissus'].values()), orientation='h', marker_color='#E17055', text=list(DONNEES['tissus'].values()), textposition='outside'))
        fig.update_layout(title='Occurrences Tissus', xaxis_title='Nb Produits', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.info("💡 **RECO :** LIN dominant (358). Sécuriser 2-3 fournisseurs LIN.")
    with tab3:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=list(DONNEES['tailles'].keys()), y=list(DONNEES['tailles'].values()), marker_color='#6C5CE7', text=list(DONNEES['tailles'].values()), textposition='outside'))
        fig.update_layout(title='Distribution des Tailles', yaxis_title='Nb Produits', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.info("💡 **RECO :** 253 produits Taille Unique. Développer gamme 3XL+ et enfants.")

st.divider()
st.caption("© 2026 Sellams Edimo Fashion - Portail d'Analyse Stratégique • CONFIDENTIEL")