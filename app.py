"""
Dashboard Streamlit pour le monitoring EIOPA
Bonus : Interface interactive pour visualiser les taux et l'historique
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

from config import TARGET_COUNTRY, TARGET_MATURITIES
from src.analyzer import EIOPAAnalyzer
from src.downloader import EIOPADownloader
from src.exporter import available_export_dates, export_curve_csv
from src.ingestion import ingest_zip
from src.reporter import EIOPAReporter
from src.utils import format_rate_pct

# Configuration de la page
st.set_page_config(
    page_title="EIOPA Monitoring Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .alert-box {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 15px;
        margin: 10px 0;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_historical_data():
    """Charge les données historiques avec cache"""
    analyzer = EIOPAAnalyzer()
    return analyzer.historical_data


@st.cache_resource
def get_analyzer():
    """Récupère l'analyzer (singleton)"""
    return EIOPAAnalyzer()


def plot_yield_curve(rates: dict, title: str = "Courbe des taux"):
    """Affiche la courbe des taux"""
    maturities = sorted(rates.keys())
    values = [rates[m] * 100 for m in maturities]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=maturities,
        y=values,
        mode='lines+markers',
        name='Taux',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=10)
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Maturité (années)",
        yaxis_title="Taux (%)",
        hovermode='x unified',
        height=400
    )
    
    return fig


def plot_time_series(df: pd.DataFrame, maturity: int, title: str = None):
    """Affiche une série temporelle"""
    if title is None:
        title = f"Évolution du taux {maturity}Y"
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['reference_date'],
        y=df['rate'] * 100,
        mode='lines',
        name=f'Taux {maturity}Y',
        line=dict(color='#2ca02c', width=2)
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Taux (%)",
        hovermode='x unified',
        height=400
    )
    
    return fig


def plot_comparison(current_rates: dict, previous_rates: dict):
    """Compare deux courbes de taux"""
    maturities = sorted(current_rates.keys())
    
    fig = go.Figure()
    
    # Courbe actuelle
    fig.add_trace(go.Scatter(
        x=maturities,
        y=[current_rates[m] * 100 for m in maturities],
        mode='lines+markers',
        name='Actuel',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=10)
    ))
    
    # Courbe précédente
    fig.add_trace(go.Scatter(
        x=maturities,
        y=[previous_rates.get(m, 0) * 100 for m in maturities],
        mode='lines+markers',
        name='Précédent',
        line=dict(color='#ff7f0e', width=3, dash='dash'),
        marker=dict(size=10)
    ))
    
    fig.update_layout(
        title="Comparaison des courbes",
        xaxis_title="Maturité (années)",
        yaxis_title="Taux (%)",
        hovermode='x unified',
        height=400
    )
    
    return fig


def main():
    st.title("📊 EIOPA Risk-Free Rates Monitoring")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Action à effectuer
        action = st.radio(
            "Action",
            ["📈 Vue d'ensemble", "🔄 Mise à jour", "📜 Historique", "📊 Analyse", "📤 Export"]
        )
        
        st.markdown("---")
        st.markdown(f"**Pays surveillé** : {TARGET_COUNTRY}")
        st.markdown(f"**Maturités** : {', '.join(map(str, TARGET_MATURITIES))}Y")
    
    # Vue d'ensemble
    if action == "📈 Vue d'ensemble":
        show_overview()
    
    # Mise à jour
    elif action == "🔄 Mise à jour":
        show_update_page()
    
    # Historique
    elif action == "📜 Historique":
        show_historical_page()
    
    # Analyse
    elif action == "📊 Analyse":
        show_analysis_page()

    # Export
    elif action == "📤 Export":
        show_export_page()


def show_overview():
    """Page de vue d'ensemble"""
    st.header("Vue d'ensemble")
    
    analyzer = get_analyzer()
    
    if analyzer.historical_data.empty:
        st.warning("⚠️ Aucune donnée disponible. Effectuez une première mise à jour.")
        return
    
    # Dernières données
    latest_row = analyzer.historical_data.iloc[-1]
    latest_date = latest_row['reference_date']
    
    st.subheader(f"📅 Dernière mise à jour : {latest_date.strftime('%d/%m/%Y')}")
    
    # Métriques principales — une par maturité suivie (config.TARGET_MATURITIES), plus VA
    columns = st.columns(len(TARGET_MATURITIES) + 1)

    for col, maturity in zip(columns[:-1], TARGET_MATURITIES):
        with col:
            col_name = f'rate_{maturity}y'
            if col_name in latest_row and pd.notna(latest_row[col_name]):
                st.metric(f"Taux {maturity}Y", f"{latest_row[col_name] * 100:.2f}%")

    with columns[-1]:
        va = latest_row['va'] * 100 if pd.notna(latest_row['va']) else None
        st.metric("VA", f"{va:.2f}%" if va is not None else "N/A")
    
    # Courbe actuelle
    st.subheader("📈 Courbe des taux actuelle")
    
    rates = {}
    for maturity in TARGET_MATURITIES:
        col_name = f'rate_{maturity}y'
        if col_name in latest_row and pd.notna(latest_row[col_name]):
            rates[maturity] = float(latest_row[col_name])
    
    if rates:
        fig = plot_yield_curve(rates)
        st.plotly_chart(fig, use_container_width=True)
    
    # Évolution récente (6 derniers mois)
    st.subheader("📊 Évolution récente (Taux 10Y)")
    
    six_months_ago = latest_date - timedelta(days=180)
    ts = analyzer.get_time_series(
        country=TARGET_COUNTRY,
        maturity=10,
        start_date=six_months_ago
    )
    
    if not ts.empty:
        fig = plot_time_series(ts, 10)
        st.plotly_chart(fig, use_container_width=True)


def show_update_page():
    """Page de mise à jour — liste les dates distantes et locales, télécharge la sélection."""
    st.header("🔄 Mise à jour des données")

    # ------------------------------------------------------------------
    # 1. Dates déjà ingérées en base (historical.db) — pas un scan de fichiers,
    #    reflète l'état réel de la base plutôt que la présence d'un fichier extrait.
    # ------------------------------------------------------------------
    from src import db

    conn = db.get_connection()
    try:
        local_dates = {datetime.strptime(d, "%Y-%m-%d").date() for d in db.get_dates(conn, TARGET_COUNTRY)}
    finally:
        conn.close()

    # ------------------------------------------------------------------
    # 2. Dates disponibles sur le site EIOPA
    # ------------------------------------------------------------------
    with st.spinner("Récupération des fichiers disponibles sur l'EIOPA..."):
        try:
            downloader = EIOPADownloader()
            available_files = downloader.get_available_files()  # [(filename, url, date)]
        except Exception as e:
            st.error(f"❌ Impossible de contacter l'EIOPA : {e}")
            return
 
    if not available_files:
        st.warning("⚠️ Aucun fichier trouvé sur le site EIOPA.")
        return
 
    # ------------------------------------------------------------------
    # 3. Construction du tableau de statut
    # ------------------------------------------------------------------
    st.subheader("📋 Fichiers disponibles")
 
    rows = []
    for filename, url, file_date in available_files:
        already_done = file_date.date() in local_dates
        rows.append({
            "_date":     file_date,
            "_url":      url,
            "_filename": filename,
            "Date":      file_date.strftime("%d/%m/%Y"),
            "Fichier":   filename,
            "Statut":    "✅ Déjà traité" if already_done else "⬇️ À télécharger",
        })
 
    df_display = pd.DataFrame(rows)[["Date", "Fichier", "Statut"]]
    st.dataframe(df_display, use_container_width=True, hide_index=True)
 
    # ------------------------------------------------------------------
    # 4. Sélection des dates à télécharger
    # ------------------------------------------------------------------
    downloadable = [r for r in rows if r["Statut"] == "⬇️ À télécharger"]
 
    if not downloadable:
        st.success("✅ Tous les fichiers disponibles ont déjà été traités.")
        return
 
    st.subheader("📥 Sélection")
 
    date_options = {r["Date"]: r for r in downloadable}
    selected_labels = st.multiselect(
        "Dates à télécharger",
        options=list(date_options.keys()),
        default=list(date_options.keys())[:1],
    )
 
    if not selected_labels:
        st.info("Sélectionnez au moins une date.")
        return
 
    if st.button(f"▶️ Lancer le téléchargement ({len(selected_labels)} fichier(s))", type="primary"):
        selected_rows = [date_options[lbl] for lbl in selected_labels]
        run_update(selected_rows)
 
 
def run_update(selected_rows: list):
    """Télécharge et traite les fichiers sélectionnés."""
    total = len(selected_rows)
    progress_bar = st.progress(0)
    status = st.empty()
    results = []
 
    for i, row in enumerate(selected_rows):
        label = row["Date"]
        status.text(f"[{i+1}/{total}] Traitement de {label}...")
 
        try:
            # Téléchargement
            downloader = EIOPADownloader()
            zip_path = downloader.download_file(row["_url"], row["_filename"])
            if not zip_path:
                results.append((label, False, "Échec du téléchargement"))
                continue

            # Ingestion (extraction + écriture dans historical.db)
            current_data = ingest_zip(zip_path)

            # Analyse
            analyzer = get_analyzer()
            analysis = analyzer.analyze(current_data)

            # Rapport
            reporter = EIOPAReporter()
            reporter.generate_text_report(analysis)

            message = f"{len(current_data['rates'])} taux extraits"
            if current_data["status"] == "PARTIAL":
                message += f" (⚠️ partiel : {'; '.join(current_data['missing_maturities'][:3])})"
            results.append((label, True, message))

        except Exception as e:
            results.append((label, False, str(e)))
 
        progress_bar.progress((i + 1) / total)
 
    progress_bar.empty()
    status.empty()
 
    # Résumé
    st.subheader("📊 Résultats")
    for label, success, message in results:
        if success:
            st.success(f"✅ {label} — {message}")
        else:
            st.error(f"❌ {label} — {message}")
 
    if any(s for _, s, _ in results):
        get_analyzer().export_historical_csv()
        st.cache_data.clear()


def show_historical_page():
    """Page historique"""
    st.header("📜 Données historiques")
    
    df = load_historical_data()
    
    if df.empty:
        st.warning("⚠️ Aucune donnée historique disponible")
        return
    
    # Statistiques
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Nombre d'enregistrements", len(df))
    
    with col2:
        min_date = df['reference_date'].min()
        st.metric("Première date", min_date.strftime('%d/%m/%Y'))
    
    with col3:
        max_date = df['reference_date'].max()
        st.metric("Dernière date", max_date.strftime('%d/%m/%Y'))
    
    # Sélection de la maturité
    st.subheader("📈 Évolution temporelle")
    
    maturity = st.selectbox(
        "Sélectionner une maturité",
        TARGET_MATURITIES,
        format_func=lambda x: f"{x} ans"
    )
    
    # Plage de dates
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Date de début",
            value=df['reference_date'].max() - timedelta(days=365)
        )
    
    with col2:
        end_date = st.date_input(
            "Date de fin",
            value=df['reference_date'].max()
        )
    
    # Récupérer la série temporelle
    analyzer = get_analyzer()
    ts = analyzer.get_time_series(
        country=TARGET_COUNTRY,
        maturity=maturity,
        start_date=datetime.combine(start_date, datetime.min.time()),
        end_date=datetime.combine(end_date, datetime.max.time())
    )
    
    if not ts.empty:
        fig = plot_time_series(ts, maturity)
        st.plotly_chart(fig, use_container_width=True)
        
        # Tableau de données
        with st.expander("📋 Voir les données"):
            display_df = ts.copy()
            display_df['rate'] = display_df['rate'].apply(lambda x: f"{x*100:.4f}%")
            st.dataframe(display_df, use_container_width=True)
    else:
        st.warning("Aucune donnée pour la période sélectionnée")


def show_analysis_page():
    """Page d'analyse"""
    st.header("📊 Analyse comparative")
    
    analyzer = get_analyzer()
    
    if analyzer.historical_data.empty:
        st.warning("⚠️ Aucune donnée disponible")
        return
    
    # Sélection des dates
    dates = sorted(analyzer.historical_data['reference_date'].unique(), reverse=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        date1 = st.selectbox(
            "Date 1 (actuelle)",
            dates,
            format_func=lambda x: x.strftime('%d/%m/%Y')
        )
    
    with col2:
        date2 = st.selectbox(
            "Date 2 (comparaison)",
            dates,
            index=min(1, len(dates)-1),
            format_func=lambda x: x.strftime('%d/%m/%Y')
        )
    
    # Récupérer les données
    data1 = analyzer.get_historical_data(TARGET_COUNTRY, date1)
    data2 = analyzer.get_historical_data(TARGET_COUNTRY, date2)
    
    if not data1 or not data2:
        st.error("Données manquantes pour les dates sélectionnées")
        return
    
    # Comparaison des courbes
    st.subheader("📈 Comparaison des courbes")
    fig = plot_comparison(data1['rates'], data2['rates'])
    st.plotly_chart(fig, use_container_width=True)
    
    # Tableau de variations
    st.subheader("📊 Variations (en points de base)")
    
    variations = []
    for maturity in sorted(data1['rates'].keys()):
        if maturity in data2['rates']:
            rate1 = data1['rates'][maturity]
            rate2 = data2['rates'][maturity]
            change_bps = (rate1 - rate2) * 10000
            
            variations.append({
                'Maturité': f'{maturity}Y',
                'Date 1': format_rate_pct(rate1),
                'Date 2': format_rate_pct(rate2),
                'Variation (bps)': f"{change_bps:+.1f}",
                'Variation (%)': f"{((rate1/rate2 - 1) * 100):+.2f}%"
            })
    
    df_variations = pd.DataFrame(variations)
    st.dataframe(df_variations, use_container_width=True, hide_index=True)


def show_export_page():
    """Page d'export au format d'échange (Maturity,Base,Up,Down) pour ESG / Asset_PTF."""
    st.header("📤 Export")
    st.markdown(
        "Génère les fichiers `RFR_[DATE]_[VA_TYPE].csv` (colonnes "
        "`Maturity,Base,Up,Down`) consommés par les outils ESG et Asset_PTF."
    )
    st.info(
        "Le choix NO_VA / WITH_VA à utiliser dépend de l'outil cible et de la "
        "méthodologie retenue — voir la documentation externe à ce dashboard. "
        "Cette page ne fixe aucun défaut."
    )

    dates = available_export_dates(TARGET_COUNTRY)
    if not dates:
        st.warning("⚠️ Aucune courbe en base. Effectuez d'abord une mise à jour.")
        return

    date_labels = {datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y"): d for d in dates}
    selected_label = st.selectbox("Date de clôture", list(date_labels.keys()))
    selected_date = date_labels[selected_label]

    va_type_map = {
        "Sans VA (NO_VA)": ["NO_VA"],
        "Avec VA (WITH_VA)": ["WITH_VA"],
        "Les deux": ["NO_VA", "WITH_VA"],
    }
    va_choice = st.radio("Type de courbe", list(va_type_map.keys()), horizontal=True)

    if st.button("▶️ Générer l'export", type="primary"):
        generated = []
        for va_type in va_type_map[va_choice]:
            try:
                path = export_curve_csv(selected_date, va_type)
                generated.append((va_type, path))
                st.success(f"✅ {va_type} — {path.name}")
            except ValueError as e:
                st.error(f"❌ {va_type} — {e}")

        for va_type, path in generated:
            with open(path, "rb") as f:
                st.download_button(
                    label=f"⬇️ Télécharger {path.name}",
                    data=f.read(),
                    file_name=path.name,
                    mime="text/csv",
                    key=f"download_{path.name}",
                )


if __name__ == "__main__":
    main()