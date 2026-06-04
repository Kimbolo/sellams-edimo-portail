import streamlit as st
import pymysql
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime
import warnings
import base64
from io import BytesIO
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Sellams Edimo Fashion", page_icon="", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GRAPHIQUES_PATH = os.path.join(BASE_DIR, "03_graphiques")

DB_CONFIG = {
    'host': '127.0.0.1', 'user': 'root', 'password': '',
    'database': 'sellams_edimofashion', 'connect_timeout': 10
}

# ============================================================
# FONCTIONS CACHEES
# ============================================================
@st.cache_data(ttl=300)
def get_kpi():
    conn = pymysql.connect(**DB_CONFIG)
    ca = pd.read_sql("SELECT SUM(lf.QUANTITE*lf.PRIX_UNITAIRE) as c FROM facturec f JOIN ligne_facturec lf ON f.ID_FACTURE=lf.ID_FACTURE WHERE f.STATUT=1", conn)['c'][0] or 0
    produits = pd.read_sql("SELECT COUNT(*) as n FROM produit WHERE STATUT=1", conn)['n'][0]
    fournisseurs = pd.read_sql("SELECT COUNT(*) as n FROM fournisseur WHERE STATUT=1", conn)['n'][0]
    stock = pd.read_sql("SELECT SUM(QUANTITE*PRIX_VENTE) as v FROM stock WHERE STATUT=1 AND QUANTITE>0", conn)['v'][0] or 0
    factures = pd.read_sql("SELECT COUNT(*) as n FROM facturec WHERE STATUT=1", conn)['n'][0]
    conn.close()
    return float(ca), int(produits), int(fournisseurs), float(stock), int(factures)

@st.cache_data(ttl=300)
def get_ventes_mensuelles():
    conn = pymysql.connect(**DB_CONFIG)
    df = pd.read_sql("""
        SELECT YEAR(f.DATE_FACTURE) as annee, MONTH(f.DATE_FACTURE) as mois,
               pv.NOM_POINT_VENTE as boutique,
               SUM(lf.QUANTITE*lf.PRIX_UNITAIRE) as ca,
               COUNT(DISTINCT f.ID_FACTURE) as nb_factures,
               SUM(lf.QUANTITE) as articles
        FROM facturec f JOIN ligne_facturec lf ON f.ID_FACTURE=lf.ID_FACTURE
        JOIN point_vente pv ON f.ID_POINT_VENTE=pv.ID_POINT_VENTE
        WHERE f.STATUT=1 GROUP BY YEAR(f.DATE_FACTURE), MONTH(f.DATE_FACTURE), pv.NOM_POINT_VENTE
        ORDER BY annee, mois
    """, conn)
    conn.close()
    return df

@st.cache_data(ttl=300)
def get_predictions():
    conn = pymysql.connect(**DB_CONFIG)
    df = pd.read_sql("""
        SELECT DATE(f.DATE_FACTURE) as date, SUM(lf.QUANTITE*lf.PRIX_UNITAIRE) as ca
        FROM facturec f JOIN ligne_facturec lf ON f.ID_FACTURE=lf.ID_FACTURE
        WHERE f.STATUT=1 AND f.DATE_FACTURE>='2023-01-01' AND f.DATE_FACTURE<'2025-01-01'
        GROUP BY DATE(f.DATE_FACTURE) ORDER BY date
    """, conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date'])
    df['mois'] = df['date'].dt.to_period('M')
    ca_mensuel = df.groupby('mois')['ca'].sum()
    valeurs = ca_mensuel.values
    dernier = ca_mensuel.index.max().to_timestamp()
    x = np.arange(len(valeurs))
    coeffs = np.polyfit(x, valeurs, 1)
    future_x = np.arange(len(valeurs), len(valeurs)+6)
    tendance = np.polyval(coeffs, future_x)
    mois_nums = ca_mensuel.index.map(lambda p: p.month)
    saison = (ca_mensuel.groupby(mois_nums).mean() / valeurs.mean()).to_dict()
    predictions = []
    future_dates = []
    for i in range(6):
        d = dernier + pd.DateOffset(months=i+1)
        future_dates.append(d.strftime('%Y-%m'))
        coef = saison.get(d.month, 1.0)
        predictions.append(max(0, float(tendance[i] * coef)))
    return future_dates, predictions, float(sum(predictions)), coeffs[0]

@st.cache_data(ttl=300)
def get_productions_detail():
    conn = pymysql.connect(**DB_CONFIG)
    df = pd.read_sql("""
        SELECT p.REF_PRODUCTION, p.date_production, p.quantite,
               pr.DESIGNATION as produit, m.NOM_MAGASIN as magasin, p.valide
        FROM production p
        JOIN produit pr ON p.id_produit_resultant = pr.ID_PRODUIT
        JOIN magasin m ON p.id_magasin = m.ID_MAGASIN
        WHERE p.statut = 1
        ORDER BY p.date_production DESC
        LIMIT 100
    """, conn)
    conn.close()
    return df

def telecharger_pdf(fig, nom="graphique"):
    """Convertit un graphique Plotly en PDF pour téléchargement"""
    buffer = BytesIO()
    fig.write_image(buffer, format="pdf")
    buffer.seek(0)
    return buffer

# ============================================================
# FONCTION GENERATION PDF COMPLET
# ============================================================
def generer_pdf_complet():
    """Génère un PDF complet avec toutes les analyses"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.units import mm, cm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image, Table, 
                                     TableStyle, PageBreak, KeepTogether)
    from reportlab.platypus.flowables import HRFlowable
    import tempfile
    import os
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    
    # Styles personnalisés
    style_titre = ParagraphStyle('Titre', parent=styles['Title'], fontSize=22, textColor=HexColor('#1a1a2e'), spaceAfter=5, alignment=TA_CENTER)
    style_soustitre = ParagraphStyle('SousTitre', parent=styles['Normal'], fontSize=12, textColor=HexColor('#95a5a6'), alignment=TA_CENTER, spaceAfter=20)
    style_h1 = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=16, textColor=HexColor('#e94560'), spaceBefore=20, spaceAfter=10)
    style_h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=13, textColor=HexColor('#2c3e50'), spaceBefore=15, spaceAfter=8)
    style_body = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, textColor=HexColor('#2c3e50'), alignment=TA_JUSTIFY, spaceAfter=6)
    style_kpi_val = ParagraphStyle('KPIVal', parent=styles['Normal'], fontSize=16, textColor=white, alignment=TA_CENTER, fontName='Helvetica-Bold')
    style_kpi_lbl = ParagraphStyle('KPILbl', parent=styles['Normal'], fontSize=8, textColor=HexColor('#cccccc'), alignment=TA_CENTER)
    style_reco = ParagraphStyle('Reco', parent=styles['Normal'], fontSize=10, textColor=HexColor('#E74C3C'), alignment=TA_JUSTIFY, spaceAfter=10, leftIndent=10)
    
    story = []
    
    # ============================================================
    # PAGE DE COUVERTURE
    # ============================================================
    story.append(Spacer(1, 3*cm))
    story.append(Paragraph("SELLAMS EDIMO FASHION", style_titre))
    story.append(Paragraph("Rapport d'Analyse Stratégique Complet", style_soustitre))
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="80%", thickness=2, color=HexColor('#e94560')))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(f"Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", style_soustitre))
    story.append(Paragraph("Période d'analyse : 2023 - 2026", style_soustitre))
    story.append(Paragraph("Source : Base de données sellams_edimofashion (109 tables)", style_soustitre))
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph("CONFIDENTIEL", ParagraphStyle('Conf', parent=style_soustitre, textColor=HexColor('#e94560'), fontSize=16, fontName='Helvetica-Bold')))
    story.append(PageBreak())
    
    # ============================================================
    # 1. SYNTHÈSE - KPI
    # ============================================================
    story.append(Paragraph("1. SYNTHÈSE EXÉCUTIVE", style_h1))
    story.append(Paragraph("Indicateurs Clés de Performance", style_h2))
    
    ca, produits, fournisseurs, stock, factures = get_kpi()
    future_dates, predictions, total_6m, tendance_coeff = get_predictions()
    
    # Tableau KPI
    kpi_data = [
        [Paragraph(f"{ca/1e6:.1f}M FCFA", style_kpi_val), Paragraph("CA TOTAL", style_kpi_lbl),
         Paragraph(f"{factures:,}", style_kpi_val), Paragraph("FACTURES", style_kpi_lbl),
         Paragraph(f"{stock/1e6:.1f}M FCFA", style_kpi_val), Paragraph("VALEUR STOCK", style_kpi_lbl)],
        [Paragraph(f"{produits:,}", style_kpi_val), Paragraph("PRODUITS", style_kpi_lbl),
         Paragraph(f"{fournisseurs}", style_kpi_val), Paragraph("FOURNISSEURS", style_kpi_lbl),
         Paragraph(f"{total_6m/1e6:.1f}M FCFA", style_kpi_val), Paragraph("PRÉVISION 6M", style_kpi_lbl)]
    ]
    t_kpi = Table(kpi_data, colWidths=[3.5*cm, 3.5*cm]*3)
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), HexColor('#1a1a2e')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('ROUNDEDCORNERS', [5,5,5,5]),
    ]))
    story.append(t_kpi)
    story.append(Spacer(1, 0.5*cm))
    
    story.append(Paragraph("Constat Majeurs :", style_h2))
    story.append(Paragraph("• CA Total de 236,4M FCFA sur la période analysée", style_body))
    story.append(Paragraph("• Marge globale excellente de 82,3%", style_body))
    story.append(Paragraph("• Fournisseur GLOBAL représente 65% des achats → Risque de dépendance", style_reco))
    story.append(Paragraph("• Pic anormal de CA en Janvier 2024 (76M FCFA)", style_body))
    story.append(PageBreak())
    
    # ============================================================
    # 2. FOURNISSEURS
    # ============================================================
    story.append(Paragraph("2. ANALYSE DES FOURNISSEURS", style_h1))
    
    conn = pymysql.connect(**DB_CONFIG)
    df_fourn = pd.read_sql("""
        SELECT f.NOM_FOURNISSEUR, SUM(lr.QUANTITE*lr.PRIX_UNITAIRE) as achats,
               COUNT(DISTINCT r.ID_RECEPTION) as nb_receptions
        FROM fournisseur f JOIN reception r ON f.ID_FOURNISSEUR=r.ID_FOURNISSEUR
        JOIN ligne_reception lr ON r.ID_RECEPTION=lr.ID_RECEPTION
        WHERE r.STATUT=1 GROUP BY f.NOM_FOURNISSEUR ORDER BY achats DESC LIMIT 10
    """, conn)
    conn.close()
    
    # Graphique fournisseurs
    fig_fourn = go.Figure()
    fig_fourn.add_trace(go.Bar(y=df_fourn['NOM_FOURNISSEUR'].str[:25], x=df_fourn['achats']/1e6, orientation='h', marker_color='#E17055'))
    fig_fourn.update_layout(title='Top 10 Fournisseurs', xaxis_title='Millions FCFA', height=350, margin=dict(l=10,r=10,t=40,b=10))
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        fig_fourn.write_image(tmp.name, width=800, height=400)
        story.append(Image(tmp.name, width=16*cm, height=8*cm))
        os.unlink(tmp.name)
    
    # Tableau fournisseurs
    fourn_data = [['Fournisseur', 'Achats (M FCFA)', 'Nb Réceptions']]
    for _, row in df_fourn.head(8).iterrows():
        fourn_data.append([row['NOM_FOURNISSEUR'][:30], f"{row['achats']/1e6:.1f}", str(row['nb_receptions'])])
    
    t_fourn = Table(fourn_data, colWidths=[7*cm, 5*cm, 4*cm])
    t_fourn.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [HexColor('#f8f9fa'), white]),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_fourn)
    story.append(Paragraph("RECOMMANDATION : Diversifier le portefeuille fournisseurs. Objectif : GLOBAL < 40% des achats d'ici 12 mois.", style_reco))
    story.append(PageBreak())
    
    # ============================================================
    # 3. STOCKS
    # ============================================================
    story.append(Paragraph("3. ANALYSE DES STOCKS", style_h1))
    
    conn = pymysql.connect(**DB_CONFIG)
    df_stock = pd.read_sql("""
        SELECT m.NOM_MAGASIN, SUM(s.QUANTITE) as qte, SUM(s.QUANTITE*s.PRIX_VENTE) as valeur
        FROM stock s JOIN magasin m ON s.ID_MAGASIN=m.ID_MAGASIN
        WHERE s.STATUT=1 AND s.QUANTITE>0 GROUP BY m.NOM_MAGASIN ORDER BY valeur DESC
    """, conn)
    conn.close()
    
    fig_stock = make_subplots(rows=1, cols=2, specs=[[{'type':'pie'}, {'type':'bar'}]])
    fig_stock.add_trace(go.Pie(labels=df_stock['NOM_MAGASIN'].str[:25], values=df_stock['valeur']/1e6, hole=0.4), row=1, col=1)
    fig_stock.add_trace(go.Bar(x=df_stock['NOM_MAGASIN'].str[:25], y=df_stock['valeur']/1e6, marker_color=['#FDCB6E','#00B894','#E17055','#6C5CE7']), row=1, col=2)
    fig_stock.update_layout(height=350, margin=dict(l=10,r=10,t=40,b=10))
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        fig_stock.write_image(tmp.name, width=1000, height=400)
        story.append(Image(tmp.name, width=16*cm, height=7*cm))
        os.unlink(tmp.name)
    
    stock_data = [['Magasin', 'Quantité', 'Valeur (M FCFA)']]
    for _, row in df_stock.iterrows():
        stock_data.append([row['NOM_MAGASIN'][:35], f"{row['qte']:,.0f}", f"{row['valeur']/1e6:.1f}"])
    t_stock = Table(stock_data, colWidths=[8*cm, 4*cm, 4*cm])
    t_stock.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [HexColor('#f8f9fa'), white]),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_stock)
    story.append(Paragraph("RECOMMANDATION : 10 produits dormants identifiés (~5,2M FCFA). Organiser une vente promotionnelle pour liquider ces stocks.", style_reco))
    story.append(PageBreak())
    
    # ============================================================
    # 4. VENTES
    # ============================================================
    story.append(Paragraph("4. ANALYSE DES VENTES", style_h1))
    
    # CA mensuel
    df_pivot = df_ventes.groupby(['annee','mois'])['ca'].sum().reset_index()
    fig_ca = go.Figure()
    for annee in sorted(df_pivot['annee'].unique()):
        data = df_pivot[df_pivot['annee']==annee]
        fig_ca.add_trace(go.Scatter(x=[mois_noms[m-1] for m in data['mois']], y=data['ca']/1e6, mode='lines+markers', name=str(annee)))
    fig_ca.update_layout(title='CA Mensuel par Année', yaxis_title='Millions FCFA', height=350, margin=dict(l=10,r=10,t=40,b=10))
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        fig_ca.write_image(tmp.name, width=900, height=400)
        story.append(Image(tmp.name, width=16*cm, height=7*cm))
        os.unlink(tmp.name)
    
    # Saisonnalité
    df_saison = df_ventes.groupby('mois')['ca'].mean().reset_index()
    fig_saison = go.Figure()
    fig_saison.add_trace(go.Bar(x=[mois_noms[int(m)-1] for m in df_saison['mois']], y=df_saison['ca']/1e6, marker_color='#3498DB'))
    fig_saison.update_layout(title='CA Moyen par Mois (Saisonnalité)', yaxis_title='Millions FCFA', height=300)
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        fig_saison.write_image(tmp.name, width=900, height=350)
        story.append(Image(tmp.name, width=16*cm, height=6*cm))
        os.unlink(tmp.name)
    
    story.append(Paragraph("• Pic Janvier (27M FCFA moyen) et Décembre (7,3M) = Haute saison", style_body))
    story.append(Paragraph("• Mars-Avril = Creux (2-3M FCFA)", style_body))
    story.append(Paragraph("RECOMMANDATION : Renforcer les stocks dès Octobre. Lancer des promotions ciblées en Mars-Avril pour lisser l'activité.", style_reco))
    story.append(PageBreak())
    
    # ============================================================
    # 5. PRÉDICTIONS
    # ============================================================
    story.append(Paragraph("5. PRÉDICTIONS DE VENTES", style_h1))
    story.append(Paragraph(f"Tendance : {'Hausse' if tendance_coeff > 0 else 'Baisse'} de {abs(tendance_coeff):,.0f} FCFA/mois", style_body))
    
    fig_pred = go.Figure()
    fig_pred.add_trace(go.Bar(x=future_dates, y=[p/1e6 for p in predictions], marker_color=['#E74C3C' if p>5e6 else '#4ECDC4' for p in predictions],
                               text=[f'{p/1e6:.1f}M' for p in predictions], textposition='outside'))
    fig_pred.update_layout(title='Prévisions CA - 6 Prochains Mois', yaxis_title='Millions FCFA', height=350)
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        fig_pred.write_image(tmp.name, width=900, height=400)
        story.append(Image(tmp.name, width=16*cm, height=7*cm))
        os.unlink(tmp.name)
    
    pred_data = [['Mois', 'Prévision (FCFA)', 'Niveau']]
    for d, p in zip(future_dates, predictions):
        niveau = 'Élevé' if p>5e6 else ('Moyen' if p>2e6 else 'Faible')
        pred_data.append([d, f"{p:,.0f}", niveau])
    t_pred = Table(pred_data, colWidths=[5*cm, 6*cm, 5*cm])
    t_pred.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor('#cccccc')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_pred)
    story.append(Paragraph(f"Total prévu sur 6 mois : {total_6m:,.0f} FCFA", style_h2))
    story.append(PageBreak())
    
    # ============================================================
    # 6. PRODUCTION
    # ============================================================
    story.append(Paragraph("6. PRODUCTION", style_h1))
    
    df_prod = get_productions_detail()
    prod_mensuel = df_prod.groupby(df_prod['date_production'].dt.strftime('%Y-%m')).agg({'quantite':'sum', 'REF_PRODUCTION':'count'}).reset_index()
    prod_mensuel.columns = ['Mois', 'Quantité', 'Nb_Productions']
    
    fig_prod = go.Figure()
    fig_prod.add_trace(go.Bar(x=prod_mensuel['Mois'], y=prod_mensuel['Quantité'], name='Quantité', marker_color='#6C5CE7'))
    fig_prod.update_layout(title='Production Mensuelle', yaxis_title='Quantité', height=350)
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        fig_prod.write_image(tmp.name, width=900, height=400)
        story.append(Image(tmp.name, width=16*cm, height=7*cm))
        os.unlink(tmp.name)
    
    top_prod = df_prod.groupby('produit')['quantite'].sum().sort_values(ascending=False).head(10)
    prod_data = [['Produit', 'Quantité Totale']]
    for nom, qte in top_prod.items():
        prod_data.append([nom[:60], f"{qte:,.0f}"])
    t_prod = Table(prod_data, colWidths=[12*cm, 4*cm])
    t_prod.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor('#cccccc')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_prod)
    story.append(PageBreak())
    
    # ============================================================
    # 7. TISSUS & CARACTÉRISTIQUES
    # ============================================================
    story.append(Paragraph("7. TISSUS & CARACTÉRISTIQUES", style_h1))
    
    couleurs_data = {'BLEU':170,'NOIR':151,'BLANC':142,'VERT':96,'GRIS':74,'ROUGE':61,'JAUNE':57,'ROSE':47,'MARRON':43,'ORANGE':34}
    fig_coul = go.Figure()
    fig_coul.add_trace(go.Bar(x=list(couleurs_data.keys()), y=list(couleurs_data.values()), marker_color='#3498DB'))
    fig_coul.update_layout(title='Palette de Couleurs', yaxis_title='Nb Produits', height=300)
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        fig_coul.write_image(tmp.name, width=900, height=350)
        story.append(Image(tmp.name, width=16*cm, height=6*cm))
        os.unlink(tmp.name)
    
    tissus_data = {'LIN':358,'TISSU':174,'SOIE':70,'DOUBLURE':46,'PAGNE':43,'BOUTON':41,'COTON':37}
    fig_tiss = go.Figure()
    fig_tiss.add_trace(go.Bar(y=list(tissus_data.keys()), x=list(tissus_data.values()), orientation='h', marker_color='#E17055'))
    fig_tiss.update_layout(title='Occurrences Tissus', xaxis_title='Nb Produits', height=300)
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        fig_tiss.write_image(tmp.name, width=900, height=350)
        story.append(Image(tmp.name, width=16*cm, height=6*cm))
        os.unlink(tmp.name)
    
    story.append(Paragraph("• LIN dominant (358 produits) - Sécuriser les approvisionnements", style_body))
    story.append(Paragraph("• BLEU, NOIR, BLANC = 46% des produits", style_body))
    story.append(Paragraph("RECOMMANDATION : Développer collection grandes tailles (3XL+) et enfants.", style_reco))
    story.append(PageBreak())
    
    # ============================================================
    # 8. RECOMMANDATIONS FINALES
    # ============================================================
    story.append(Paragraph("8. RECOMMANDATIONS STRATÉGIQUES", style_h1))
    
    recommandations = [
        ("Fournisseurs", "Diversifier le portefeuille. Objectif : GLOBAL < 40% des achats. Développer ATELIER COUTURE EDIMO."),
        ("Stocks", "Liquider les 10 produits dormants (~5,2M FCFA). Mettre en place une alerte à 90 jours sans mouvement."),
        ("Ventes", "Exploiter les pics de Janvier et Décembre. Lancer des promotions en Mars-Avril pour lisser l'activité."),
        ("Boutiques", "Dupliquer les pratiques de Yaoundé (panier 2x supérieur) à Douala. Former au up-selling."),
        ("Production", "Automatiser le suivi des matières premières (POPELINE, LIN). Planifier selon saisonnalité."),
        ("Produits", "Développer la ligne mode (marges + élevées). Réduire la dépendance aux maillots FECAFOOT."),
    ]
    
    for titre, reco in recommandations:
        story.append(Paragraph(f"<b>{titre}</b> : {reco}", style_body))
        story.append(Spacer(1, 0.2*cm))
    
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#cccccc')))
    story.append(Paragraph(f"© {datetime.now().year} Sellams Edimo Fashion - Document confidentiel généré automatiquement", 
                           ParagraphStyle('Footer', parent=style_soustitre, fontSize=8)))
    
    # Générer le PDF
    doc.build(story)
    buffer.seek(0)
    
    # Sauvegarder dans un fichier temporaire
    pdf_path = os.path.join(BASE_DIR, f"Rapport_Complet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    with open(pdf_path, 'wb') as f:
        f.write(buffer.read())
    
    return pdf_path

# ============================================================
# SIDEBAR AVEC FILTRES GLOBAUX
# ============================================================
with st.sidebar:
    st.title("SELLAMS EDIMO")
    st.caption("Portail d'Analyse Stratégique")
    st.divider()
    
    # Filtres globaux
    st.subheader("Filtres d'Analyse")
    df_ventes = get_ventes_mensuelles()
    annees_dispo = sorted(df_ventes['annee'].unique())
    
    filtre_annee = st.selectbox("Année", ["Toutes"] + [str(a) for a in annees_dispo])
    mois_noms = ['Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre']
    filtre_mois = st.selectbox("Mois", ["Tous"] + mois_noms)
    
    st.divider()
    page = st.radio("Navigation", [
        "Accueil",
        "Analyses Ciblées",
        "Galerie Graphiques",
        "Exports & Rapports",
        "Prédictions",
        "Tissus & Caractéristiques"
    ])
    st.divider()
    st.caption(f"{datetime.now().strftime('%d/%m/%Y %H:%M')}")
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
cols[0].metric("CA Total", f"{ca/1e6:.1f}M")
cols[1].metric("Stock", f"{stock/1e6:.1f}M")
cols[2].metric("Produits", f"{produits:,}")
cols[3].metric("Prévision 6M", f"{total_6m/1e6:.1f}M")
cols[4].metric("CA Filtré", f"{ca_filtre/1e6:.1f}M")
cols[5].metric("Factures Filtrées", f"{factures_filtre:,}")

st.divider()

# ============================================================
# ACCUEIL
# ============================================================
if page == "Accueil":
    st.header("Tableau de Bord Général")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Marge Globale", "82,3%", delta="Excellente")
    with col2:
        st.metric("Boutiques", "2", delta="Douala + Yaoundé")
    with col3:
        st.metric("Tables BDD", "109", delta="Analysées")
    
    # Comparaison années
    st.subheader("Comparaison CA Mensuel par Année")
    df_pivot = df_ventes.groupby(['annee','mois'])['ca'].sum().reset_index()
    fig = go.Figure()
    couleurs_annees = {2023:'#3498DB', 2024:'#E74C3C', 2025:'#2ECC71', 2026:'#F39C12'}
    for annee in sorted(df_pivot['annee'].unique()):
        data_annee = df_pivot[df_pivot['annee']==annee]
        fig.add_trace(go.Scatter(
            x=[mois_noms[m-1] for m in data_annee['mois']],
            y=data_annee['ca']/1e6,
            mode='lines+markers',
            name=str(annee),
            line=dict(width=3, color=couleurs_annees.get(annee, '#95A5A6')),
            marker=dict(size=8),
            hovertemplate='<b>%{x} %{text}</b><br>CA: %{y:.1f}M FCFA<extra></extra>',
            text=[str(annee)]*len(data_annee)
        ))
    fig.update_layout(title='Comparaison CA Mensuel Toutes Années', yaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=450, hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)
    
    # Prévisions
    st.subheader("Prévisions 6 Mois")
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=future_dates, y=[p/1e6 for p in predictions], marker_color=['#E74C3C' if p>5e6 else '#4ECDC4' for p in predictions],
                          text=[f"{p/1e6:.1f}M" for p in predictions], textposition='outside',
                          hovertemplate='<b>%{x}</b><br>Prévision: %{y:.1f}M FCFA<extra></extra>'))
    fig2.update_layout(title='Prévisions CA', yaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=350)
    st.plotly_chart(fig2, use_container_width=True)

# ============================================================
# ANALYSES CIBLEES
# ============================================================
elif page == "Analyses Ciblées":
    st.header("Analyses Ciblées")
    
    tabs = st.tabs(["Fournisseurs", "Stocks", "Ventes", "Boutiques", "Production"])
    
    # --- FOURNISSEURS ---
    with tabs[0]:
        st.subheader("Fournisseurs & Approvisionnements")
        conn = pymysql.connect(**DB_CONFIG)
        df_fourn = pd.read_sql("""
            SELECT f.NOM_FOURNISSEUR, YEAR(r.DATE_RECEPTION) as annee,
                   SUM(lr.QUANTITE*lr.PRIX_UNITAIRE) as achats, COUNT(DISTINCT r.ID_RECEPTION) as nb_receptions
            FROM fournisseur f JOIN reception r ON f.ID_FOURNISSEUR=r.ID_FOURNISSEUR
            JOIN ligne_reception lr ON r.ID_RECEPTION=lr.ID_RECEPTION
            WHERE r.STATUT=1 GROUP BY f.NOM_FOURNISSEUR, YEAR(r.DATE_RECEPTION) ORDER BY achats DESC
        """, conn)
        conn.close()
        
        annee_fourn = st.selectbox("Filtrer par année", ["Toutes"] + sorted(df_fourn['annee'].unique().astype(str).tolist()), key="fourn_annee")
        if annee_fourn != "Toutes":
            df_fourn = df_fourn[df_fourn['annee'] == int(annee_fourn)]
        
        fig = go.Figure()
        df_agg = df_fourn.groupby('NOM_FOURNISSEUR')['achats'].sum().sort_values(ascending=True).tail(10)
        fig.add_trace(go.Bar(y=df_agg.index.str[:25], x=df_agg.values/1e6, orientation='h', marker_color='#E17055',
                              text=[f"{v/1e6:.1f}M" for v in df_agg.values], textposition='outside',
                              hovertemplate='<b>%{y}</b><br>Achats: %{x:.1f}M FCFA<extra></extra>'))
        fig.update_layout(title=f'Achats par Fournisseur ({annee_fourn})', xaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        st.warning("**RECOMMANDATION :** GLOBAL = 65% des achats. Diversifier avec ATELIER COUTURE EDIMO et rechercher 2-3 nouveaux fournisseurs pour réduire le risque de dépendance.")
    
    # --- STOCKS ---
    with tabs[1]:
        st.subheader("Analyse des Stocks")
        conn = pymysql.connect(**DB_CONFIG)
        df_stock = pd.read_sql("""
            SELECT m.NOM_MAGASIN, cp.NOM as categorie, SUM(s.QUANTITE) as qte,
                   SUM(s.QUANTITE*s.PRIX_VENTE) as valeur_vente, SUM(s.QUANTITE*s.PRIX_ACHAT) as valeur_achat
            FROM stock s JOIN magasin m ON s.ID_MAGASIN=m.ID_MAGASIN
            JOIN produit p ON s.ID_PRODUIT=p.ID_PRODUIT
            LEFT JOIN categorie_produit cp ON p.ID_CATEGORIE_PRODUIT=cp.ID_CATEGORIE
            WHERE s.STATUT=1 AND s.QUANTITE>0 GROUP BY m.NOM_MAGASIN, cp.NOM ORDER BY valeur_vente DESC LIMIT 20
        """, conn)
        conn.close()
        
        fig = make_subplots(rows=1, cols=2, specs=[[{'type':'pie'}, {'type':'bar'}]], subplot_titles=('Stock par Magasin (%)', 'Top Catégories en Stock'))
        stock_mag = df_stock.groupby('NOM_MAGASIN')['valeur_vente'].sum()
        fig.add_trace(go.Pie(labels=stock_mag.index.str[:25], values=stock_mag.values/1e6, hole=0.4,
                              hovertemplate='<b>%{label}</b><br>%{value:.1f}M FCFA<br>%{percent}<extra></extra>'), row=1, col=1)
        
        top_cat = df_stock.groupby('categorie')['valeur_vente'].sum().sort_values(ascending=True).tail(8)
        fig.add_trace(go.Bar(y=top_cat.index.str[:25], x=top_cat.values/1e6, orientation='h', marker_color='#00B894',
                              text=[f"{v/1e6:.1f}M" for v in top_cat.values], textposition='outside'), row=1, col=2)
        fig.update_layout(height=450, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
        
        st.warning("**RECOMMANDATION :** 10 produits dormants (~5,2M FCFA). Organiser une vente flash avec -30% pour liquider ces stocks. Mettre en place une alerte automatique à 90 jours sans mouvement.")
    
    # --- VENTES ---
    with tabs[2]:
        st.subheader("Analyse des Ventes")
        conn = pymysql.connect(**DB_CONFIG)
        df_ventes_cat = pd.read_sql("""
            SELECT cp.NOM as categorie, YEAR(f.DATE_FACTURE) as annee, MONTH(f.DATE_FACTURE) as mois,
                   SUM(lf.QUANTITE*lf.PRIX_UNITAIRE) as ca, SUM(lf.QUANTITE) as qte
            FROM facturec f JOIN ligne_facturec lf ON f.ID_FACTURE=lf.ID_FACTURE
            JOIN produit p ON lf.ID_PRODUIT=p.ID_PRODUIT
            LEFT JOIN categorie_produit cp ON p.ID_CATEGORIE_PRODUIT=cp.ID_CATEGORIE
            WHERE f.STATUT=1 GROUP BY cp.NOM, YEAR(f.DATE_FACTURE), MONTH(f.DATE_FACTURE) ORDER BY ca DESC
        """, conn)
        conn.close()
        
        col1, col2 = st.columns(2)
        with col1:
            annee_ventes = st.selectbox("Année", ["Toutes"] + sorted(df_ventes_cat['annee'].unique().astype(str).tolist()), key="ventes_annee")
        with col2:
            top_n = st.slider("Top N catégories", 5, 20, 10)
        
        if annee_ventes != "Toutes":
            df_v = df_ventes_cat[df_ventes_cat['annee'] == int(annee_ventes)]
        else:
            df_v = df_ventes_cat
        
        df_v_agg = df_v.groupby('categorie')['ca'].sum().sort_values(ascending=True).tail(top_n)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=df_v_agg.index.str[:30], x=df_v_agg.values/1e6, orientation='h', marker_color='#3498DB',
                              text=[f"{v/1e6:.1f}M" for v in df_v_agg.values], textposition='outside'))
        fig.update_layout(title=f'Top {top_n} Catégories - CA ({annee_ventes})', xaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        st.info("**RECOMMANDATION :** Pic Janvier (27M) et Décembre (7M). Renforcer les stocks dès Octobre pour ces périodes. Mars-Avril = creux : lancer des promotions ciblées.")
    
    # --- BOUTIQUES ---
    with tabs[3]:
        st.subheader("Performance Boutiques")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Grand Mall Douala", "154,3M FCFA", delta="65,3% du CA")
            st.metric("Panier Moyen", "69 500 FCFA")
            st.metric("Factures", "4 018")
        with col2:
            st.metric("Djeuga Palace Yaoundé", "73,8M FCFA", delta="31,2% du CA")
            st.metric("Panier Moyen", "137 000 FCFA")
            st.metric("Factures", "415")
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=['Grand Mall Douala', 'Djeuga Palace Yaoundé'], y=[154.3, 73.8],
                              marker_color=['#FF6B6B', '#4ECDC4'], text=['154,3M', '73,8M'], textposition='outside'))
        fig.update_layout(title='CA par Boutique (MFCFA)', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=350)
        st.plotly_chart(fig, use_container_width=True)
        
        st.info("**RECOMMANDATION :** Yaoundé a un panier moyen 2x supérieur. Étudier les pratiques de vente pour les dupliquer à Douala. Former les vendeurs Douala au up-selling.")
    
    # --- PRODUCTION (DÉTAILLÉ) ---
    with tabs[4]:
        st.subheader("Production - Détail Complet")
        df_prod = get_productions_detail()
        
        # Filtres
        col1, col2, col3 = st.columns(3)
        with col1:
            annees_prod = sorted(df_prod['date_production'].dt.year.unique().astype(int))
            annee_prod = st.selectbox("Année", ["Toutes"] + [str(a) for a in annees_prod])
        with col2:
            magasins_prod = sorted(df_prod['magasin'].unique())
            magasin_prod = st.selectbox("Magasin", ["Tous"] + list(magasins_prod))
        
        df_prod_filtre = df_prod.copy()
        if annee_prod != "Toutes":
            df_prod_filtre = df_prod_filtre[df_prod_filtre['date_production'].dt.year == int(annee_prod)]
        if magasin_prod != "Tous":
            df_prod_filtre = df_prod_filtre[df_prod_filtre['magasin'] == magasin_prod]
        
        # KPIs production
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Total Productions", len(df_prod_filtre))
        col_b.metric("Quantité Totale", f"{df_prod_filtre['quantite'].sum():,.0f}")
        col_c.metric("Taux Validation", f"{(df_prod_filtre['valide'].mean()*100):.0f}%")
        
        # Graphique production par mois
        df_prod_filtre['mois'] = df_prod_filtre['date_production'].dt.strftime('%Y-%m')
        prod_mensuel = df_prod_filtre.groupby('mois').agg({'quantite':'sum', 'REF_PRODUCTION':'count'}).reset_index()
        prod_mensuel.columns = ['Mois', 'Quantité', 'Nb_Productions']
        
        fig = make_subplots(specs=[[{'secondary_y': True}]])
        fig.add_trace(go.Bar(x=prod_mensuel['Mois'], y=prod_mensuel['Quantité'], name='Quantité', marker_color='#6C5CE7'), secondary_y=False)
        fig.add_trace(go.Scatter(x=prod_mensuel['Mois'], y=prod_mensuel['Nb_Productions'], name='Nb Productions', mode='lines+markers', line=dict(color='#E74C3C', width=3)), secondary_y=True)
        fig.update_layout(title='Production Mensuelle', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400, hovermode='x unified')
        fig.update_yaxes(title_text='Quantité Produite', secondary_y=False)
        fig.update_yaxes(title_text='Nombre de Productions', secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)
        
        # Tableau détaillé
        st.subheader("Détail des 50 Dernières Productions")
        st.dataframe(df_prod_filtre.head(50)[['date_production','produit','quantite','magasin']],
                     use_container_width=True, hide_index=True,
                     column_config={'date_production':'Date','produit':'Produit','quantite':'Qté','magasin':'Magasin'})
        
        # Top produits fabriqués
        st.subheader("Produits les Plus Fabriqués")
        top_produits = df_prod_filtre.groupby('produit')['quantite'].sum().sort_values(ascending=False).head(10)
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(y=top_produits.index.str[:50], x=top_produits.values, orientation='h', marker_color='#F39C12',
                               text=top_produits.values, textposition='outside'))
        fig2.update_layout(title='Top 10 Produits Fabriqués', xaxis_title='Quantité', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
        st.plotly_chart(fig2, use_container_width=True)
        
        st.info("**RECOMMANDATION :** La production est concentrée sur les ensembles et chemises. Automatiser le suivi des matières premières (POPELINE, LIN) pour éviter les ruptures. L'Atelier Couture Edimo monte en puissance.")

# ============================================================
# GALERIE GRAPHIQUES (INTERACTIFS + ANALYSES)
# ============================================================
elif page == "Galerie Graphiques":
    st.header("Galerie de Graphiques Interactifs avec Analyses")
    
    # Graphique 1 : CA mensuel avec comparaison
    with st.expander("1. Évolution du CA Mensuel", expanded=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            df_pivot = df_ventes.groupby(['annee','mois'])['ca'].sum().reset_index()
            fig = go.Figure()
            for annee in sorted(df_pivot['annee'].unique()):
                data_annee = df_pivot[df_pivot['annee']==annee]
                fig.add_trace(go.Scatter(x=[mois_noms[m-1] for m in data_annee['mois']], y=data_annee['ca']/1e6,
                                          mode='lines+markers', name=str(annee), line=dict(width=2.5)))
            fig.update_layout(title='CA Mensuel par Année', yaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400, hovermode='x unified')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("### Analyse")
            st.markdown("""
            - **Pic Janvier 2024** : 76M FCFA (anormal, vérifier saisie)
            - **Tendance** : Baisse progressive depuis 2024
            - **Saisonnalité** : Janvier et Décembre = pics
            """)
            st.success("**RECO :** Vérifier le pic Janvier 2024. Si réel, répliquer la stratégie.")
    
    # Graphique 2 : Répartition CA boutiques
    with st.expander("2. Répartition CA par Boutique", expanded=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = make_subplots(rows=1, cols=2, specs=[[{'type':'pie'}, {'type':'bar'}]])
            ca_bout = df_ventes.groupby('boutique')['ca'].sum()
            fig.add_trace(go.Pie(labels=ca_bout.index, values=ca_bout.values/1e6, hole=0.4), row=1, col=1)
            fig.add_trace(go.Bar(x=ca_bout.index.str[:20], y=ca_bout.values/1e6, marker_color=['#FF6B6B','#4ECDC4'],
                                  text=[f'{v/1e6:.1f}M' for v in ca_bout.values], textposition='outside'), row=1, col=2)
            fig.update_layout(height=400, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("### Analyse")
            st.markdown("""
            - **Douala** : 65,3% du CA (volume)
            - **Yaoundé** : 31,2% (valeur unitaire + élevée)
            - **Panier Yaoundé** : 2x supérieur à Douala
            """)
            st.success("**RECO :** Former vendeurs Douala au premium. Organiser événements VIP à Yaoundé.")
    
    # Graphique 3 : Top 10 Produits
    with st.expander("3. Top 10 Produits par CA", expanded=True):
        conn = pymysql.connect(**DB_CONFIG)
        df_top = pd.read_sql("""
            SELECT p.DESIGNATION, SUM(lf.QUANTITE*lf.PRIX_UNITAIRE) as ca, SUM(lf.QUANTITE) as qte
            FROM ligne_facturec lf JOIN facturec f ON lf.ID_FACTURE=f.ID_FACTURE AND f.STATUT=1
            JOIN produit p ON lf.ID_PRODUIT=p.ID_PRODUIT GROUP BY p.DESIGNATION ORDER BY ca DESC LIMIT 10
        """, conn)
        conn.close()
        
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = go.Figure()
            fig.add_trace(go.Bar(y=df_top['DESIGNATION'].str[:40], x=df_top['ca']/1e6, orientation='h', marker_color='#6C5CE7'))
            fig.update_layout(title='Top 10 Produits', xaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("### Analyse")
            st.markdown("""
            - **Maillots FECAFOOT** dominent (29,7M + 25,4M)
            - **Produits mode** : faible poids en CA
            - Concentration sur produits sportifs
            """)
            st.success("**RECO :** Développer la ligne mode (marges + élevées). Limiter dépendance aux maillots.")
    
    # Graphique 4 : Stock par Magasin
    with st.expander("4. Valeur du Stock par Magasin", expanded=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            conn = pymysql.connect(**DB_CONFIG)
            df_st = pd.read_sql("""
                SELECT m.NOM_MAGASIN, SUM(s.QUANTITE*s.PRIX_VENTE) as valeur FROM stock s
                JOIN magasin m ON s.ID_MAGASIN=m.ID_MAGASIN WHERE s.STATUT=1 AND s.QUANTITE>0 GROUP BY m.NOM_MAGASIN
            """, conn)
            conn.close()
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_st['NOM_MAGASIN'].str[:30], y=df_st['valeur']/1e6,
                                  marker_color=['#FDCB6E','#00B894','#E17055','#6C5CE7'],
                                  text=[f'{v/1e6:.1f}M' for v in df_st['valeur']], textposition='outside'))
            fig.update_layout(title='Stock par Magasin', yaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=350)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("### Analyse")
            st.markdown("""
            - **Djeuga Palace** : 35,9M (72% du stock)
            - **Grand Mall** : 11,7M (articles + nombreux)
            - **Matières premières** : 1,2M
            """)
            st.warning("**RECO :** Rééquilibrer le stock entre boutiques. Transférer surplus Yaoundé → Douala.")
    
    # Graphique 5 : Fournisseurs
    with st.expander(" 5. Top Fournisseurs", expanded=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            conn = pymysql.connect(**DB_CONFIG)
            df_f = pd.read_sql("""
                SELECT f.NOM_FOURNISSEUR, SUM(lr.QUANTITE*lr.PRIX_UNITAIRE) as achats FROM fournisseur f
                JOIN reception r ON f.ID_FOURNISSEUR=r.ID_FOURNISSEUR JOIN ligne_reception lr ON r.ID_RECEPTION=lr.ID_RECEPTION
                WHERE r.STATUT=1 GROUP BY f.NOM_FOURNISSEUR ORDER BY achats DESC LIMIT 10
            """, conn)
            conn.close()
            fig = go.Figure()
            fig.add_trace(go.Bar(y=df_f['NOM_FOURNISSEUR'].str[:25], x=df_f['achats']/1e6, orientation='h', marker_color='#E17055'))
            fig.update_layout(title='Top 10 Fournisseurs', xaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("### Analyse")
            st.markdown("""
            - **GLOBAL** = 65% des achats
            - **INTERNE** = 16%
            - Risque de dépendance élevé
            """)
            st.error("**RECO URGENTE :** Diversifier immédiatement. Objectif : GLOBAL < 40%.")
    
    # Graphique 6 : Saisonnalité
    with st.expander(" 6. Saisonnalité des Ventes", expanded=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            df_ventes_mois = df_ventes.groupby('mois')['ca'].mean().reset_index()
            fig = go.Figure()
            colors_saison = ['#E74C3C' if v > df_ventes_mois['ca'].mean() else '#3498DB' for v in df_ventes_mois['ca']]
            fig.add_trace(go.Bar(x=[mois_noms[int(m)-1] for m in df_ventes_mois['mois']], y=df_ventes_mois['ca']/1e6,
                                  marker_color=colors_saison, text=[f'{v/1e6:.1f}M' for v in df_ventes_mois['ca']], textposition='outside'))
            fig.add_hline(y=df_ventes_mois['ca'].mean()/1e6, line_dash='dash', line_color='gray', annotation_text='Moyenne')
            fig.update_layout(title='CA Moyen par Mois (Saisonnalité)', yaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("### Analyse")
            st.markdown("""
            - **Haute saison** : Janvier (27M), Septembre, Décembre
            - **Basse saison** : Mars-Avril (2-3M)
            - Écart x10 entre pic et creux
            """)
            st.success("**RECO :** Campagnes marketing Octobre-Novembre. Promotions Mars-Avril pour lisser l'activité.")

# ============================================================
# EXPORTS & RAPPORTS
# ============================================================
elif page == "Exports & Rapports":
    st.header("Exports & Rapports")
    
    tab_exports = st.tabs(["Excel", "PDF", "CSV"])
    
    with tab_exports[0]:
        st.subheader("Télécharger les Exports Excel")
        exports_path = os.path.join(BASE_DIR, "04_exports")
        if os.path.exists(exports_path):
            for f in sorted(os.listdir(exports_path)):
                if f.endswith('.xlsx'):
                    with open(os.path.join(exports_path, f), 'rb') as file:
                        st.download_button(f"⬇ {f}", file, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        else:
            st.warning("Aucun export trouvé.")
    
    with tab_exports[1]:
        st.subheader("Exporter les Graphiques en PDF")
        st.markdown("Cliquez sur un graphique pour le télécharger en PDF :")
        
        # CA comparatif PDF
        fig_pdf = go.Figure()
        df_pivot = df_ventes.groupby(['annee','mois'])['ca'].sum().reset_index()
        for annee in sorted(df_pivot['annee'].unique()):
            data = df_pivot[df_pivot['annee']==annee]
            fig_pdf.add_trace(go.Scatter(
                x=[mois_noms[m-1] for m in data['mois']],
                y=data['ca']/1e6,
                mode='lines+markers',
                name=str(annee)
            ))
        fig_pdf.update_layout(title='CA Mensuel Comparatif', yaxis_title='Millions FCFA')
        
        pdf_buffer = telecharger_pdf(fig_pdf, "ca_comparatif")
        st.download_button("⬇ Télécharger CA Comparatif (PDF)", pdf_buffer, "CA_Comparatif.pdf", "application/pdf")
        
        # Rapport HTML
        st.subheader("Rapport Complet")
        rapport_path = os.path.join(BASE_DIR, "05_rapport")
        if os.path.exists(rapport_path):
            for f in sorted(os.listdir(rapport_path)):
                if f.endswith('.html'):
                    with open(os.path.join(rapport_path, f), 'r', encoding='utf-8') as file:
                        st.download_button(f"⬇ {f}", file.read(), f, 'text/html')
    
    with tab_exports[2]:
        st.subheader("Fichiers CSV (Prédictions)")
        pred_path = os.path.join(BASE_DIR, "06_predictions")
        if os.path.exists(pred_path):
            for f in sorted(os.listdir(pred_path)):
                if f.endswith('.csv'):
                    with open(os.path.join(pred_path, f), 'rb') as file:
                        st.download_button(f"⬇ {f}", file, f, 'text/csv')

# ============================================================
# PRÉDICTIONS
# ============================================================

elif page == "Prédictions":
    st.header("Prédictions & Projections 2026-2027")
    st.caption("Basé sur les données réelles 2023-2024 · 3 méthodes combinées")
    
    # ============================================================
    # FONCTIONS DE PRÉDICTION ÉTENDUES
    # ============================================================
    @st.cache_data(ttl=300)
    def get_predictions_etendues():
        conn = pymysql.connect(**DB_CONFIG)
        
        # 1. Ventes mensuelles 2023-2024 (base d'apprentissage)
        df_ventes_base = pd.read_sql("""
            SELECT DATE(f.DATE_FACTURE) as date, pv.NOM_POINT_VENTE as boutique,
                   SUM(lf.QUANTITE*lf.PRIX_UNITAIRE) as ca,
                   SUM(lf.QUANTITE) as qte_vendue,
                   COUNT(DISTINCT f.ID_FACTURE) as nb_factures
            FROM facturec f JOIN ligne_facturec lf ON f.ID_FACTURE=lf.ID_FACTURE
            JOIN point_vente pv ON f.ID_POINT_VENTE=pv.ID_POINT_VENTE
            WHERE f.STATUT=1 AND f.DATE_FACTURE>='2023-01-01' AND f.DATE_FACTURE<'2025-01-01'
            GROUP BY DATE(f.DATE_FACTURE), pv.NOM_POINT_VENTE
            ORDER BY date
        """, conn)
        df_ventes_base['date'] = pd.to_datetime(df_ventes_base['date'])
        
        # 2. Productions 2023-2024
        df_prod_base = pd.read_sql("""
            SELECT DATE(date_production) as date, SUM(quantite) as qte_produite, COUNT(*) as nb_productions
            FROM production WHERE statut=1 AND valide=1
            AND date_production>='2023-01-01' AND date_production<'2025-01-01'
            GROUP BY DATE(date_production) ORDER BY date
        """, conn)
        df_prod_base['date'] = pd.to_datetime(df_prod_base['date'])
        
        # 3. Achats fournisseurs 2023-2024
        df_achats_base = pd.read_sql("""
            SELECT DATE(r.DATE_RECEPTION) as date, SUM(lr.QUANTITE*lr.PRIX_UNITAIRE) as achats,
                   SUM(lr.QUANTITE) as qte_achetee
            FROM reception r JOIN ligne_reception lr ON r.ID_RECEPTION=lr.ID_RECEPTION
            WHERE r.STATUT=1 AND r.DATE_RECEPTION>='2023-01-01' AND r.DATE_RECEPTION<'2025-01-01'
            GROUP BY DATE(r.DATE_RECEPTION) ORDER BY date
        """, conn)
        df_achats_base['date'] = pd.to_datetime(df_achats_base['date'])
        
        conn.close()
        
        # Agrégation mensuelle
        df_ventes_base['mois'] = df_ventes_base['date'].dt.to_period('M')
        df_prod_base['mois'] = df_prod_base['date'].dt.to_period('M')
        df_achats_base['mois'] = df_achats_base['date'].dt.to_period('M')
        
        ca_mensuel = df_ventes_base.groupby('mois')['ca'].sum()
        qte_mensuel = df_ventes_base.groupby('mois')['qte_vendue'].sum()
        factures_mensuel = df_ventes_base.groupby('mois')['nb_factures'].sum()
        prod_mensuel = df_prod_base.groupby('mois')['qte_produite'].sum()
        achats_mensuel = df_achats_base.groupby('mois')['achats'].sum()
        
        # Saisonnalité par mois
        saison_ca = (ca_mensuel.groupby(lambda x: x.month).mean() / ca_mensuel.mean()).to_dict()
        saison_qte = (qte_mensuel.groupby(lambda x: x.month).mean() / qte_mensuel.mean()).to_dict()
        saison_prod = (prod_mensuel.groupby(lambda x: x.month).mean() / prod_mensuel.mean()).to_dict() if len(prod_mensuel) > 0 else {}
        saison_achats = (achats_mensuel.groupby(lambda x: x.month).mean() / achats_mensuel.mean()).to_dict() if len(achats_mensuel) > 0 else {}
        
        # Tendances
        x_ca = np.arange(len(ca_mensuel))
        coeff_ca = np.polyfit(x_ca, ca_mensuel.values, 1)
        coeff_qte = np.polyfit(x_ca, qte_mensuel.values, 1)
        coeff_fact = np.polyfit(x_ca, factures_mensuel.values, 1)
        
        # Projections : Juin 2026 à Décembre 2027 (19 mois)
        nb_mois_futurs = 19
        dernier_mois = pd.Period('2026-05', 'M')
        future_dates = [(dernier_mois + i).strftime('%Y-%m') for i in range(1, nb_mois_futurs+1)]
        
        # Prédictions CA (3 méthodes)
        future_x = np.arange(len(ca_mensuel), len(ca_mensuel) + nb_mois_futurs)
        tendance_ca = np.polyval(coeff_ca, future_x)
        predictions_ca = []
        predictions_ca_ponderees = []
        for i in range(nb_mois_futurs):
            mois_futur = (dernier_mois + i + 1).month
            coef = saison_ca.get(mois_futur, 1.0)
            pred_saison = float(tendance_ca[i] * coef)
            # Holt-Winters simplifié
            alpha = 0.3
            if i == 0:
                level = ca_mensuel.values[-1]
                trend = coeff_ca[0]
            else:
                level = alpha * max(0, tendance_ca[i-1]) + (1-alpha) * (level + trend)
                trend = 0.2 * (tendance_ca[i] - tendance_ca[i-1]) + 0.8 * trend
            pred_hw = float(level + trend * (i+1))
            predictions_ca.append(pred_saison)
            predictions_ca_ponderees.append(float((pred_saison * 0.5 + max(0, tendance_ca[i]) * 0.3 + max(0, pred_hw) * 0.2)))
        
        # Prédictions quantités
        tendance_qte = np.polyval(coeff_qte, future_x)
        predictions_qte = [float(max(0, tendance_qte[i] * saison_qte.get((dernier_mois+i+1).month, 1.0))) for i in range(nb_mois_futurs)]
        
        # Prédictions factures
        tendance_fact = np.polyval(coeff_fact, future_x)
        predictions_fact = [int(max(0, tendance_fact[i])) for i in range(nb_mois_futurs)]
        
        # Prédictions production (si données)
        predictions_prod = []
        if len(prod_mensuel) > 0:
            x_prod = np.arange(len(prod_mensuel))
            coeff_prod = np.polyfit(x_prod, prod_mensuel.values, 1)
            future_x_prod = np.arange(len(prod_mensuel), len(prod_mensuel) + nb_mois_futurs)
            tendance_prod = np.polyval(coeff_prod, future_x_prod)
            predictions_prod = [float(max(0, tendance_prod[i] * saison_prod.get((dernier_mois+i+1).month, 1.0))) if saison_prod else float(max(0, tendance_prod[i])) for i in range(nb_mois_futurs)]
        
        # Prédictions achats
        predictions_achats = []
        if len(achats_mensuel) > 0:
            x_ach = np.arange(len(achats_mensuel))
            coeff_ach = np.polyfit(x_ach, achats_mensuel.values, 1)
            future_x_ach = np.arange(len(achats_mensuel), len(achats_mensuel) + nb_mois_futurs)
            tendance_ach = np.polyval(coeff_ach, future_x_ach)
            predictions_achats = [float(max(0, tendance_ach[i] * saison_achats.get((dernier_mois+i+1).month, 1.0))) for i in range(nb_mois_futurs)]
        
        return {
            'future_dates': future_dates,
            'predictions_ca': predictions_ca_ponderees,
            'predictions_qte': predictions_qte,
            'predictions_fact': predictions_fact,
            'predictions_prod': predictions_prod,
            'predictions_achats': predictions_achats,
            'coeff_ca': coeff_ca[0],
            'coeff_qte': coeff_qte[0],
            'ca_moyen_mensuel': ca_mensuel.mean(),
            'qte_moyen_mensuel': qte_mensuel.mean(),
            'saison_ca': saison_ca,
            'ca_2023': ca_mensuel[ca_mensuel.index.year==2023].sum(),
            'ca_2024': ca_mensuel[ca_mensuel.index.year==2024].sum(),
            'qte_2023': qte_mensuel[qte_mensuel.index.year==2023].sum(),
            'qte_2024': qte_mensuel[qte_mensuel.index.year==2024].sum(),
        }
    
    preds = get_predictions_etendues()
    
    # ============================================================
    # KPI DE PRÉDICTION
    # ============================================================
    mois_2026 = [d for d in preds['future_dates'] if d.startswith('2026')]
    mois_2027 = [d for d in preds['future_dates'] if d.startswith('2027')]
    
    ca_2026 = sum(preds['predictions_ca'][:len(mois_2026)])
    ca_2027 = sum(preds['predictions_ca'][len(mois_2026):])
    qte_2026 = sum(preds['predictions_qte'][:len(mois_2026)])
    qte_2027 = sum(preds['predictions_qte'][len(mois_2026):])
    
    st.subheader("Synthèse des Projections")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("CA Reste 2026", f"{ca_2026/1e6:.1f}M FCFA", delta=f"{len(mois_2026)} mois")
    col2.metric("CA Prévu 2027", f"{ca_2027/1e6:.1f}M FCFA", delta=f"{len(mois_2027)} mois")
    col3.metric("Qté Vendue 2027", f"{qte_2027:,.0f}", delta="articles")
    col4.metric("CA Moyen Mensuel", f"{preds['ca_moyen_mensuel']/1e6:.1f}M", delta="Historique")
    col5.metric("Tendance CA", f"{'Hausse' if preds['coeff_ca']>0 else 'Baisse'}", delta=f"{abs(preds['coeff_ca']):,.0f} FCFA/mois")
    
    st.divider()
    
    # ============================================================
    # ONGLETS DE PRÉDICTION DÉTAILLÉE
    # ============================================================
    tabs_pred = st.tabs([
        "CA & Ventes",
        "Quantités & Volumes",
        "Production",
        "Approvisionnements",
        "Synthèse Globale"
    ])
    
    # --- CA & VENTES ---
    with tabs_pred[0]:
        st.subheader("Projections de Chiffre d'Affaires")
        st.markdown(f"""
        **Justification :** Basé sur les données réelles 2023-2024 (CA total {preds['ca_2023']/1e6:.1f}M en 2023, {preds['ca_2024']/1e6:.1f}M en 2024).
        La tendance montre une {'hausse' if preds['coeff_ca']>0 else 'baisse'} de {abs(preds['coeff_ca']):,.0f} FCFA/mois.
        """)
        
        # Graphique projections CA
        fig = go.Figure()
        # Historique
        conn = pymysql.connect(**DB_CONFIG)
        df_hist = pd.read_sql("""
            SELECT DATE_FORMAT(DATE_FACTURE,'%Y-%m') as mois, SUM(lf.QUANTITE*lf.PRIX_UNITAIRE) as ca
            FROM facturec f JOIN ligne_facturec lf ON f.ID_FACTURE=lf.ID_FACTURE
            WHERE f.STATUT=1 AND f.DATE_FACTURE>='2023-01-01' AND f.DATE_FACTURE<'2026-06-01'
            GROUP BY DATE_FORMAT(DATE_FACTURE,'%Y-%m') ORDER BY mois
        """, conn)
        conn.close()
        
        fig.add_trace(go.Scatter(x=df_hist['mois'].tolist(), y=df_hist['ca']/1e6, mode='lines', name='CA Réel', line=dict(color='#3498DB', width=2)))
        fig.add_trace(go.Scatter(x=preds['future_dates'], y=[p/1e6 for p in preds['predictions_ca']], mode='lines+markers', name='CA Prévu', line=dict(color='#E74C3C', width=3, dash='dash'), marker=dict(size=6)))
        fig.add_vline(x=len(df_hist)-1, line_width=1, line_dash="dash", line_color="gray")
        fig.update_layout(title='Projection CA : Juin 2026 → Décembre 2027', yaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=450, hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)
        
        # Tableau détaillé
        st.subheader("Détail Mensuel")
        df_ca_detail = pd.DataFrame({
            'Mois': preds['future_dates'],
            'CA Prévu (FCFA)': [f"{p:,.0f}" for p in preds['predictions_ca']],
            'Niveau': ['🔴 Élevé' if p>8e6 else ('🟠 Moyen' if p>4e6 else '🟢 Faible') for p in preds['predictions_ca']],
            'Variation': ['↗' if i>0 and preds['predictions_ca'][i]>preds['predictions_ca'][i-1] else '↘' for i in range(len(preds['predictions_ca']))]
        })
        st.dataframe(df_ca_detail, use_container_width=True, hide_index=True)
        
        st.info("""
        **💡 Analyse CA :** 
        - La projection intègre la saisonnalité observée (pics Janvier, Septembre, Décembre)
        - La tendance de fond est calculée sur 24 mois de données réelles
        - Les mois de Janvier 2027 et Décembre 2027 devraient être les plus forts
        - Le CA 2027 est estimé entre **{:.0f}M et {:.0f}M FCFA** selon le scénario
        """.format(ca_2027/1e6 * 0.85, ca_2027/1e6 * 1.15))
    
    # --- QUANTITÉS & VOLUMES ---
    with tabs_pred[1]:
        st.subheader("Projections des Quantités Vendues")
        st.markdown(f"""
        **Justification :** Volume total {preds['qte_2023']:,.0f} articles en 2023, {preds['qte_2024']:,.0f} en 2024.
        Tendance : {'hausse' if preds['coeff_qte']>0 else 'baisse'} de {abs(preds['coeff_qte']):,.1f} articles/mois.
        """)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=preds['future_dates'], y=preds['predictions_qte'], marker_color=['#E74C3C' if q>500 else '#4ECDC4' for q in preds['predictions_qte']],
                              text=[f'{q:,.0f}' for q in preds['predictions_qte']], textposition='outside',
                              hovertemplate='<b>%{x}</b><br>Qté prévue: %{y:,.0f} articles<extra></extra>'))
        fig.update_layout(title='Projection Quantités Vendues', yaxis_title='Articles', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        st.info(f"""
        **Analyse Volumes :**
        - Volume total estimé 2027 : **{qte_2027:,.0f} articles**
        - Panier moyen stable autour de {preds['ca_moyen_mensuel']/preds['qte_moyen_mensuel']:,.0f} FCFA/article
        - Les pics de volume coïncident avec les périodes de fêtes (Décembre) et rentrée (Janvier)
        """)
    
    # --- PRODUCTION ---
    with tabs_pred[2]:
        st.subheader("Projections de Production")
        
        if len(preds['predictions_prod']) > 0:
            st.markdown("**Justification :** Basé sur l'historique de production 2023-2024 (185 productions enregistrées).")
            
            fig = go.Figure()
            fig.add_trace(go.Bar(x=preds['future_dates'], y=preds['predictions_prod'], marker_color='#6C5CE7',
                                  text=[f'{p:,.0f}' for p in preds['predictions_prod']], textposition='outside',
                                  hovertemplate='<b>%{x}</b><br>Production prévue: %{y:,.0f} unités<extra></extra>'))
            fig.update_layout(title='Projection Production Mensuelle', yaxis_title='Unités Produites', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            total_prod_2027 = sum(preds['predictions_prod'][len(mois_2026):])
            st.info(f"""
            **Analyse Production :**
            - Production totale estimée 2027 : **{total_prod_2027:,.0f} unités**
            - La production suit la saisonnalité des ventes avec 1-2 mois d'avance
            - L'Atelier Couture Edimo représente une part croissante de la production
            - RECO : Planifier les approvisionnements tissus 3 mois avant les pics de production
            """)
        else:
            st.warning("Données de production insuffisantes pour une projection fiable.")
    
    # --- APPROVISIONNEMENTS ---
    with tabs_pred[3]:
        st.subheader("🏗️ Projections des Approvisionnements")
        
        if len(preds['predictions_achats']) > 0:
            st.markdown("**Justification :** Basé sur l'historique des réceptions 2023-2024.")
            
            fig = go.Figure()
            fig.add_trace(go.Bar(x=preds['future_dates'], y=[p/1e6 for p in preds['predictions_achats']], marker_color='#E17055',
                                  text=[f'{p/1e6:.1f}M' for p in preds['predictions_achats']], textposition='outside',
                                  hovertemplate='<b>%{x}</b><br>Achats prévus: %{y:.1f}M FCFA<extra></extra>'))
            fig.update_layout(title='Projection Achats/Approvisionnements', yaxis_title='Millions FCFA', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            total_achats_2027 = sum(preds['predictions_achats'][len(mois_2026):])
            st.info(f"""
            **Analyse Approvisionnements :**
            - Achats totaux estimés 2027 : **{total_achats_2027/1e6:.1f}M FCFA**
            - Ratio Achats/CA projeté : {total_achats_2027/ca_2027*100:.1f}%
            - RECO : Négocier des contrats annuels avec GLOBAL pour sécuriser les prix
            - RECO : Diversifier vers 2-3 nouveaux fournisseurs pour réduire le risque
            """)
        else:
            st.warning("Données d'achats insuffisantes pour une projection fiable.")
    
    # --- SYNTHÈSE GLOBALE ---
    with tabs_pred[4]:
        st.subheader("Synthèse Globale 2026-2027")
        
        # Résumé annuel
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Reste 2026 (Juin-Déc)")
            st.markdown(f"""
            - **CA estimé** : {ca_2026/1e6:.1f}M FCFA
            - **Articles vendus** : {qte_2026:,.0f}
            - **Mois concernés** : {len(mois_2026)}
            - **CA moyen mensuel** : {ca_2026/len(mois_2026)/1e6:.1f}M
            """)
        with col2:
            st.markdown("### Année 2027")
            st.markdown(f"""
            - **CA estimé** : {ca_2027/1e6:.1f}M FCFA
            - **Articles vendus** : {qte_2027:,.0f}
            - **Mois concernés** : {len(mois_2027)}
            - **CA moyen mensuel** : {ca_2027/len(mois_2027)/1e6:.1f}M
            """)
        
        # Graphique synthèse
        fig = make_subplots(rows=2, cols=2, subplot_titles=('CA Mensuel Projeté', 'Quantités Vendues', 'Production Estimée', 'Approvisionnements'))
        
        fig.add_trace(go.Scatter(x=preds['future_dates'], y=[p/1e6 for p in preds['predictions_ca']], mode='lines', name='CA', line=dict(color='#E74C3C', width=2)), row=1, col=1)
        fig.add_trace(go.Bar(x=preds['future_dates'], y=preds['predictions_qte'], name='Qté', marker_color='#3498DB'), row=1, col=2)
        if len(preds['predictions_prod']) > 0:
            fig.add_trace(go.Bar(x=preds['future_dates'], y=preds['predictions_prod'], name='Prod', marker_color='#6C5CE7'), row=2, col=1)
        if len(preds['predictions_achats']) > 0:
            fig.add_trace(go.Bar(x=preds['future_dates'], y=[p/1e6 for p in preds['predictions_achats']], name='Achats', marker_color='#E17055'), row=2, col=2)
        
        fig.update_layout(height=700, showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
        
        # RECOMMANDATIONS FINALES
        st.subheader("Recommandations Stratégiques Basées sur les Projections")
        
        reco_data = [
            ("CA 2027", f"Estimé à {ca_2027/1e6:.1f}M FCFA", "Objectif : +10% via développement Yaoundé et ligne mode"),
            ("Stocks", f"Anticiper {qte_2027:,.0f} ventes", "Constituer stock stratégique Oct-Nov pour pics Décembre-Janvier"),
            ("Production", "Planifier selon saisonnalité", "Lisser la production sur l'année pour optimiser l'atelier"),
            ("Achats", f"~{sum(preds['predictions_achats'][len(mois_2026):])/1e6:.1f}M FCFA estimés", "Négocier tarifs annuels, diversifier fournisseurs"),
            ("Effectifs", "Adapter aux pics", "Renforts saisonniers Octobre-Janvier, formation continue"),
            ("Suivi", "Tableau de bord mensuel", "Comparer réel vs prévu chaque mois, ajuster les projections"),
        ]
        
        for titre, valeur, action in reco_data:
            with st.expander(f"{titre} : {valeur}"):
                st.markdown(f"**Action recommandée :** {action}")

# ============================================================
# TISSUS
# ============================================================
elif page == "Tissus & Caractéristiques":
    st.header("Analyse Tissus & Caractéristiques")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Matières", "779"); col2.metric("LIN", "358"); col3.metric("Couleurs", "18"); col4.metric("Tissus", "15")
    
    tab1, tab2, tab3 = st.tabs(["Couleurs", "Tissus", "Tailles"])
    with tab1:
        fig = go.Figure()
        couleurs_data = {'BLEU':170,'NOIR':151,'BLANC':142,'VERT':96,'GRIS':74,'ROUGE':61,'JAUNE':57,'ROSE':47,'MARRON':43,'ORANGE':34,'CIEL':32,'BEIGE':27,'BORDEAU':26,'VIOLET':21,'OLIVE':11}
        fig.add_trace(go.Bar(x=list(couleurs_data.keys()), y=list(couleurs_data.values()),
                              marker_color=['#3498DB','#2C3E50','#ECF0F1','#2ECC71','#95A5A6','#E74C3C','#F1C40F','#FD79A8','#795548','#E67E22','#87CEEB','#D4C5A9','#C0392B','#9B59B6','#808000'],
                              text=list(couleurs_data.values()), textposition='outside'))
        fig.update_layout(title='Palette de Couleurs', yaxis_title='Nb Produits', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=450)
        st.plotly_chart(fig, use_container_width=True)
        st.info("**RECO :** BLEU, NOIR, BLANC = 46% des produits. Développer une collection ROUGE/JAUNE pour la saison estivale.")
    
    with tab2:
        fig = go.Figure()
        tissus_data = {'LIN':358,'TISSU':174,'SOIE':70,'DOUBLURE':46,'PAGNE':43,'BOUTON':41,'COTON':37,'FERMETURE':35,'BROKA':34,'BRODERIE':25}
        fig.add_trace(go.Bar(y=list(tissus_data.keys()), x=list(tissus_data.values()), orientation='h', marker_color='#E17055', text=list(tissus_data.values()), textposition='outside'))
        fig.update_layout(title='Occurrences Tissus', xaxis_title='Nb Produits', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.info("**RECO :** LIN dominant (358 produits). Sécuriser 2-3 fournisseurs de LIN pour éviter les ruptures.")
    
    with tab3:
        fig = go.Figure()
        tailles_data = {'TU':253,'XL':170,'S':157,'T.42':71,'T.44':58,'T.46':31,'T.48':28,'T.U':22,'ENFANT':15,'3XL':14}
        fig.add_trace(go.Bar(x=list(tailles_data.keys()), y=list(tailles_data.values()), marker_color='#6C5CE7', text=list(tailles_data.values()), textposition='outside'))
        fig.update_layout(title='Distribution des Tailles', yaxis_title='Nb Produits', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.info("**RECO :** 253 produits en Taille Unique. Développer une gamme grandes tailles (3XL+) et enfants.")

st.divider()
st.caption("© 2026 Sellams Edimo Fashion - Portail d'Analyse Stratégique • Tous droits réservés • CONFIDENTIEL")