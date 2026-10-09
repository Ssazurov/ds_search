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
[class*="st-key-actions_left_"] [data-testid="stHorizontalBlock"] { justify-content: flex-start; }
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
.gar-topbar b { font-size: 20px; font-weight: 600; letter-spacing: -0.01em; color: var(--text); }
div.block-container { padding-top: 72px !important; }
/* Бренд слева, как пункты меню */
[data-testid="stSidebar"] .gar-brand { justify-content: flex-start !important; text-align: left; padding: 26px 10px 20px; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(.gar-brand) { text-align: left; }
[data-testid="stElementContainer"]:has(.srcleft-mark) { display: none; }
[data-testid="stElementContainer"]:has(.gar-topbar) { position: absolute; }
/* Источники: правая колонка занимает остаток, без переноса вниз */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .srcleft-mark) { flex-wrap: nowrap !important; }
[data-testid="stColumn"]:has(.srcleft-mark) + [data-testid="stColumn"] { flex: 1 1 0 !important; width: auto !important; min-width: 0 !important; }
/* Меню: текст пунктов слева */
[class*="st-key-nav"] button > div, [class*="st-key-nav"] button [data-testid="stMarkdownContainer"] {
  justify-content: flex-start !important; text-align: left !important; width: 100%; }
/* Пагинация: компактные кнопки в ряд */
.st-key-pgnums [data-testid="stHorizontalBlock"] { gap: 4px !important; justify-content: flex-start; flex-wrap: nowrap; }
.st-key-pgnums [data-testid="stColumn"] { flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; }
.st-key-pgnums button { min-width: 34px; height: 32px; min-height: 32px !important; padding: 0 8px !important;
  font-size: 13px !important; border-radius: 6px !important; }
.st-key-pgnums [data-testid="stBaseButton-primary"] { font-weight: 600 !important; }
.st-key-pgnums .pg-gap { color: var(--dim); padding: 0 2px; line-height: 32px; }
.st-key-pgsize { margin-left: 16px; }
.st-key-pgsize [data-testid="stButtonGroup"] { gap: 4px; }
.st-key-pgfoot { margin-top: 4px; }
.st-key-pgfoot [data-testid="stCaptionContainer"] { margin: 0; }
.st-key-pgfoot [data-testid="stButtonGroup"] { justify-content: flex-end; gap: 4px; }
.st-key-pgfoot [data-testid^="stBaseButton-segmented"] { min-width: 38px; padding: 4px 10px !important;
  font-size: 12px !important; border-radius: 6px !important; }
/* Список источников: компактные строки, текст слева */
[class*="st-key-pick_"] button { justify-content: flex-start !important; padding: 6px 12px !important; min-height: 32px !important; }
[class*="st-key-pick_"] button > div { justify-content: flex-start !important; width: 100%; text-align: left !important; }
[class*="st-key-pick_"] button p { font-size: 13px !important; }
.st-key-tabmain [data-testid="stBaseLinkButton-secondary"], .st-key-tabmain [data-testid="stBaseLinkButton-primary"] {
  min-height: 32px !important; padding: 6px 10px !important; border-radius: 6px !important; font-size: 13px !important; }

/* Все вкладки: подпись слева от поля (компактно по вертикали).
   Без подписи (collapsed) — исключены по ключам src_search, dp_sel_*. */
.st-key-tabmain [data-testid="stElementContainer"]:not([class*="st-key-src_search"]):not([class*="st-key-dp_sel_"]):not([class*="_limit"]) > :is([data-testid="stTextInput"], [data-testid="stSelectbox"], [data-testid="stNumberInput"], [data-testid="stTextArea"], [data-testid="stMultiSelect"], [data-testid="stDateInput"], [data-testid="stTimeInput"], [data-testid="stRadio"]) {
  display: grid !important; grid-template-columns: 180px minmax(0, 1fr); column-gap: 12px; align-items: center; }
.st-key-tabmain [data-testid="stColumn"] [data-testid="stElementContainer"]:not([class*="st-key-src_search"]):not([class*="st-key-dp_sel_"]):not([class*="_limit"]) > :is([data-testid="stTextInput"], [data-testid="stSelectbox"], [data-testid="stNumberInput"], [data-testid="stTextArea"], [data-testid="stMultiSelect"], [data-testid="stDateInput"], [data-testid="stTimeInput"], [data-testid="stRadio"]) {
  grid-template-columns: 110px minmax(0, 1fr); }
.st-key-tabmain [data-testid="stTextArea"], .st-key-tabmain [data-testid="stMultiSelect"] { align-items: start !important; }
.st-key-tabmain [data-testid="stWidgetLabel"] { margin: 0 !important; min-height: 0 !important; }
.st-key-tabmain [data-testid="stWidgetLabel"] p { font-size: 12px !important; color: var(--sub); }
.st-key-tabmain [data-testid="stVerticalBlock"] { gap: 0.4rem !important; }
.st-key-tabmain [data-testid="stHorizontalBlock"] { gap: 0.75rem !important; }
.st-key-tabmain hr { margin: 0.5rem 0 !important; }
/* Загрузка: «Файл документа» | имя файла | кнопка «Выбрать» в одной строке */
.st-key-upl_file_row [data-testid="stHorizontalBlock"] {
  display: grid !important; grid-template-columns: 180px minmax(0, 1fr) auto; column-gap: 12px; align-items: center; }
.st-key-upl_file_row [data-testid="stColumn"] { width: auto !important; flex: none !important; min-width: 0 !important; }
.st-key-tabmain .st-key-upl_file_row [data-testid="stColumn"] [data-testid="stElementContainer"] > [data-testid="stTextInput"][data-testid="stTextInput"][data-testid="stTextInput"][data-testid="stTextInput"] {
  display: block !important; }
.st-key-upl_file_row [data-testid="stFileUploader"] > :not([data-testid="stFileUploaderDropzone"]):not(:has([data-testid="stFileUploaderDropzone"])) {
  display: none !important; }
.st-key-upl_file_row [data-testid="stFileUploaderDropzone"] {
  padding: 0 !important; border: none !important; background: transparent !important; }
.st-key-upl_file_row [data-testid="stFileUploaderDropzoneInstructions"] { display: none !important; }
.st-key-upl_file_row [data-testid="stFileUploaderDropzone"] {
  display: flex !important; align-items: center; min-height: 0 !important; margin: 0 !important; }
.st-key-upl_file_row [data-testid="stFileUploaderDropzone"] button {
  height: 34px !important; min-height: 34px !important; box-sizing: border-box; margin: 0 !important; padding: 0 16px !important;
  display: inline-flex !important; align-items: center; justify-content: center; line-height: 1 !important; }
.st-key-upl_file_row [data-testid="stFileUploaderDropzone"] button > * { display: none !important; }
.st-key-upl_file_row [data-testid="stFileUploaderDropzone"] button::after {
  content: "Выбрать"; font-family: inherit; font-size: 12px; font-weight: 400; line-height: 1; }
.st-key-upl_file_row [data-testid="stMarkdownContainer"] p {
  font-size: 12px !important; color: var(--sub) !important; margin: 0 !important; line-height: 1.2; }
.st-key-upl_file_row [data-testid="stElementContainer"] { margin: 0 !important; }
/* Кнопки в рядах фильтров («Сбросить», периоды): высота = высоте поля (34px), по центру/низу строки */
.st-key-tabmain [class*="st-key-cmp"] [data-testid="stHorizontalBlock"] button {
  height: 34px !important; min-height: 34px !important; box-sizing: border-box; padding: 0 14px !important;
  display: inline-flex !important; align-items: center; justify-content: center; line-height: 1 !important; }
.st-key-tabmain [class*="st-key-cmpv_"] [data-testid="stHorizontalBlock"] { align-items: flex-end !important; }
.st-key-tabmain [data-testid="stElementContainer"]:has(.srcdetail-mark) { display: none !important; }
.st-key-tabmain .st-key-src_filter[data-testid="stElementContainer"] > [data-testid="stRadio"][data-testid="stRadio"][data-testid="stRadio"] {
  display: block !important; }
.st-key-src_filter [role="radiogroup"] { flex-wrap: nowrap !important; white-space: nowrap; }
.st-key-tabmain [data-testid="stColumn"]:has(.srcdetail-mark) { padding-right: 1.75rem; }
.st-key-tabmain [data-testid="stColumn"]:has(.srcdetail-mark) [data-testid="stColumn"]:first-child [data-testid="stElementContainer"] > :is([data-testid="stTextInput"], [data-testid="stSelectbox"]) {
  grid-template-columns: 175px minmax(0, 1fr) !important; }
[class*="st-key-"][class*="_limit"] [data-testid="stNumberInput"] { display: flex !important; flex-direction: row !important; align-items: center !important;
  gap: 0 !important; width: 100% !important; max-width: none !important; }
[class*="st-key-"][class*="_limit"] [data-testid="stNumberInput"] > [data-testid="stWidgetLabel"] { flex: 0 0 180px !important; width: 180px !important; margin: 0 !important; white-space: nowrap; }
[class*="st-key-"][class*="_limit"] [data-testid="stNumberInput"] > :not([data-testid="stWidgetLabel"]) { flex: 0 0 130px !important; width: 130px !important; display: block !important; visibility: visible !important; opacity: 1 !important; }
/* Раскрывающиеся блоки и формы: все поля со светлосерой границей */
[data-testid="stExpander"] [data-baseweb="input"],
details [data-baseweb="input"],
[data-testid="stForm"] [data-baseweb="input"],
[data-testid="stExpander"] [data-baseweb="textarea"],
details [data-baseweb="textarea"],
[data-testid="stForm"] [data-baseweb="textarea"],
[data-testid="stExpander"] [data-baseweb="select"] > div,
details [data-baseweb="select"] > div,
[data-testid="stForm"] [data-baseweb="select"] > div {
  border: 1px solid var(--border) !important; box-shadow: 0 0 0 1px var(--border) inset !important; background: #fff !important; }
[data-testid="stExpander"] [data-baseweb="base-input"],
details [data-baseweb="base-input"],
[data-testid="stForm"] [data-baseweb="base-input"],
[data-testid="stExpander"] [data-baseweb="input"] input,
details [data-baseweb="input"] input,
[data-testid="stForm"] [data-baseweb="input"] input,
[data-testid="stExpander"] textarea,
details textarea,
[data-testid="stForm"] textarea { border: none !important; box-shadow: none !important; background: transparent !important; }
[data-testid="stExpander"] [data-baseweb="input"]:focus-within,
details [data-baseweb="input"]:focus-within,
[data-testid="stForm"] [data-baseweb="input"]:focus-within,
[data-testid="stExpander"] [data-baseweb="textarea"]:focus-within,
details [data-baseweb="textarea"]:focus-within,
[data-testid="stForm"] [data-baseweb="textarea"]:focus-within { border-color: var(--blue) !important; box-shadow: 0 0 0 1px var(--blue) inset !important; }
.st-key-manual_draft[data-testid="stForm"] { border: none !important; padding: 0 !important; }
/* Streamlit 1.64: рамку поля рисует *RootElement (не data-baseweb) */
[data-testid="stExpander"] [data-testid$="RootElement"],
details [data-testid$="RootElement"],
[data-testid="stForm"] [data-testid$="RootElement"] {
  border: 1px solid var(--border) !important; background: #fff !important; border-radius: 6px !important; }
[data-testid="stExpander"] [data-testid$="RootElement"]:focus-within,
details [data-testid$="RootElement"]:focus-within,
[data-testid="stForm"] [data-testid$="RootElement"]:focus-within { border-color: var(--blue) !important; }
/* Серая граница полей — только на белом фоне (раскрывающиеся блоки); вне их поля стоят на сером фоне без неё */
[data-testid="stExpander"] [data-testid$="RootElement"],
[data-testid="stExpander"] [data-testid="stNumberInputContainer"],
details [data-testid$="RootElement"],
details [data-testid="stNumberInputContainer"],
[data-testid="stForm"] [data-testid$="RootElement"],
[data-testid="stForm"] [data-testid="stNumberInputContainer"] {
  border: 1px solid var(--border) !important; border-radius: 6px !important; }
[data-testid="stExpander"] [data-testid$="RootElement"]:focus-within,
[data-testid="stExpander"] [data-testid="stNumberInputContainer"]:focus-within,
details [data-testid$="RootElement"]:focus-within,
details [data-testid="stNumberInputContainer"]:focus-within,
[data-testid="stForm"] [data-testid$="RootElement"]:focus-within,
[data-testid="stForm"] [data-testid="stNumberInputContainer"]:focus-within { border-color: var(--blue) !important; }
[data-testid="stExpander"] [data-testid="stForm"], details [data-testid="stForm"] { border: none !important; padding: 0 !important; }
/* Единый интервал между строками полей (как Направление/Категория на «Поиске») */
.st-key-tabmain [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] > :is([data-testid="stTextInput"], [data-testid="stSelectbox"], [data-testid="stNumberInput"], [data-testid="stTextArea"], [data-testid="stMultiSelect"], [data-testid="stDateInput"], [data-testid="stTimeInput"], [data-testid="stRadio"], [data-testid="stCheckbox"])),
.st-key-tabmain [data-testid="stForm"] [data-testid="stVerticalBlock"],
.st-key-tabmain [data-testid="stExpanderDetails"] [data-testid="stVerticalBlock"] { gap: 14px !important; row-gap: 14px !important; }
/* Числовые поля: рамка как у кнопок (1px var(--border), радиус 6px) */
[data-testid="stNumberInputContainer"][data-testid="stNumberInputContainer"][data-testid="stNumberInputContainer"] { border: 1px solid var(--border) !important; border-radius: 6px !important; }
[data-testid="stNumberInputContainer"][data-testid="stNumberInputContainer"][data-testid="stNumberInputContainer"]:focus-within { border-color: var(--blue) !important; }
/* Источники: карточка домена — подписи в одну строку, интервалы как на вкладке «Поиск» */
.st-key-tabmain [data-testid="stColumn"]:has(.srcdetail-mark) [data-testid="stElementContainer"] > :is([data-testid="stTextInput"], [data-testid="stSelectbox"], [data-testid="stTextArea"], [data-testid="stNumberInput"]) {
  grid-template-columns: 175px minmax(0, 1fr) !important; }
.st-key-tabmain [data-testid="stColumn"]:has(.srcdetail-mark) [data-testid="stWidgetLabel"] {
  white-space: nowrap !important; min-width: max-content; }
.st-key-tabmain [data-testid="stColumn"]:has(.srcdetail-mark) [data-testid="stColumn"] [data-testid="stElementContainer"] > :is([data-testid="stTextInput"], [data-testid="stSelectbox"]) {
  grid-template-columns: 70px minmax(0, 1fr) !important; }
.st-key-tabmain [data-testid="stColumn"]:has(.srcdetail-mark) [data-testid="stVerticalBlock"] { gap: 14px !important; }
.st-key-tabmain [data-testid="stColumn"]:has(.srcdetail-mark) [data-testid="stElementContainer"] { margin: 0 !important; }
.st-key-tabmain [data-testid="stColumn"]:has(.srcdetail-mark) [data-testid="stCheckbox"] { min-height: 34px; display: flex; align-items: center; }
.st-key-tabmain [data-testid="stHeading"] h1, .st-key-tabmain [data-testid="stHeading"] h2,
.st-key-tabmain [data-testid="stHeading"] h3 { padding: 0.25rem 0 !important; }
.st-key-tabmain [data-baseweb="input"] input, .st-key-tabmain [data-baseweb="select"] > div { min-height: 34px; }
.st-key-tabmain [data-testid="stCheckbox"], .st-key-tabmain [data-testid="stRadio"] { min-height: 0; }
/* Строка под таблицей: подпись слева, шестерня «Колонки» справа */
.st-key-tabmain [class*="st-key-colfoot_"] [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; align-items: center; gap: 0.5rem !important; }
.st-key-tabmain [class*="st-key-colfoot_"] [data-testid="stColumn"]:first-child { flex: 1 1 0 !important; min-width: 0 !important; }
.st-key-tabmain [class*="st-key-colfoot_"] [data-testid="stColumn"]:last-child { flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; display: flex; justify-content: flex-end; }
.st-key-tabmain [class*="st-key-colfoot_"] [data-testid="stCaptionContainer"] { margin: 0; }
.st-key-tabmain [class*="st-key-colfoot_"] button { min-height: 32px; padding: 2px 10px; }
.st-key-tabmain .st-key-colfoot_words [data-testid="stHorizontalBlock"] { align-items: flex-start; }
.st-key-tabmain [class*="st-key-colfoot_"] .st-key-pgnums [data-testid="stHorizontalBlock"] { gap: 4px !important; flex-wrap: nowrap !important; align-items: center; justify-content: flex-start; }
.st-key-tabmain [class*="st-key-colfoot_"] .st-key-pgnums [data-testid="stColumn"]:is(:first-child, :last-child, :nth-child(n)) { flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; display: block; justify-content: flex-start; }
.st-key-tabmain [class*="st-key-colfoot_"] .st-key-pgnums button { min-height: 32px !important; padding: 0 8px !important; }
.st-key-cmp_selall [data-testid="stHorizontalBlock"] { align-items: center !important; justify-content: space-between !important; }
.st-key-cmp_selall [data-testid="stColumn"]:last-child { text-align: right; display: flex; align-items: center; justify-content: flex-end; }
.st-key-cmp_selall [data-testid="stColumn"]:last-child [data-testid="stMarkdownContainer"] p { margin: 0 !important; font-size: 14px !important; color: var(--text) !important; line-height: 1.5 !important; }
.st-key-cmp_selall [data-testid="stCheckbox"] { margin: 0 !important; padding: 0 !important; min-height: 0 !important; display: flex; align-items: center; }
[class*="st-key-pv_"] label { user-select: none; }
/* Пальцы 👍/👎 в Просмотре: без рамки, размер иконки; выбранный — цветной */
[class*="st-key-th_up_"] button, [class*="st-key-th_down_"] button { 
  min-height: 0 !important; height: 24px !important; width: 24px !important; 
  padding: 0 !important; border: 0 !important; background: transparent !important; 
  color: #9aa0a6 !important; box-shadow: none !important; }
[class*="st-key-th_up_"] button:hover, [class*="st-key-th_down_"] button:hover { 
  background: transparent !important; opacity: 0.7; }
[class*="st-key-th_up_"], [class*="st-key-th_down_"] { width: auto !important; }
[class*="st-key-th_up_on_"] button { color: #2e9e4f !important; background: #e6f4ea !important; }
[class*="st-key-th_down_on_"] button { color: #d93025 !important; background: transparent !important; }
/* Компактные ряды: cmp_ — подпись слева, cmpv_ — подпись сверху; колонки по ширине содержимого, влево */
.st-key-tabmain [class*="st-key-cmp"] [data-testid="stHorizontalBlock"] {
  flex-wrap: wrap !important; justify-content: flex-start !important; gap: 0.5rem !important; align-items: flex-end; }
.st-key-tabmain [class*="st-key-cmp_"] [data-testid="stHorizontalBlock"] { align-items: center; }
.st-key-tabmain [class*="st-key-cmp"] [data-testid="stColumn"] { flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; }
.st-key-tabmain [class*="st-key-cmpv_"] [data-testid="stColumn"]:first-child { flex: 1 1 0 !important; min-width: 180px !important; }
.st-key-tabmain [class*="st-key-cmp_"] [data-testid="stHorizontalBlock"] [data-testid="stColumn"] [data-testid="stElementContainer"] > :is([data-testid="stTextInput"], [data-testid="stSelectbox"], [data-testid="stDateInput"], [data-testid="stTimeInput"], [data-testid="stRadio"]) {
  display: flex !important; flex-direction: row; align-items: center; gap: 8px; }
.st-key-tabmain [class*="st-key-cmpv_"] [data-testid="stHorizontalBlock"] [data-testid="stColumn"] [data-testid="stElementContainer"] > :is([data-testid="stTextInput"], [data-testid="stSelectbox"], [data-testid="stDateInput"], [data-testid="stTimeInput"], [data-testid="stRadio"]) {
  display: flex !important; flex-direction: column; align-items: stretch; gap: 2px; }
.st-key-tabmain [class*="st-key-cmp"] [data-testid="stWidgetLabel"] { flex: 0 0 auto !important; width: auto !important; min-width: max-content !important; white-space: nowrap !important; }
.st-key-tabmain [class*="st-key-cmp"] [data-testid="stElementContainer"] > [data-testid^="st"] > div:last-child { flex: 1 1 auto; min-width: 0; }
"""


def topbar(page: str) -> None:
    """Название вкладки в верхней панели (слева от Deploy)."""
    if page == "Слова":
        st.markdown(
            f'<div class="gar-topbar"><b>{page} <span class="words-help-icon" title="Данные: /ds_words (YAML репозитория ds_words). Вкладка только читает и пишет файлы.">?</span></b></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <style>
            .words-help-icon {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 16px;
                height: 16px;
                border-radius: 50%;
                background-color: #8991a3;
                color: white;
                font-size: 11px;
                font-weight: 600;
                cursor: help;
                vertical-align: middle;
                pointer-events: auto;
            }
            .words-help-icon:hover {
                background-color: #7a8193;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f'<div class="gar-topbar"><b>{page}</b></div>', unsafe_allow_html=True)
