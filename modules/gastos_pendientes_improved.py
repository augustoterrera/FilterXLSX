import streamlit as st
import pandas as pd
import math
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
from datetime import datetime
from dateutil import parser as dateparser

# ==========================
# GASTOS PENDIENTES - MongoDB
# ==========================
def show():
    # ---------- Conexión ----------
    def get_mongo():
        try:
            uri = st.secrets["MONGO_URI"]
            db_name = st.secrets.get("MONGO_DB", "gastos_db")
            coll_name = st.secrets.get("MONGO_COLLECTION", "gastos")
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            db = client[db_name]
            coll = db[coll_name]
            # Índices recomendados (id único y fecha)
            coll.create_index([("id", ASCENDING)], unique=False, name="idx_id")
            coll.create_index([("estado", ASCENDING), ("fecha", DESCENDING)], name="idx_estado_fecha")
            return coll
        except KeyError:
            st.error("⚠️ Falta MONGO_URI en secrets")
            return None
        except Exception as e:
            st.error(f"⚠️ Error de conexión a MongoDB: {e}")
            return None

    coll = get_mongo()
    if coll is None:
        return

    # ---------- Helpers ----------
    def _parse_fecha(v):
        if v is None or v == "":
            return None
        if isinstance(v, datetime):
            return v
        # admite "2025-09-01" o "01/09/2025"
        try:
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
        if pd.isnull(value) or value == '' or str(value).strip() == '':
            return 'No especificado'
        return str(value)

    def format_monto(x):
        try:
            return f"$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return f"$ {x}"

    # ---------- Carga de datos ----------
    def load_pending_expenses():
        try:
            # Query equivalente: WHERE estado='pendiente' ORDER BY fecha DESC
            cursor = coll.find({"estado": "pendiente"}).sort([("fecha", DESCENDING)])
            rows = []
            for d in cursor:
                rows.append({
                    "id": d.get("id") or d.get("_id"),
                    "fecha": d.get("fecha"),
                    "concepto": d.get("concepto"),
                    "monto": d.get("monto"),
                    "comprobante": d.get("comprobante"),
                    "obra": d.get("obra"),
                    "persona": d.get("persona"),
                    "estado": d.get("estado"),
                    "proveedor": d.get("proveedor"),
                    "metodo_pago": d.get("metodo_pago"),
                    "_oid": d.get("_id")
                })
            df = pd.DataFrame(rows)
            # Normalizar fecha -> pandas datetime para ordenar/filtrar
            if not df.empty and "fecha" in df.columns:
                df["fecha"] = pd.to_datetime(df["fecha"].apply(_parse_fecha))
            return df
        except Exception as e:
            st.error(f"Error cargando datos: {e}")
            return pd.DataFrame()

    df = load_pending_expenses()
    if df.empty:
        st.info("🎉 No hay gastos pendientes de aprobación.")
        return

    # ---------- Estilos (CSS) ----------
    st.markdown(
        """
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
        """,
        unsafe_allow_html=True
    )

    # ---------- Filtros ----------
    with st.container():
        st.subheader("💰 Gastos Pendientes de Aprobación")
        top1, top2, top3 = st.columns([2, 2, 1.2])

        with top1:
            search_query = st.text_input("🔍 Buscar (N° comprobante, monto)", value="", key="global_search")

        with top2:
            cols = st.columns(2)
            with cols[0]:
                obras_sel = st.multiselect("🏗️ Obra", sorted([x for x in df["obra"].dropna().unique() if str(x).strip() != ""]))
            with cols[1]:
                personas_sel = st.multiselect("👤 Persona", sorted([x for x in df["persona"].dropna().unique() if str(x).strip() != ""]))

            cols2 = st.columns(2)
            with cols2[0]:
                metodos_sel = st.multiselect("💳 Método de pago", sorted([x for x in df["metodo_pago"].dropna().unique() if str(x).strip() != ""]))
            with cols2[1]:
                proveedores_sel = st.multiselect("🏪 Proveedor", sorted([x for x in df["proveedor"].dropna().unique() if str(x).strip() != ""]))

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
        filtered_df = filtered_df.sort_values(by="fecha", ascending=False, na_position="last")
    elif sort_by == "Fecha ↑":
        filtered_df = filtered_df.sort_values(by="fecha", ascending=True, na_position="last")
    elif sort_by == "Monto ↓":
        filtered_df = filtered_df.sort_values(by="monto", ascending=False, na_position="last")
    else:
        filtered_df = filtered_df.sort_values(by="monto", ascending=True, na_position="last")

    # Estado vacío
    if filtered_df.empty:
        st.warning("⚠️ No se encontraron gastos con los criterios de búsqueda.")
        return
    else:
        st.caption(f"📊 Mostrando {len(filtered_df)} de {len(df)} gastos pendientes")

    # ---------- Acciones DB ----------
    def mark_as_loaded(expense_id, oid=None):
        """
        Cambia estado a 'cargado'. Intenta por id (tu id numérico) y si está disponible por _id.
        """
        # normalizar id
        q = {}
        if oid:
            try:
                q = {"_id": ObjectId(str(oid))}
            except Exception:
                q = {}
        if not q and expense_id not in (None, "",):
            q = {"id": expense_id}
        if not q:
            st.error("ID inválido")
            return False

        try:
            res = coll.update_one(q, {"$set": {"estado": "cargado"}})
            return res.modified_count == 1
        except Exception as e:
            st.error(f"Error actualizando gasto: {str(e)}")
            return False

    # ---------- Helpers UI ----------
    def render_chips(row):
        return f"""
        <div class="chips">
            <span class="chip">🏗️ {safe_format(row['obra'])}</span>
            <span class="chip">👤 {safe_format(row['persona'])}</span>
            <span class="chip">💳 {safe_format(row['metodo_pago'])}</span>
            <span class="chip">📝 {safe_format(row['concepto'])}</span>
        </div>
        """

    def status_class(estado):
        if not estado: return "status-badge"
        estado_l = str(estado).strip().lower()
        if "pend" in estado_l: return "status-badge status--pendiente"
        if "carg" in estado_l or "aprob" in estado_l: return "status-badge status--cargado"
        if "rech" in estado_l: return "status-badge status--rechazado"
        return "status-badge"

    def open_confirm_dialog(row):
        dialog_fn = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)
        if not dialog_fn:
            return False

        @dialog_fn("Confirmar aprobación")
        def _dialog():
            st.write(f"¿Aprobar el gasto **#{row.get('id','')} - {safe_format(row.get('concepto'))}** por **{format_monto(row.get('monto'))}**?")
            st.caption(f"Fecha: {format_fecha(row.get('fecha'))} · Obra: {safe_format(row.get('obra'))} · Persona: {safe_format(row.get('persona'))}")
            c1, c2 = st.columns(2)
            if c1.button("✅ Sí, aprobar", key=f"dlg_yes_{row.get('id')}", use_container_width=True):
                if mark_as_loaded(row.get('id'), row.get('_oid')):
                    try:
                        st.toast(f"✅ Gasto #{row.get('id')} aprobado")
                    except Exception:
                        st.success(f"✅ Gasto #{row.get('id')} aprobado")
                    st.rerun()
            if c2.button("❌ Cancelar", key=f"dlg_no_{row.get('id')}", use_container_width=True):
                st.rerun()
        _dialog()
        return True

    def card_html(row):
        return f"""
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              {safe_format(row.get("proveedor"))}
              <span class="id-badge">#{safe_format(row.get("id"))}</span>
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

    # ---------- Paginación y render ----------
    total_pages = max(1, math.ceil(len(filtered_df) / items_per_page))
    if "current_page" not in st.session_state:
        st.session_state.current_page = 1

    nav1, nav2, nav3 = st.columns([1, 3, 1])
    with nav1:
        if st.button("⬅️ Anterior", use_container_width=True, disabled=st.session_state.current_page <= 1):
            st.session_state.current_page -= 1
    with nav2:
        st.write(f"Página **{st.session_state.current_page}** de **{total_pages}**")
    with nav3:
        if st.button("Siguiente ➡️", use_container_width=True, disabled=st.session_state.current_page >= total_pages):
            st.session_state.current_page += 1

    page = max(1, min(st.session_state.current_page, total_pages))
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_df = filtered_df.iloc[start_idx:end_idx]

    N_COLS = 2
    cols = st.columns(N_COLS, gap="small")
    for i, (_, row) in enumerate(page_df.iterrows()):
        with cols[i % N_COLS]:
            with st.container():
                st.markdown(card_html(row), unsafe_allow_html=True)
                approve_key = f"approve_{row.get('id')}"
                if st.button("✅ Aprobar", key=approve_key, use_container_width=True):
                    opened = open_confirm_dialog(row)
                    if not opened:
                        st.session_state[f"confirm_approve_{row.get('id')}"] = True
                if st.session_state.get(f"confirm_approve_{row.get('id')}", False):
                    with st.expander("⚠️ Confirmar aprobación", expanded=True):
                        st.markdown(f"¿Estás seguro que quieres aprobar el gasto **#{safe_format(row.get('id'))} - {safe_format(row.get('concepto'))}**?")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("✅ Sí, aprobar", key=f"approve_confirm_{row.get('id')}", use_container_width=True):
                                if mark_as_loaded(row.get('id'), row.get('_oid')):
                                    try:
                                        st.toast(f"✅ Gasto #{row.get('id')} aprobado")
                                    except Exception:
                                        st.success(f"✅ Gasto #{row.get('id')} aprobado")
                                    st.session_state[f"confirm_approve_{row.get('id')}"] = False
                                    st.rerun()
                        with col_no:
                            if st.button("❌ Cancelar", key=f"approve_cancel_{row.get('id')}", use_container_width=True):
                                st.session_state[f"confirm_approve_{row.get('id')}"] = False

if __name__ == "__main__":
    st.set_page_config(page_title="Gastos pendientes", layout="wide")
    show()
