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


if "token" not in st.session_state:
    st.session_state.token = None
if "leagues" not in st.session_state:
    st.session_state.leagues = []
if "results" not in st.session_state:
    st.session_state.results = None


def clear_session():
    st.session_state.token = None
    st.session_state.leagues = []
    st.session_state.results = None


def format_number(value):
    """Round numeric table values and format them with German separators."""
    if pd.isna(value):
        return ""
    return f"{value:,.0f}".replace(",", ".")


def format_table(dataframe):
    numeric_columns = dataframe.select_dtypes(include="number").columns
    return dataframe.style.format(
        {column: format_number for column in numeric_columns}, na_rep=""
    )


def default_display_table(dataframe):
    columns = [
        "last_name",
        "mv",
        "predicted_mv_target",
        "hours_to_exp",
    ]
    visible_columns = [column for column in columns if column in dataframe.columns]
    return dataframe[visible_columns]


def update_select_all(table_key, row_count):
    row_keys = [f"{table_key}_row_{row_index}" for row_index in range(row_count)]
    st.session_state[f"{table_key}_select_all"] = all(
        st.session_state.get(row_key, True) for row_key in row_keys
    )


def set_all_rows(table_key, row_count, selected):
    st.session_state[f"{table_key}_selection"] = {
        row_index: selected for row_index in range(row_count)
    }
    st.session_state[f"{table_key}_editor_version"] = (
        st.session_state.get(f"{table_key}_editor_version", 0) + 1
    )


def render_selectable_table(dataframe, table_key):
    display_data = default_display_table(dataframe).reset_index(drop=True)
    row_count = len(display_data)
    selection_key = f"{table_key}_selection"
    editor_version_key = f"{table_key}_editor_version"
    signature_key = f"{table_key}_selection_signature"
    signature = tuple(
        tuple(str(value) for value in row)
        for row in display_data.astype(str).itertuples(index=False, name=None)
    )

    if st.session_state.get(signature_key) != signature:
        st.session_state[selection_key] = {
            row_index: True for row_index in range(row_count)
        }
        st.session_state[signature_key] = signature
        st.session_state[editor_version_key] = (
            st.session_state.get(editor_version_key, 0) + 1
        )
    if editor_version_key not in st.session_state:
        st.session_state[editor_version_key] = 0

    sum_column, count_column, average_column = st.columns(3)
    sum_placeholder = sum_column.empty()
    count_placeholder = count_column.empty()
    average_placeholder = average_column.empty()

    select_column, deselect_column = st.columns(2)
    with select_column:
        st.button(
            "Select all",
            key=f"{table_key}_select_all_button",
            on_click=set_all_rows,
            args=(table_key, row_count, True),
            use_container_width=True,
        )
    with deselect_column:
        st.button(
            "Deselect all",
            key=f"{table_key}_deselect_all_button",
            on_click=set_all_rows,
            args=(table_key, row_count, False),
            use_container_width=True,
        )

    table_data = display_data.copy()
    for column in table_data.select_dtypes(include="number").columns:
        table_data[column] = table_data[column].map(format_number)
    table_data.insert(
        0,
        "Use",
        [
            st.session_state[selection_key].get(row_index, True)
            for row_index in range(row_count)
        ],
    )

    editor_key = f"{table_key}_editor_{st.session_state[editor_version_key]}"
    edited_data = st.data_editor(
        table_data,
        key=editor_key,
        hide_index=True,
        use_container_width=True,
        disabled=[column for column in table_data.columns if column != "Use"],
        column_config={
            "Use": st.column_config.CheckboxColumn("Use", default=True),
        },
    )
    st.session_state[selection_key] = {
        row_index: bool(selected)
        for row_index, selected in enumerate(edited_data["Use"])
    }
    selected_values = [
        pd.to_numeric(row["predicted_mv_target"], errors="coerce")
        for row_index, (_, row) in enumerate(display_data.iterrows())
        if st.session_state[selection_key].get(row_index, True)
        and "predicted_mv_target" in row
    ]
    selected_series = pd.Series(selected_values, dtype="float64")
    selected_sum = selected_series.sum()
    selected_average = selected_series.mean()
    if pd.isna(selected_average):
        selected_average = 0
    selected_count = sum(
        st.session_state[selection_key].get(row_index, True)
        for row_index in range(row_count)
    )
    sum_placeholder.metric("Selected predicted MV change", format_number(selected_sum))
    count_placeholder.metric("Selected players", selected_count)
    average_placeholder.metric(
        "Average predicted MV change", format_number(selected_average)
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


background = "#ffffff"
background_subtle = "#f9fafb"
card = "#ffffff"
border = "#e4e4e7"
text = "#09090b"
muted = "#71717a"

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
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background: var(--card);
        border-color: var(--border) !important;
    }}
    @media (max-width: 640px) {{
        .block-container {{ padding: 1rem 0.75rem 2rem; }}
        .brand {{ align-items: flex-start; flex-direction: column; gap: 0.15rem; }}
        .brand-name {{ font-size: 1.65rem; }}
        .brand-mark {{ font-size: 0.68rem; }}
        .subtitle {{ font-size: 0.85rem; margin-bottom: 1rem; }}
        h1, h2, h3 {{ overflow-wrap: anywhere; }}
        [data-testid="stHorizontalBlock"] {{ gap: 0.5rem; }}
        [data-testid="stVerticalBlockBorderWrapper"] {{ padding: 0.75rem !important; }}
        [data-testid="stMetricValue"] {{ font-size: 1.25rem; }}
        button[data-baseweb="tab"] {{ padding: 0.45rem 0.5rem !important; font-size: 0.75rem !important; }}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


with st.container():
    st.markdown(
        '<div class="brand"><span class="brand-name">KickAdvisor</span>'
        '<span class="brand-mark">DAILY PREDICTIONS</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="subtitle">Market value signals and squad recommendations for your Kickbase league.</div>',
        unsafe_allow_html=True,
    )


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


with st.expander("Model evaluation", expanded=False):
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
    render_selectable_table(results["market_recommendations"], "market")
    render_player_alerts(results["market_recommendations"])
with tab_squad:
    render_selectable_table(results["squad_recommendations"], "squad")
    render_player_alerts(results["squad_recommendations"])
