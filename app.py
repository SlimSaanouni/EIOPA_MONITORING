"""
Dashboard Streamlit pour le monitoring EIOPA
Bonus : Interface interactive pour visualiser les taux et l'historique
"""
from pathlib import Path

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

# Logo SSA Analytics — deux variantes (traits noirs / traits blancs), la même
# icône. logo_white.svg pour les fonds sombres/colorés, logo.svg pour les
# fonds clairs. Chargées une fois, inlinées en SVG pour rester stylables en
# CSS (voir .eiopa-logo-light/.eiopa-logo-dark plus bas).
_ASSETS_DIR = Path(__file__).parent / "assets"
LOGO_LIGHT = (_ASSETS_DIR / "logo.svg").read_text()        # traits noirs — fond clair
LOGO_DARK = (_ASSETS_DIR / "logo_white.svg").read_text()   # traits blancs — fond sombre/coloré

# Configuration de la page
st.set_page_config(
    page_title="EIOPA Monitoring Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Instance hébergée (ex. Streamlit Community Cloud) : disque éphémère, donc
# aucune écriture faite ici ne survit à un redémarrage/redeploy. La donnée
# de production est ingérée en local puis poussée sur git — voir le README,
# section "Déploiement". Ce flag se règle via les Secrets de l'app hébergée
# (jamais commité), absent = False par défaut pour un usage local normal.
# st.secrets lève une exception (pas juste une valeur manquante) tant qu'aucun
# fichier secrets.toml n'existe du tout — normal en local, à absorber ici.
try:
    READONLY_DASHBOARD = st.secrets.get("READONLY_DASHBOARD", False)
except Exception:
    READONLY_DASHBOARD = False

# ---------------------------------------------------------------------------
# Système visuel — tokens de palette (clair/sombre), hero, stat tiles.
# Couleurs calées sur la palette catégorielle/statut du design system data-viz
# (slot 1 bleu = accent/série "actuelle", slot 2 orange = série "comparaison").
# ---------------------------------------------------------------------------
PALETTE = {
    "accent":       {"light": "#2a78d6", "dark": "#3987e5"},  # slot 1 — série actuelle/base
    "accent_2":     {"light": "#eb6834", "dark": "#d95926"},  # slot 2 — série comparaison/précédente
}

st.markdown("""
<style>
    :root {
        --ink-primary: #0b0b0b;
        --ink-secondary: #52514e;
        --ink-muted: #898781;
        --surface-card: #fcfcfb;
        --border: rgba(11,11,11,0.10);
        --accent: #2a78d6;
        --accent-2: #eb6834;
        /* Palette statut — fixe, mêmes valeurs en clair et en sombre (contraste validé sur les deux surfaces) */
        --status-good: #0ca30c;
        --status-critical: #d03b3b;
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --ink-primary: #ffffff;
            --ink-secondary: #c3c2b7;
            --ink-muted: #898781;
            --surface-card: #1a1a19;
            --border: rgba(255,255,255,0.10);
            --accent: #3987e5;
            --accent-2: #d95926;
        }
    }

    /* Bandeau hero — surface neutre + liseré d'accent, pas de fond bleu plein
       (trop tranché sur fond sombre) */
    .eiopa-hero {
        background: var(--surface-card);
        border: 1px solid var(--border);
        border-left: 5px solid var(--accent);
        border-radius: 14px;
        padding: 22px 28px;
        margin-bottom: 1.75rem;
        color: var(--ink-primary);
    }
    .eiopa-hero .eiopa-hero-title {
        margin: 0;
        font-size: 1.55rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        color: var(--ink-primary);
    }
    .eiopa-hero .eiopa-hero-sub {
        margin: 6px 0 0;
        font-size: 0.92rem;
        color: var(--ink-secondary);
    }

    /* Stat tiles */
    .stat-tile {
        background: var(--surface-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 14px 16px;
        height: 100%;
    }
    .stat-tile .stat-label {
        font-size: 0.74rem;
        color: var(--ink-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        font-weight: 600;
        margin: 0 0 4px;
    }
    .stat-tile .stat-value {
        font-size: 1.55rem;
        font-weight: 700;
        color: var(--ink-primary);
        font-variant-numeric: tabular-nums;
        line-height: 1.2;
    }
    .stat-tile .stat-delta {
        font-size: 0.8rem;
        color: var(--ink-secondary);
        font-variant-numeric: tabular-nums;
        margin-top: 2px;
    }
    .stat-tile .stat-delta.up { color: var(--status-good); }
    .stat-tile .stat-delta.down { color: var(--status-critical); }

    /* Navigation sidebar — rows au lieu de boutons radio nus */
    div[data-testid="stRadio"] > div[role="radiogroup"] { gap: 2px; }
    div[data-testid="stRadio"] label {
        padding: 6px 10px;
        border-radius: 8px;
        transition: background-color 0.15s ease;
    }
    div[data-testid="stRadio"] label:hover {
        background-color: var(--border);
    }

    /* Logo SSA Analytics */
    /* Logo réel ~2.34:1 (large et bas) depuis son viewBox recentré — largeur
       calée sur ce ratio pour ne pas l'écraser dans une boîte carrée. */
    .eiopa-logo-hero { height: 72px; width: 168px; flex-shrink: 0; }
    .eiopa-logo-hero svg { height: 100%; width: 100%; display: block; }

    .eiopa-brand-credit {
        display: flex;
        align-items: center;
        gap: 10px;
        opacity: 0.85;
    }
    .eiopa-brand-credit .eiopa-logo-footer { height: 32px; width: 75px; flex-shrink: 0; }
    .eiopa-brand-credit .eiopa-logo-footer svg { height: 100%; width: 100%; display: block; }
    .eiopa-brand-credit span { font-size: 0.78rem; color: var(--ink-secondary); }

    /* Variante du logo affichée selon le mode — une seule des deux existe
       dans le DOM à la fois visuellement, l'autre est masquée. */
    .eiopa-logo-dark-only { display: none; }
    @media (prefers-color-scheme: dark) {
        .eiopa-logo-light-only { display: none; }
        .eiopa-logo-dark-only { display: block; }
    }
</style>
""", unsafe_allow_html=True)


def render_hero(title: str, subtitle: str = ""):
    """Bandeau d'en-tête de marque, affiché une fois en haut du dashboard.

    Surface neutre (adapte au mode clair/sombre), donc le logo bascule lui
    aussi entre ses deux variantes selon le mode actif.
    """
    st.markdown(f"""
    <div class="eiopa-hero" style="display:flex; align-items:center; gap:20px;">
        <div class="eiopa-logo-hero eiopa-logo-light-only">{LOGO_LIGHT}</div>
        <div class="eiopa-logo-hero eiopa-logo-dark-only">{LOGO_DARK}</div>
        <div>
            <p class="eiopa-hero-title">{title}</p>
            {f'<p class="eiopa-hero-sub">{subtitle}</p>' if subtitle else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_brand_credit():
    """Crédit 'Propulsé par SSA Analytics' avec logo adapté au mode clair/sombre actif."""
    st.markdown(f"""
    <div class="eiopa-brand-credit">
        <div class="eiopa-logo-footer eiopa-logo-light-only">{LOGO_LIGHT}</div>
        <div class="eiopa-logo-footer eiopa-logo-dark-only">{LOGO_DARK}</div>
        <span>Propulsé par SSA Analytics</span>
    </div>
    """, unsafe_allow_html=True)


def render_stat_tile(label: str, value: str, delta: str = "", delta_direction: str = ""):
    """
    Carte de métrique (valeur + delta optionnel), remplace st.metric pour un
    rendu de marque. delta_direction: 'up' (vert), 'down' (rouge), ou '' (neutre).
    """
    delta_class = f" {delta_direction}" if delta_direction in ("up", "down") else ""
    st.markdown(f"""
    <div class="stat-tile">
        <p class="stat-label">{label}</p>
        <p class="stat-value">{value}</p>
        {f'<p class="stat-delta{delta_class}">{delta}</p>' if delta else ''}
    </div>
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


# Marge/police communes — le reste du chrome (fond, grille, texte) suit le
# thème actif via st.plotly_chart(..., theme="streamlit").
_CHART_LAYOUT = dict(
    hovermode='x unified',
    height=380,
    margin=dict(l=10, r=10, t=40, b=10),
    font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif"),
)


def plot_yield_curve(rates: dict, title: str = "Courbe des taux"):
    """Affiche la courbe des taux — série unique, identité bleu (slot 1)."""
    maturities = sorted(rates.keys())
    values = [rates[m] * 100 for m in maturities]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=maturities,
        y=values,
        mode='lines+markers',
        name='Taux',
        line=dict(color=PALETTE["accent"]["light"], width=2),
        marker=dict(size=8),
        hovertemplate="%{x}Y : %{y:.2f}%<extra></extra>",
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Maturité (années)",
        yaxis_title="Taux (%)",
        showlegend=False,
        **_CHART_LAYOUT,
    )

    return fig


def plot_time_series(df: pd.DataFrame, maturity: int, title: str = None):
    """Affiche une série temporelle — même identité que la courbe actuelle (bleu)."""
    if title is None:
        title = f"Évolution du taux {maturity}Y"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['reference_date'],
        y=df['rate'] * 100,
        mode='lines',
        name=f'Taux {maturity}Y',
        line=dict(color=PALETTE["accent"]["light"], width=2),
        hovertemplate="%{x|%d/%m/%Y} : %{y:.2f}%<extra></extra>",
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Taux (%)",
        showlegend=False,
        **_CHART_LAYOUT,
    )

    return fig


def plot_comparison(current_rates: dict, previous_rates: dict):
    """Compare deux courbes de taux — actuel (bleu, slot 1) vs précédent (orange, slot 2)."""
    maturities = sorted(current_rates.keys())

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=maturities,
        y=[current_rates[m] * 100 for m in maturities],
        mode='lines+markers',
        name='Actuel',
        line=dict(color=PALETTE["accent"]["light"], width=2),
        marker=dict(size=8),
        hovertemplate="%{x}Y : %{y:.2f}%<extra>Actuel</extra>",
    ))

    fig.add_trace(go.Scatter(
        x=maturities,
        y=[previous_rates.get(m, 0) * 100 for m in maturities],
        mode='lines+markers',
        name='Précédent',
        line=dict(color=PALETTE["accent_2"]["light"], width=2, dash='dash'),
        marker=dict(size=8),
        hovertemplate="%{x}Y : %{y:.2f}%<extra>Précédent</extra>",
    ))

    fig.update_layout(
        title="Comparaison des courbes",
        xaxis_title="Maturité (années)",
        yaxis_title="Taux (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **_CHART_LAYOUT,
    )

    return fig


def main():
    df = load_historical_data()
    if not df.empty:
        latest = df['reference_date'].max().strftime('%d/%m/%Y')
        subtitle = f"Solvency II · Taux sans risque EIOPA · Dernière clôture : {latest}"
    else:
        subtitle = "Solvency II · Taux sans risque EIOPA"

    # Navigation native (remplace le radio du sidebar par les onglets/pages
    # gérés par Streamlit lui-même — état actif visible, icônes dédiées,
    # URL par page).
    pg = st.navigation([
        st.Page(show_overview, title="Vue d'ensemble", icon="📈", url_path="vue-d-ensemble", default=True),
        st.Page(show_update_page, title="Mise à jour", icon="🔄", url_path="mise-a-jour"),
        st.Page(show_historical_page, title="Historique", icon="📜", url_path="historique"),
        st.Page(show_analysis_page, title="Analyse", icon="📊", url_path="analyse"),
        st.Page(show_export_page, title="Export", icon="📤", url_path="export"),
    ])

    with st.sidebar:
        st.markdown("---")
        st.caption("⚙️ Configuration")
        st.markdown(f"**Pays surveillé** : {TARGET_COUNTRY}")
        st.markdown(f"**Maturités** : {', '.join(map(str, TARGET_MATURITIES))}Y")

        st.markdown("---")
        if READONLY_DASHBOARD:
            st.caption("🔒 Instance hébergée — lecture seule")
        else:
            st.caption("💻 Instance locale — production")

        st.markdown("---")
        render_brand_credit()

    render_hero("EIOPA Risk-Free Rates Monitoring", subtitle)
    pg.run()


def show_overview():
    """Page de vue d'ensemble"""
    st.header("Vue d'ensemble")

    analyzer = get_analyzer()

    if analyzer.historical_data.empty:
        st.warning("⚠️ Aucune donnée disponible. Effectuez une première mise à jour.")
        return

    # Dernières données (+ mois précédent pour la variation M/M des stat tiles)
    history = analyzer.historical_data
    latest_row = history.iloc[-1]
    previous_row = history.iloc[-2] if len(history) >= 2 else None
    latest_date = latest_row['reference_date']

    st.caption(f"📅 Dernière mise à jour : {latest_date.strftime('%d/%m/%Y')}")

    # Métriques principales — une par maturité suivie (config.TARGET_MATURITIES), plus VA.
    # Delta M/M : vert en hausse, rouge en baisse (demande explicite —
    # remplace le rendu neutre initial).
    columns = st.columns(len(TARGET_MATURITIES) + 1)

    for col, maturity in zip(columns[:-1], TARGET_MATURITIES):
        with col:
            col_name = f'rate_{maturity}y'
            if col_name in latest_row and pd.notna(latest_row[col_name]):
                delta, direction = "", ""
                if previous_row is not None and pd.notna(previous_row.get(col_name)):
                    change_bps = (latest_row[col_name] - previous_row[col_name]) * 10000
                    direction = "up" if change_bps >= 0 else "down"
                    arrow = "▲" if change_bps >= 0 else "▼"
                    delta = f"{arrow} {change_bps:+.1f} bps (M/M)"
                render_stat_tile(f"Taux {maturity}Y", f"{latest_row[col_name] * 100:.2f}%", delta, direction)

    with columns[-1]:
        va = latest_row['va'] * 100 if pd.notna(latest_row['va']) else None
        render_stat_tile("VA", f"{va:.2f}%" if va is not None else "N/A")

    # Courbe actuelle
    st.subheader("📈 Courbe des taux actuelle")
    
    rates = {}
    for maturity in TARGET_MATURITIES:
        col_name = f'rate_{maturity}y'
        if col_name in latest_row and pd.notna(latest_row[col_name]):
            rates[maturity] = float(latest_row[col_name])
    
    if rates:
        fig = plot_yield_curve(rates)
        st.plotly_chart(fig, width='stretch')
    
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
        st.plotly_chart(fig, width='stretch')


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
    st.dataframe(df_display, width='stretch', hide_index=True)
 
    # ------------------------------------------------------------------
    # 4. Sélection des dates à télécharger — désactivé sur instance hébergée :
    #    toute ingestion faite ici serait perdue au prochain redémarrage.
    # ------------------------------------------------------------------
    if READONLY_DASHBOARD:
        st.warning(
            "🔒 Cette instance est en lecture seule. L'ingestion de nouvelles "
            "données se fait en local (`streamlit run app.py` ou `python "
            "main.py`), puis `historical.db` est poussé sur git — voir le "
            "README, section \"Déploiement\". Un téléchargement lancé ici "
            "serait perdu au prochain redémarrage de l'instance."
        )
        return

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
        render_stat_tile("Nombre d'enregistrements", str(len(df)))

    with col2:
        min_date = df['reference_date'].min()
        render_stat_tile("Première date", min_date.strftime('%d/%m/%Y'))

    with col3:
        max_date = df['reference_date'].max()
        render_stat_tile("Dernière date", max_date.strftime('%d/%m/%Y'))
    
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
        st.plotly_chart(fig, width='stretch')
        
        # Tableau de données
        with st.expander("📋 Voir les données"):
            display_df = ts.copy()
            display_df['rate'] = display_df['rate'].apply(lambda x: f"{x*100:.4f}%")
            st.dataframe(display_df, width='stretch')
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
    st.plotly_chart(fig, width='stretch')
    
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
    st.dataframe(df_variations, width='stretch', hide_index=True)


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