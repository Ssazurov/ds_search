"""GAR-стиль для Streamlit-админки ds_search (issue #504).

Светлая тема по умолчанию задаётся в .streamlit/config.toml; тёмная —
встроенным переключателем Streamlit (Settings). Здесь только шрифты IBM Plex
(как в gar-admin-ui) и нейтральные правила, работающие в обеих темах.
"""
import streamlit as st

_FONT_FACES = """
@font-face { font-family: 'IBM Plex Sans'; font-weight: 400; font-display: swap;
  src: url(/app/static/fonts/ibm-plex-sans-cyrillic-400.woff2) format('woff2');
  unicode-range: U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116; }
@font-face { font-family: 'IBM Plex Sans'; font-weight: 400; font-display: swap;
  src: url(/app/static/fonts/ibm-plex-sans-latin-400.woff2) format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+2000-206F; }
@font-face { font-family: 'IBM Plex Sans'; font-weight: 500; font-display: swap;
  src: url(/app/static/fonts/ibm-plex-sans-cyrillic-500.woff2) format('woff2');
  unicode-range: U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116; }
@font-face { font-family: 'IBM Plex Sans'; font-weight: 500; font-display: swap;
  src: url(/app/static/fonts/ibm-plex-sans-latin-500.woff2) format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+2000-206F; }
@font-face { font-family: 'IBM Plex Sans'; font-weight: 600; font-display: swap;
  src: url(/app/static/fonts/ibm-plex-sans-cyrillic-600.woff2) format('woff2');
  unicode-range: U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116; }
@font-face { font-family: 'IBM Plex Sans'; font-weight: 600; font-display: swap;
  src: url(/app/static/fonts/ibm-plex-sans-latin-600.woff2) format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+2000-206F; }
"""

_RULES = """
html, body, [data-testid="stApp"], [data-testid="stSidebar"] {
  font-family: 'IBM Plex Sans', system-ui, sans-serif; }
h1, h2, h3 { font-weight: 600; letter-spacing: -0.01em; }
div.block-container { padding-top: 2.5rem !important; }
[data-testid="stExpander"], [data-testid="stMetric"] {
  border: 1px solid rgba(128,128,128,0.25); border-radius: 8px; }
/* ряды кнопок действий под таблицами: вправо, равные малые промежутки */
[class*="st-key-actions_"] [data-testid="stHorizontalBlock"] {
  justify-content: flex-end; gap: 0.5rem !important; flex-wrap: wrap; }
[class*="st-key-actions_"] [data-testid="stColumn"] {
  flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; }
[class*="st-key-actions_"] button { white-space: nowrap; }
"""


# Боковое меню — как Sidebar.tsx в gar-admin-ui: 212px, правый бордер,
# пункты 13.5px без маркеров, активный — фон + синяя полоса слева.
_SIDEBAR = """
[data-testid="stSidebar"] { width: 212px !important; min-width: 212px !important; }
[data-testid="stSidebar"] > div:first-child { width: 212px !important; }
[data-testid="stSidebar"] { border-right: 1px solid rgba(128,128,128,0.25); }
[data-testid="stSidebar"] [data-testid="stSidebarHeader"] { display: none; }
[data-testid="stSidebar"] .gar-brand { display: flex; align-items: center; gap: 8px;
  padding: 26px 10px 20px; }
[data-testid="stSidebar"] .gar-brand b { font-size: 14px; font-weight: 600; }
[data-testid="stSidebar"] .gar-brand span { font-size: 11px; opacity: 0.6; }
[data-testid="stSidebar"] .gar-group { font-size: 10.5px; text-transform: uppercase;
  letter-spacing: 0.3px; opacity: 0.6; padding: 14px 10px 4px; }
[data-testid="stSidebar"] [data-testid="stRadio"] > label { display: none; }
[data-testid="stSidebar"] [role="radiogroup"] { gap: 2px; }
[data-testid="stSidebar"] [role="radiogroup"] > label {
  padding: 9px 10px; margin: 0; border-radius: 6px; border-left: 2px solid transparent;
  font-size: 13.5px; opacity: 0.75; transition: background .15s; }
[data-testid="stSidebar"] [role="radiogroup"] > label:hover {
  background: rgba(128,128,128,0.12); opacity: 1; }
[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {
  background: rgba(59,111,209,0.12); border-left-color: #3b6fd1; opacity: 1; font-weight: 600; }
[data-testid="stSidebar"] [role="radiogroup"] [data-baseweb="radio"] { display: none; }
"""


# Компоненты — по gar-admin-ui: Card (panel, border, radius 8px, padding 18/20),
# Button (primary — синяя заливка; ghost — рамка; md 13px, sm 12px, radius 6px),
# заголовки 14px semibold, подписи 12px.
_COMPONENTS = """
html, body, [data-testid="stApp"] { font-size: 14px; }
div.block-container { padding: 2.5rem 1.75rem 3rem !important; max-width: none !important; }
h1 { font-size: 20px !important; }
h2 { font-size: 16px !important; }
h3 { font-size: 14px !important; }
[data-testid="stMarkdownContainer"] p, [data-testid="stCaptionContainer"] { font-size: 13px; }
[data-testid="stCaptionContainer"] { opacity: 0.7; }
/* Card: контейнеры с рамкой */
[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] { gap: 0.75rem; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > div[data-testid="stVerticalBlock"]) { border-radius: 8px !important; }
/* Button primary / ghost (sm по умолчанию) */
[data-testid="stBaseButton-primary"], button[kind="primary"] {
  background: #3b6fd1 !important; color: #fff !important; border: none !important;
  border-radius: 6px !important; font-weight: 500 !important; font-size: 13px !important;
  padding: 7px 14px !important; min-height: 0 !important; }
[data-testid="stBaseButton-secondary"], button[kind="secondary"] {
  background: transparent !important; border: 1px solid rgba(128,128,128,0.35) !important;
  border-radius: 6px !important; font-weight: 500 !important; font-size: 13px !important;
  padding: 7px 14px !important; min-height: 0 !important; }
[data-testid="stBaseButton-primary"]:hover, button[kind="primary"]:hover { opacity: 0.9; }
[data-testid="stBaseButton-primary"]:disabled, [data-testid="stBaseButton-secondary"]:disabled { opacity: 0.5; }
/* Поля ввода */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {
  border-radius: 6px !important; font-size: 13px !important; }
[data-testid="stTextArea"] textarea, [data-testid="stNumberInput"] input { font-size: 13px !important; }
/* Вкладки st.tabs */
[data-baseweb="tab-list"] { gap: 4px; }
[data-baseweb="tab"] { font-size: 13px !important; font-weight: 500 !important; padding: 8px 12px !important; }
[data-baseweb="tab-highlight"] { background: #3b6fd1 !important; }
/* Таблицы, метрики, алерты */
[data-testid="stDataFrame"], [data-testid="stTable"] { border-radius: 8px; }
[data-testid="stMetricValue"] { font-weight: 600; font-size: 22px !important; }
[data-testid="stMetricLabel"] { font-size: 12px !important; opacity: 0.7; }
[data-testid="stAlert"] { border-radius: 6px; font-size: 13px; }
[data-testid="stExpander"] summary { font-size: 13px; font-weight: 500; }
"""


# Палитра и компоненты 1:1 с gar-admin-ui (app/globals.css, ui/Button|Card|Field).
_GAR = """
:root { --bg:#f4f5f7; --panel:#ffffff; --panel2:#eef0f4; --border:#dde1e8; --text:#1a2030;
  --sub:#596178; --dim:#8991a3; --blue:#3b6fd1; --green:#1f9d6c; --amber:#b9791f; --red:#c73b45; }
[data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background: var(--bg) !important; color: var(--text); }
[data-testid="stHeader"] { background: var(--bg) !important; height: 52px;
  border-bottom: 1px solid var(--border); }
[data-testid="stSidebar"] { background: var(--bg) !important; border-right: 1px solid var(--border) !important; }
[data-testid="stSidebar"] .gar-brand span, [data-testid="stSidebar"] .gar-group { color: var(--dim); opacity: 1; }
[data-testid="stSidebar"] [role="radiogroup"] > label { color: var(--sub); opacity: 1; }
[data-testid="stSidebar"] [role="radiogroup"] > label:hover { background: var(--panel); color: var(--text); }
[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {
  background: var(--panel2); border-left-color: var(--blue); color: var(--text); }
/* Card */
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > div[data-testid="stVerticalBlock"]),
[data-testid="stExpander"], [data-testid="stMetric"] {
  background: var(--panel) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; }
div[data-testid="stVerticalBlockBorderWrapper"] > div { padding: 18px 20px; }
[data-testid="stExpander"] details, [data-testid="stExpander"] summary { background: transparent !important; }
[data-testid="stMetric"] { padding: 18px 20px; }
/* Button */
[data-testid="stBaseButton-primary"], button[kind="primary"] { background: var(--blue) !important;
  color: #ffffff !important; padding: 8px 14px !important; line-height: 1 !important; }
[data-testid="stBaseButton-secondary"], button[kind="secondary"] { background: transparent !important;
  border: 1px solid var(--border) !important; color: var(--text) !important; padding: 8px 14px !important; line-height: 1 !important; }
[data-testid="stBaseButton-secondary"]:hover { border-color: var(--sub) !important; }
/* Field */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"], [data-baseweb="base-input"] {
  background: var(--panel) !important; border: 1px solid var(--border) !important; color: var(--text) !important; }
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within, [data-baseweb="textarea"]:focus-within {
  box-shadow: 0 0 0 2px var(--blue) !important; }
input, textarea { color: var(--text) !important; }
/* Tabs */
[data-baseweb="tab-list"] { border-bottom: 1px solid var(--border); }
[data-baseweb="tab"] { color: var(--sub) !important; background: transparent !important; }
[aria-selected="true"][data-baseweb="tab"] { color: var(--text) !important; }
[data-baseweb="tab-highlight"] { background: var(--blue) !important; }
[data-baseweb="tab-border"] { background: var(--border) !important; }
/* Текст */
[data-testid="stCaptionContainer"] { color: var(--dim) !important; opacity: 1 !important; font-size: 12px !important; }
[data-testid="stMetricLabel"] { color: var(--sub); opacity: 1 !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 8px; }
[data-testid="stAlert"] { background: var(--panel2) !important; border: 1px solid var(--border); }
hr { border-color: var(--border) !important; }
"""


def inject_theme() -> None:
    """Подключает шрифты IBM Plex и базовые правила. Вызывать после st.set_page_config."""
    st.markdown(f"<style>{_FONT_FACES}{_RULES}{_SIDEBAR}{_COMPONENTS}{_GAR}{_NAV}</style>", unsafe_allow_html=True)



def sidebar_brand() -> None:
    """Шапка бокового меню: логотип-бренд как в GAR console."""
    st.sidebar.markdown(
        '<div class="gar-brand"><b>Солнечный мир</b></div>',
        unsafe_allow_html=True,
    )


_NAV = """
[class*="st-key-nav"] { margin: 0 !important; }
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding: 0 12px; }
[class*="st-key-nav"] button { width: 100%; justify-content: flex-start !important; text-align: left;
  background: transparent !important; border: none !important; border-left: 2px solid transparent !important;
  border-radius: 6px !important; padding: 9px 10px !important; min-height: 0 !important;
  font-size: 13.5px !important; font-weight: 400 !important; color: var(--sub) !important; box-shadow: none !important; }
[class*="st-key-nav"] button p { font-size: 13.5px !important; }
[class*="st-key-nav"] button:hover { background: var(--panel2) !important; color: var(--text) !important; }
[class*="st-key-navon"] button { background: var(--panel2) !important; color: var(--text) !important;
  border-left-color: var(--blue) !important; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 2px; }
.gar-topbar { position: fixed; top: 0; left: 212px; right: 0; height: 52px; z-index: 999991;
  display: flex; align-items: center; padding: 0 20px; pointer-events: none;
  font-size: 13px; color: var(--sub); }
.gar-topbar b { font-weight: 500; color: var(--text); margin-left: 4px; }
div.block-container { padding-top: 74px !important; }
"""


def topbar(page: str) -> None:
    """Хлебные крошки как Topbar.tsx в gar-admin-ui: «Солнечный мир / Раздел»."""
    st.markdown(f'<div class="gar-topbar">Солнечный мир&nbsp;/ <b>{page}</b></div>', unsafe_allow_html=True)
