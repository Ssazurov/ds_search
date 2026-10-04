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


def inject_theme() -> None:
    """Подключает шрифты IBM Plex и базовые правила. Вызывать после st.set_page_config."""
    st.markdown(f"<style>{_FONT_FACES}{_RULES}</style>", unsafe_allow_html=True)
