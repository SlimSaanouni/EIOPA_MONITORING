"""
Dashboard Streamlit pour le monitoring EIOPA
Bonus : Interface interactive pour visualiser les taux et l'historique
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

from config import TARGET_COUNTRY, TARGET_MATURITIES
from analyzer import EIOPAAnalyzer
from src.downloader import EIOPADownloader
from src.processor import EIOPAProcessor
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
            ["📈 Vue d'ensemble", "🔄 Mise à jour", "📜 Historique", "📊 Analyse"]
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
    
    # Métriques principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        rate_1y = latest_row['rate_1y'] * 100
        st.metric("Taux 1Y", f"{rate_1y:.2f}%")
    
    with col2:
        rate_10y = latest_row['rate_10y'] * 100
        st.metric("Taux 10Y", f"{rate_10y:.2f}%")
    
    with col3:
        rate_30y = latest_row['rate_30y'] * 100
        st.metric("Taux 30Y", f"{rate_30y:.2f}%")
    
    with col4:
        va = latest_row['va'] * 100 if pd.notna(latest_row['va']) else 0
        st.metric("VA", f"{va:.2f}%")
    
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
    """Page de mise à jour"""
    st.header("🔄 Mise à jour des données")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.info("Télécharge et traite le dernier fichier disponible depuis l'EIOPA")
    
    with col2:
        if st.button("▶️ Lancer la mise à jour", type="primary"):
            run_update()


def run_update():
    """Exécute la mise à jour"""
    progress_bar = st.progress(0)
    status = st.empty()
    
    try:
        # Étape 1 : Téléchargement
        status.text("📥 Téléchargement en cours...")
        progress_bar.progress(25)
        
        downloader = EIOPADownloader()
        zip_path = downloader.download_latest()
        
        if not zip_path:
            st.error("❌ Échec du téléchargement")
            return
        
        # Étape 2 : Traitement
        status.text("⚙️ Traitement des données...")
        progress_bar.progress(50)
        
        processor = EIOPAProcessor(zip_path)
        current_data = processor.process()
        
        if not current_data:
            st.error("❌ Échec du traitement")
            return
        
        # Étape 3 : Analyse
        status.text("📊 Analyse en cours...")
        progress_bar.progress(75)
        
        analyzer = get_analyzer()
        analyzer.add_to_historical(current_data)
        analysis = analyzer.analyze(current_data)
        
        # Étape 4 : Génération rapports
        status.text("📝 Génération des rapports...")
        progress_bar.progress(90)
        
        reporter = EIOPAReporter()
        reporter.generate_text_report(analysis)
        
        progress_bar.progress(100)
        status.text("✅ Mise à jour terminée !")
        
        st.success(f"✅ Données mises à jour pour le {current_data['reference_date'].strftime('%d/%m/%Y')}")
        
        # Afficher les résultats
        st.subheader("📊 Résultats")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Taux extraits**")
            for maturity, rate in sorted(current_data['rates'].items()):
                st.write(f"- {maturity}Y : {format_rate_pct(rate)}")
        
        with col2:
            if current_data.get('va'):
                st.write("**Volatility Adjustment**")
                st.write(f"VA : {format_rate_pct(current_data['va'])}")
        
        # Alertes
        if analysis.get('alerts'):
            st.warning("⚠️ **Alertes détectées**")
            for alert in analysis['alerts']:
                st.write(f"- {alert}")
        
        # Forcer le rechargement du cache
        st.cache_data.clear()
        
    except Exception as e:
        st.error(f"❌ Erreur : {e}")
    finally:
        progress_bar.empty()
        status.empty()


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


if __name__ == "__main__":
    main()