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


def inject_theme() -> None:
    """Подключает шрифты IBM Plex и базовые правила. Вызывать после st.set_page_config."""
    st.markdown(f"<style>{_FONT_FACES}{_RULES}{_SIDEBAR}</style>", unsafe_allow_html=True)


def sidebar_brand() -> None:
    """Шапка бокового меню: логотип-бренд как в GAR console."""
    st.sidebar.markdown(
        '<div class="gar-brand"><b>Солнечный мир</b><span>администрирование</span></div>'
        '<div class="gar-group">Разделы</div>',
        unsafe_allow_html=True,
    )
