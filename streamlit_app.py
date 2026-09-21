import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="KickAdvisor",
    page_icon="K",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from daily_predictions import run_analysis
from kickbase_api.league import get_leagues_infos
from kickbase_api.user import login


if "theme" not in st.session_state:
    st.session_state.theme = "light"
if "token" not in st.session_state:
    st.session_state.token = None
if "leagues" not in st.session_state:
    st.session_state.leagues = []
if "results" not in st.session_state:
    st.session_state.results = None


IS_DARK = st.session_state.theme == "dark"


def toggle_theme():
    st.session_state.theme = "dark" if IS_DARK is False else "light"


def clear_session():
    st.session_state.token = None
    st.session_state.leagues = []
    st.session_state.results = None


def format_number(value):
    """Format numeric table values with German-style separators."""
    if pd.isna(value):
        return ""
    if float(value).is_integer():
        return f"{value:,.0f}".replace(",", ".")
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_table(dataframe):
    numeric_columns = dataframe.select_dtypes(include="number").columns
    return dataframe.style.format(
        {column: format_number for column in numeric_columns}, na_rep=""
    )


def render_player_alerts(dataframe):
    change_column = "predicted_mv_target"
    if change_column not in dataframe.columns:
        return

    changes = pd.to_numeric(dataframe[change_column], errors="coerce")
    player_column = "last_name" if "last_name" in dataframe.columns else "player_id"
    negative_players = dataframe.loc[changes < 0, [player_column, change_column]]
    high_growth_players = dataframe.loc[
        changes >= 300_000, [player_column, change_column]
    ]

    if not negative_players.empty:
        st.markdown("#### Predicted value decrease warning")
        for _, player in negative_players.iterrows():
            st.error(
                f"{player[player_column]}: "
                f"{format_number(player[change_column])}"
            )

    if not high_growth_players.empty:
        st.markdown("#### Strong predicted value increase")
        for _, player in high_growth_players.iterrows():
            st.success(
                f"{player[player_column]}: "
                f"+{format_number(player[change_column])}"
            )


background = "#09090b" if IS_DARK else "#ffffff"
background_subtle = "#0c0c0f" if IS_DARK else "#f9fafb"
card = "#0c0c0f" if IS_DARK else "#ffffff"
border = "#1e1e24" if IS_DARK else "#e4e4e7"
text = "#fafafa" if IS_DARK else "#09090b"
muted = "#a1a1aa" if IS_DARK else "#71717a"

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
    :root {{
        --bg: {background};
        --bg-subtle: {background_subtle};
        --card: {card};
        --border: {border};
        --text: {text};
        --muted: {muted};
        --accent: #2563eb;
    }}
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"],
    .main, .block-container, section[data-testid="stMain"] {{
        background: var(--bg) !important;
        color: var(--text) !important;
        font-family: 'DM Sans', sans-serif !important;
    }}
    .block-container {{ max-width: 1360px; padding: 2rem 2.5rem 3rem; }}
    header[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"],
    [data-testid="stDecoration"], [data-testid="stStatusWidget"], .stDeployButton {{
        display: none !important;
    }}
    .brand {{ display: flex; align-items: baseline; gap: 0.75rem; margin-bottom: 0.2rem; }}
    .brand-name {{ color: var(--text); font-size: 2rem; font-weight: 700; letter-spacing: -0.04em; }}
    .brand-mark {{ color: var(--accent); font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; font-weight: 600; }}
    .subtitle {{ color: var(--muted); font-size: 0.95rem; margin-bottom: 2rem; }}
    .panel {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1.25rem; }}
    .metric-label {{ color: var(--muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; }}
    .metric-value {{ color: var(--text); font-family: 'JetBrains Mono', monospace; font-size: 1.35rem; font-weight: 600; margin-top: 0.35rem; }}
    button[data-baseweb="tab"] {{ color: var(--muted) !important; }}
    button[data-baseweb="tab"][aria-selected="true"] {{ color: var(--text) !important; }}
    [data-testid="stDataFrame"] {{ border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }}
    </style>
    """,
    unsafe_allow_html=True,
)


header_left, header_right = st.columns([8, 1])
with header_left:
    st.markdown(
        '<div class="brand"><span class="brand-name">KickAdvisor</span>'
        '<span class="brand-mark">DAILY PREDICTIONS</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="subtitle">Market value signals and squad recommendations for your Kickbase league.</div>',
        unsafe_allow_html=True,
    )
with header_right:
    st.button("Dark mode" if not IS_DARK else "Light mode", on_click=toggle_theme)


if not st.session_state.token:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.subheader("Sign in to Kickbase")
    st.caption("Your credentials are used for this session only and are not stored.")
    with st.form("login_form"):
        username = st.text_input("Username", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)

    if submitted:
        if not username or not password:
            st.error("Enter both your username and password.")
        else:
            with st.spinner("Signing in and loading your leagues..."):
                try:
                    token = login(username, password)
                    leagues = get_leagues_infos(token)
                    if not token:
                        raise RuntimeError("Kickbase did not return an authentication token.")
                    if not leagues:
                        raise RuntimeError("No Kickbase leagues were found for this account.")
                    st.session_state.token = token
                    st.session_state.leagues = leagues
                    st.rerun()
                except Exception as error:
                    st.error(f"Sign-in failed: {error}")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()


control_left, control_middle, control_right = st.columns([3, 3, 1])
with control_left:
    league_names = [league["name"] for league in st.session_state.leagues]
    selected_name = st.selectbox("League", league_names)
with control_middle:
    st.write("")
    st.write("")
    run_clicked = st.button("Run Analysis", type="primary", use_container_width=True)
with control_right:
    st.write("")
    st.write("")
    st.button("Sign out", on_click=clear_session, use_container_width=True)


if run_clicked:
    selected_league = next(
        league for league in st.session_state.leagues if league["name"] == selected_name
    )
    with st.spinner("Running analysis. Data refresh and model training may take several minutes..."):
        try:
            st.session_state.results = run_analysis(
                st.session_state.token, selected_league["id"]
            )
            st.success(f"Analysis completed for {selected_name}.")
        except Exception as error:
            st.error(f"Analysis failed: {error}")


results = st.session_state.results
if results is None:
    st.info("Select a league and run the analysis to see recommendations.")
    st.stop()


st.subheader("Model evaluation")
metric_columns = st.columns(4)
for column, (label, value) in zip(metric_columns, results["metrics"].items()):
    formatted_value = f"{value:.2f}%" if label == "Signs correct" else f"{value:,.2f}"
    with column:
        st.markdown(
            f'<div class="panel"><div class="metric-label">{label}</div>'
            f'<div class="metric-value">{formatted_value}</div></div>',
            unsafe_allow_html=True,
        )

st.subheader("Recommendations")
tab_budgets, tab_market, tab_squad = st.tabs(
    ["Manager Budgets", "Market Recommendations", "Squad Recommendations"]
)
with tab_budgets:
    st.dataframe(
        format_table(results["manager_budgets"]),
        use_container_width=True,
        hide_index=True,
    )
with tab_market:
    st.dataframe(
        format_table(results["market_recommendations"]),
        use_container_width=True,
        hide_index=True,
    )
    render_player_alerts(results["market_recommendations"])
with tab_squad:
    st.dataframe(
        format_table(results["squad_recommendations"]),
        use_container_width=True,
        hide_index=True,
    )
    render_player_alerts(results["squad_recommendations"])
