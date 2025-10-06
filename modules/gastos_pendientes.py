# gastos_pendientes.py — Listado y aprobación de gastos (MongoDB, paginación FIX)

import math
from datetime import datetime

import pandas as pd
import streamlit as st
from bson import ObjectId
from dateutil import parser as dateparser
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError


# ==========================
# Conexión a Mongo
# ==========================
@st.cache_resource(show_spinner=False)
def _get_coll():
    try:
        uri = st.secrets["MONGO_URI"]
        db_name = st.secrets.get("MONGO_DB", "tus_gastos_db")
        coll_name = st.secrets.get("MONGO_COLLECTION", "gastos")
    except KeyError:
        raise RuntimeError("⚠️ Configurá MONGO_URI, MONGO_DB y MONGO_COLLECTION en .streamlit/secrets.toml")

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    coll = client[db_name][coll_name]

    # Índices recomendados
    try:
        coll.create_index([("estado", ASCENDING), ("fecha", DESCENDING)], name="idx_estado_fecha")
        coll.create_index([("id", ASCENDING)], name="idx_id")  # por si migraste con id propio
        coll.create_index([("obra", ASCENDING)], name="idx_obra")
        coll.create_index([("persona", ASCENDING)], name="idx_persona")
        coll.create_index([("proveedor", ASCENDING)], name="idx_proveedor")
        coll.create_index([("metodo_pago", ASCENDING)], name="idx_metodo_pago")
    except Exception:
        pass

    return coll


# ==========================
# Utilidades de formato
# ==========================
def _parse_fecha(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    try:
        # acepta "2025-09-01" o "01/09/2025"
        return dateparser.parse(str(v), dayfirst=True)
    except Exception:
        return None


def format_fecha(fecha):
    try:
        if isinstance(fecha, str):
            fecha = _parse_fecha(fecha)
        if isinstance(fecha, datetime):
            return fecha.strftime("%d/%m/%Y")
        return "Sin fecha"
    except Exception:
        return "Sin fecha"


def safe_format(value):
    if pd.isna(value) or value is None or str(value).strip() == "":
        return "No especificado"
    return str(value)


def format_monto(x):
    try:
        return f"$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"$ {x}"


# ==========================
# Carga de datos
# ==========================
def load_pending_df(coll):
    """Carga gastos con estado='pendiente' y normaliza campos."""
    try:
        cursor = coll.find({"estado": "pendiente"}).sort([("fecha", DESCENDING), ("_id", DESCENDING)])
        rows = []
        for d in cursor:
            rows.append({
                "_oid": d.get("_id"),
                "id": d.get("id"),  # puede existir si migraste desde SQL
                "fecha": d.get("fecha"),
                "concepto": d.get("concepto"),
                "monto": d.get("monto"),
                "comprobante": d.get("comprobante"),
                "obra": d.get("obra"),
                "persona": d.get("persona"),
                "estado": d.get("estado"),
                "proveedor": d.get("proveedor"),
                "metodo_pago": d.get("metodo_pago"),
            })
        df = pd.DataFrame(rows)

        if not df.empty:
            df["fecha"] = pd.to_datetime(df["fecha"].apply(_parse_fecha))
        return df
    except PyMongoError as e:
        st.error(f"❌ Error cargando gastos: {e}")
        return pd.DataFrame()


# ==========================
# Acciones DB
# ==========================
def mark_as_loaded(coll, expense_id=None, oid=None):
    """
    Cambia estado a 'cargado'. Intenta primero por _id (si viene),
    si no, por 'id' (numérico/string migrado desde SQL).
    """
    q = None
    if oid:
        try:
            q = {"_id": ObjectId(str(oid))}
        except Exception:
            q = None
    if not q and expense_id not in (None, ""):
        q = {"id": expense_id}
    if not q:
        st.error("ID inválido para aprobar.")
        return False

    try:
        res = coll.update_one(q, {"$set": {"estado": "cargado"}})
        return res.modified_count == 1
    except PyMongoError as e:
        st.error(f"❌ Error actualizando gasto: {e}")
        return False


# ==========================
# UI helpers
# ==========================
CSS = """
<style>
:root {
  --card-bg: rgba(255,255,255,0.04);
  --card-border: rgba(255,255,255,0.12);
  --text-muted: rgba(255,255,255,0.85);
  --chip-border: rgba(255,255,255,0.18);
  --chip-bg: rgba(255,255,255,0.06);
  --divider: rgba(255,255,255,0.18);
}
.card { border:1px solid var(--card-border); border-radius:14px; padding:14px 14px 10px 14px; background:var(--card-bg); box-shadow:0 2px 8px rgba(0,0,0,0.25); transition:transform .06s, box-shadow .06s; }
.card:hover { transform: translateY(-1px); box-shadow:0 8px 22px rgba(0,0,0,0.35); }
.card-header { display:flex; align-items:flex-start; justify-content:space-between; gap:10px; margin-bottom:6px; }
.card-title { font-weight:800; font-size:1.05rem; line-height:1.2; display:flex; gap:8px; align-items:center; }
.id-badge { background: rgba(116,185,255,0.18); border:1px solid rgba(116,185,255,0.35); color:#dfefff; padding:2px 8px; border-radius:12px; font-size:.74rem; font-weight:700; }
.amount-wrap { text-align:right; min-width:140px; }
.amount-label { font-size:.78rem; opacity:.8; display:block; }
.amount { font-weight:900; font-size:1.2rem; }
.subrow { font-size:.92rem; color:var(--text-muted); display:flex; gap:14px; flex-wrap:wrap; margin-bottom:8px; }
.muted { opacity:.9; }
.chips { display:flex; gap:6px; flex-wrap:wrap; margin:8px 0; }
.chip { padding:4px 10px; border-radius:999px; font-size:.78rem; border:1px solid var(--chip-border); background:var(--chip-bg); }
.status { margin:4px 0 0; }
.status-badge { display:inline-flex; align-items:center; gap:6px; border-radius:999px; padding:4px 10px; font-size:.78rem; font-weight:700; border:1px solid var(--chip-border); background:var(--chip-bg); }
.status--pendiente { background: rgba(255,214,10,0.12); border-color: rgba(255,214,10,.35); }
.status--cargado   { background: rgba(46,213,115,0.12); border-color: rgba(46,213,115,.35); }
.status--rechazado { background: rgba(255,71,87,0.12);  border-color: rgba(255,71,87,.35); }
.divider { height:1px; background: linear-gradient(90deg, transparent, var(--divider), transparent); margin:10px 0 8px; }
</style>
"""


def render_chips(row):
    return f"""
    <div class="chips">
        <span class="chip">🏗️ {safe_format(row.get('obra'))}</span>
        <span class="chip">👤 {safe_format(row.get('persona'))}</span>
        <span class="chip">💳 {safe_format(row.get('metodo_pago'))}</span>
        <span class="chip">📝 {safe_format(row.get('concepto'))}</span>
    </div>
    """


def status_class(estado):
    if not estado:
        return "status-badge"
    e = str(estado).strip().lower()
    if "pend" in e:
        return "status-badge status--pendiente"
    if "carg" in e or "aprob" in e:
        return "status-badge status--cargado"
    if "rech" in e:
        return "status-badge status--rechazado"
    return "status-badge"


def card_html(row):
    return f"""
    <div class="card">
      <div class="card-header">
        <div class="card-title">
          {safe_format(row.get("proveedor"))}
          <span class="id-badge">#{safe_format(row.get("id") or row.get("_oid"))}</span>
        </div>
        <div class="amount-wrap">
          <span class="amount-label">Importe</span>
          <span class="amount">💰 {format_monto(row.get("monto"))}</span>
        </div>
      </div>
      <div class="subrow">
        <span class="muted">📅 {format_fecha(row.get("fecha"))}</span>
        <span class="muted">🧾 {safe_format(row.get("comprobante"))}</span>
      </div>
      {render_chips(row)}
      <div class="status">
        <span class="{status_class(row.get('estado'))}">📊 {safe_format(row.get("estado"))}</span>
      </div>
      <div class="divider"></div>
    </div>
    """


def open_confirm_dialog(row, on_confirm):
    dialog_fn = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)
    if not dialog_fn:
        return False

    @dialog_fn("Confirmar aprobación")
    def _dialog():
        st.write(
            f"¿Aprobar el gasto **#{safe_format(row.get('id') or row.get('_oid'))} - "
            f"{safe_format(row.get('concepto'))}** por **{format_monto(row.get('monto'))}**?"
        )
        st.caption(
            f"Fecha: {format_fecha(row.get('fecha'))} · Obra: {safe_format(row.get('obra'))} · "
            f"Persona: {safe_format(row.get('persona'))}"
        )
        c1, c2 = st.columns(2)
        if c1.button("✅ Sí, aprobar", key=f"dlg_yes_{row.get('_oid')}", use_container_width=True):
            on_confirm()
            st.rerun()
        if c2.button("❌ Cancelar", key=f"dlg_no_{row.get('_oid')}", use_container_width=True):
            st.rerun()

    _dialog()
    return True


# ==========================
# Página principal
# ==========================
def show():
    st.set_page_config(page_title="Gastos pendientes", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.subheader("💰 Gastos Pendientes de Aprobación")

    # Conexión
    try:
        coll = _get_coll()
    except Exception as e:
        st.error(str(e))
        return

    # Cargar datos
    df = load_pending_df(coll)
    if df.empty:
        st.info("🎉 No hay gastos pendientes de aprobación.")
        return

    # ---------- Filtros ----------
    with st.container():
        top1, top2, top3 = st.columns([2, 2, 1.2])

        with top1:
            search_query = st.text_input("🔍 Buscar (N° comprobante, monto)", value="", key="global_search")

        with top2:
            cols = st.columns(2)
            with cols[0]:
                obras_sel = st.multiselect(
                    "🏗️ Obra",
                    sorted([x for x in df["obra"].dropna().unique() if str(x).strip() != ""])
                )
            with cols[1]:
                personas_sel = st.multiselect(
                    "👤 Persona",
                    sorted([x for x in df["persona"].dropna().unique() if str(x).strip() != ""])
                )

            cols2 = st.columns(2)
            with cols2[0]:
                metodos_sel = st.multiselect(
                    "💳 Método de pago",
                    sorted([x for x in df["metodo_pago"].dropna().unique() if str(x).strip() != ""])
                )
            with cols2[1]:
                proveedores_sel = st.multiselect(
                    "🏪 Proveedor",
                    sorted([x for x in df["proveedor"].dropna().unique() if str(x).strip() != ""])
                )

        with top3:
            sort_by = st.selectbox("Ordenar por", ["Fecha ↓", "Fecha ↑", "Monto ↓", "Monto ↑"], index=0)
            items_per_page = st.select_slider("Por página", options=[6, 9, 12, 15, 18], value=9)

    # Aplicar filtros
    filtered_df = df.copy()

    if search_query.strip() != "":
        mask = (
            df['comprobante'].astype(str).str.contains(search_query, case=False, na=False) |
            df['monto'].astype(str).str.contains(search_query, case=False, na=False)
        )
        filtered_df = filtered_df[mask]

    if obras_sel:
        filtered_df = filtered_df[filtered_df["obra"].isin(obras_sel)]
    if personas_sel:
        filtered_df = filtered_df[filtered_df["persona"].isin(personas_sel)]
    if metodos_sel:
        filtered_df = filtered_df[filtered_df["metodo_pago"].isin(metodos_sel)]
    if proveedores_sel:
        filtered_df = filtered_df[filtered_df["proveedor"].isin(proveedores_sel)]

    # Orden
    if sort_by == "Fecha ↓":
        filtered_df = filtered_df.sort_values(by=["fecha", "_oid"], ascending=[False, False], na_position="last")
    elif sort_by == "Fecha ↑":
        filtered_df = filtered_df.sort_values(by=["fecha", "_oid"], ascending=[True, False], na_position="last")
    elif sort_by == "Monto ↓":
        filtered_df = filtered_df.sort_values(by=["monto", "_oid"], ascending=[False, False], na_position="last")
    else:  # "Monto ↑"
        filtered_df = filtered_df.sort_values(by=["monto", "_oid"], ascending=[True, False], na_position="last")

    # Estado vacío
    if filtered_df.empty:
        st.warning("⚠️ No se encontraron gastos con los criterios de búsqueda.")
        return

    st.caption(f"📊 Mostrando {len(filtered_df)} de {len(df)} gastos pendientes")

    # ---------- Paginación y render (FIX) ----------
    # Huella del estado para resetear a página 1 si cambian filtros/orden/tamaño
    fp = (
        search_query.strip().lower(),
        tuple(sorted(obras_sel)),
        tuple(sorted(personas_sel)),
        tuple(sorted(metodos_sel)),
        tuple(sorted(proveedores_sel)),
        sort_by,
        items_per_page,
        len(filtered_df),
    )

    if "pagination_fp" not in st.session_state or st.session_state.pagination_fp != fp:
        st.session_state.current_page = 1
        st.session_state.pagination_fp = fp

    # Total de páginas y clamp de la página actual
    total_pages = max(1, math.ceil(len(filtered_df) / items_per_page))
    cur = st.session_state.get("current_page", 1)
    cur = max(1, min(cur, total_pages))
    st.session_state.current_page = cur

    # Controles de navegación con rerun inmediato
    nav1, nav2, nav3 = st.columns([1, 3, 1])
    with nav1:
        prev_disabled = st.session_state.current_page <= 1
        if st.button("⬅️ Anterior", key="btn_prev", use_container_width=True, disabled=prev_disabled):
            st.session_state.current_page = max(1, st.session_state.current_page - 1)
            st.rerun()

    with nav2:
        st.write(f"Página **{st.session_state.current_page}** de **{total_pages}**")

    with nav3:
        next_disabled = st.session_state.current_page >= total_pages
        if st.button("Siguiente ➡️", key="btn_next", use_container_width=True, disabled=next_disabled):
            st.session_state.current_page = min(total_pages, st.session_state.current_page + 1)
            st.rerun()

    # Slice de la página actual
    start_idx = (st.session_state.current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_df = filtered_df.iloc[start_idx:end_idx]

    # Render tarjetas
    N_COLS = 2
    cols = st.columns(N_COLS, gap="small")

    for i, (_, row) in enumerate(page_df.iterrows()):
        with cols[i % N_COLS]:
            with st.container():
                st.markdown(card_html(row), unsafe_allow_html=True)

                # clave única por documento
                doc_key = str(row.get("_oid") or row.get("id") or f"row{i}")
                approve_key = f"approve_{doc_key}"

                def _do_confirm():
                    ok = mark_as_loaded(coll, expense_id=row.get("id"), oid=row.get("_oid"))
                    if ok:
                        try:
                            st.toast(f"✅ Gasto #{safe_format(row.get('id') or row.get('_oid'))} aprobado")
                        except Exception:
                            st.success(f"✅ Gasto #{safe_format(row.get('id') or row.get('_oid'))} aprobado")

                if st.button("✅ Aprobar", key=approve_key, use_container_width=True):
                    opened = open_confirm_dialog(row, on_confirm=_do_confirm)
                    if not opened:
                        # Fallback si no hay st.dialog
                        st.session_state[f"confirm_approve_{doc_key}"] = True
                        st.rerun()

                if st.session_state.get(f"confirm_approve_{doc_key}", False):
                    with st.expander("⚠️ Confirmar aprobación", expanded=True):
                        st.markdown(
                            f"¿Estás seguro que querés aprobar el gasto "
                            f"**#{safe_format(row.get('id') or row.get('_oid'))} - {safe_format(row.get('concepto'))}**?"
                        )
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("✅ Sí, aprobar", key=f"approve_confirm_{doc_key}", use_container_width=True):
                                _do_confirm()
                                st.session_state[f"confirm_approve_{doc_key}"] = False
                                st.rerun()
                        with col_no:
                            if st.button("❌ Cancelar", key=f"approve_cancel_{doc_key}", use_container_width=True):
                                st.session_state[f"confirm_approve_{doc_key}"] = False
                                st.rerun()


# Entrypoint opcional
if __name__ == "__main__":
    show()
