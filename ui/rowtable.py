"""Общая таблица записей вкладок «Истории» (ds_search#702): название-кнопка, данные, 🗑 в последней ячейке."""
import streamlit as st


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
        for rid, name, cells in rows:
            c = st.columns(w, vertical_alignment="center")
            on = rid == cur
            if c[0].button(("▶ " if on else "") + (name or rid), key=f"{prefix}_open_{rid}", use_container_width=True,
                           type="secondary" if on else "tertiary"):
                st.session_state[key] = rid; st.rerun()
            for cc, v in zip(c[1:-1], cells):
                cc.markdown(str(v).replace("*", "\\*"))
            if c[-1].button("🗑", key=f"{prefix}_del_{rid}", help="Удалить"):
                on_delete(rid, name)
