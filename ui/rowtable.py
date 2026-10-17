"""Общая таблица записей вкладок «Истории» (ds_search#702): название-кнопка, данные, 🗑 в последней ячейке."""
import re

import streamlit as st
import streamlit.components.v1 as components

VISIBLE, ROW_H = 8, 30  # макс. видимых строк, высота строки, px


def current(key, ids):
    """Выбранная запись: session_state -> query-параметр -> первая; пустая/удалённая сбрасывается."""
    ss = st.session_state
    if key not in ss:
        ss[key] = st.query_params.get(key)
    if ss.get(key) not in ids:
        ss[key] = ids[0] if ids else None
    if ss[key] is not None:
        st.query_params[key] = ss[key]
    return ss[key]


def table(prefix, heads, widths, rows, cur, key, on_delete):
    """rows: [(id, название, [ячейки])]; heads/widths — по колонке на название и каждую ячейку; 🗑 добавляется последней."""
    w = [*widths, 1]
    with st.container(key=f"stimgtab_{prefix}"):
        for c, t in zip(st.columns(w), [*heads, ""]):
            if t:
                c.markdown(f"**{t}**")
        with st.container(height=VISIBLE * ROW_H if len(rows) > VISIBLE else "content", border=False, key=f"stimgtab_{prefix}_rows"):
            for rid, name, cells in rows:
                c = st.columns(w, vertical_alignment="center")
                on = rid == cur
                if c[0].button((name or rid), key=f"{prefix}_open_{rid}", use_container_width=True,
                               type="secondary" if on else "tertiary"):
                    st.session_state[key] = rid; st.rerun()
                for cc, v in zip(c[1:-1], cells):
                    cc.markdown(str(v).replace("*", "\\*"))
                if c[-1].button("🗑", key=f"{prefix}_del_{rid}", help="Удалить"):
                    on_delete(rid, name)


def _edit(parkey, vid, formkey):
    st.session_state[parkey] = vid
    st.session_state["_scroll_to"] = formkey


def img_buttons(c, key, vid, formkey, on_sel, on_like, on_del, sel=False):
    """Кнопки под картинкой: ✔ ♥ ✏ с равными отступами, 🗑 у правого края. ✏ — выбрать картинку в «Доработать» и прокрутить к блоку."""
    with c, st.container(key=f"gbtn_{key}{vid}"):
        b = st.columns(4)
        if b[0].button("✔", key=f"{key}s{vid}", help="Выбрать"):
            on_sel(); st.rerun()
        if b[1].button("♥", key=f"{key}l{vid}", help="Лайк"):
            on_like(); st.rerun()
        b[2].button("✎", key=f"{key}e{vid}", help="Доработать", on_click=_edit, args=(key + "par", vid, formkey))
        cf = f"{key}cd{vid}"
        if b[3].button("🗑", key=f"{key}d{vid}", help="Удалить"):
            if sel:  # выбранную (✔) удаляем только после подтверждения; с ♥ или без всего — сразу
                st.session_state[cf] = True
            else:
                on_del()
            st.rerun()
        if st.session_state.get(cf):
            st.caption("Удалить выбранную?")
            y, n = st.columns(2)
            if y.button("Да", key=cf + "y"):
                st.session_state.pop(cf, None); on_del(); st.rerun()
            if n.button("Нет", key=cf + "n"):
                st.session_state.pop(cf, None); st.rerun()


def frame_css():
    """Рамки картинок: тёмно-жёлтая 2px — выбрана для «Доработать» (✎), зелёная 2px — выбранный вариант (✔)."""
    st.markdown("<style>[class*='st-key-gimg_'][class*='-zedit'] img{border:2px solid #b8860b;box-sizing:border-box}"
                "[class*='st-key-gimg_'][class*='-zsel'] img{border:2px solid #2e9e4f;box-sizing:border-box}</style>",
                unsafe_allow_html=True)


def scroll_pending():
    """Вызывать в конце страницы: если нажали ✏, прокручивает к блоку «Доработать»."""
    k = st.session_state.pop("_scroll_to", None)
    if k:
        cls = re.sub(r"[^A-Za-z0-9_-]", "-", k)
        components.html(
            "<script>let n=0;const t=setInterval(()=>{const e=window.parent.document.querySelector('[class*=\"st-key-" + cls + "\"]');"
            "if(e){e.scrollIntoView({behavior:'smooth',block:'center'});clearInterval(t)}else if(++n>20)clearInterval(t)},100)</script>",
            height=0)


def var_name(vs, vid):
    """Временное имя варианта по порядку в списке: «вар. 01»."""
    i = next((n for n, v in enumerate(vs) if v["id"] == vid), -1)
    return f"вар. {i + 1:02d}"


def var_fmt(vs):
    """format_func для «Доработать»: «вар. 01 · <id>»."""
    return lambda vid: f"{var_name(vs, vid)} · {vid}"
