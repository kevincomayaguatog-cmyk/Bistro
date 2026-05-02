import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import os

# ─────────────────────────────────────────────
#  CONFIGURACIÓN GLOBAL
# ─────────────────────────────────────────────
st.set_page_config(page_title="Beraca Bistro", page_icon="🍽️", layout="wide")

PRECIOS = {
    "Almuerzo":        2.50,
    "Cena":            2.50,
    "Desayuno":        2.50,
    "Kit Limpieza":    8.00,
    "Kit Ropa":       25.00,
    "Fardo Agua":      2.00,
    "Papel Higienico": 1.50,
}

FRECUENCIAS = {
    "Kit Limpieza":    7,
    "Kit Ropa":       20,
    "Fardo Agua":      3,
    "Papel Higienico": 3,
}

MAP_KEY = {
    "Kit Limpieza":    "ult_kit_limpieza",
    "Kit Ropa":        "ult_kit_ropa",
    "Fardo Agua":      "ult_fardo_agua",
    "Papel Higienico": "ult_papel_higienico",
}

ARCHIVO_HISTORICO = "historico.json"
ARCHIVO_REOS      = "reos.json"
ARCHIVO_CONTADOR  = "contador.json"
ARCHIVO_RECIBOS   = "recibos.json"

# ─────────────────────────────────────────────
#  PERSISTENCIA
# ─────────────────────────────────────────────
def cargar_json(ruta, default):
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def guardar_json(ruta, data):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

# ─────────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────────
if "reos" not in st.session_state:
    st.session_state.reos = cargar_json(ARCHIVO_REOS, {})

if "historico" not in st.session_state:
    st.session_state.historico = cargar_json(ARCHIVO_HISTORICO, [])

if "contador" not in st.session_state:
    st.session_state.contador = cargar_json(ARCHIVO_CONTADOR, {"ultimo": 0, "ultimo_recibo": 0})

if "recibos" not in st.session_state:
    st.session_state.recibos = cargar_json(ARCHIVO_RECIBOS, [])

def guardar_estado():
    guardar_json(ARCHIVO_REOS,      st.session_state.reos)
    guardar_json(ARCHIVO_HISTORICO, st.session_state.historico)
    guardar_json(ARCHIVO_CONTADOR,  st.session_state.contador)
    guardar_json(ARCHIVO_RECIBOS,   st.session_state.recibos)

def generar_num_recibo():
    st.session_state.contador["ultimo_recibo"] = st.session_state.contador.get("ultimo_recibo", 0) + 1
    return f"REC-{st.session_state.contador['ultimo_recibo']:05d}"

def generar_id():
    """Genera ID automático tipo BB-0001, BB-0002, ..."""
    st.session_state.contador["ultimo"] += 1
    return f"BB-{st.session_state.contador['ultimo']:04d}"

# ─────────────────────────────────────────────
#  UTILIDADES
# ─────────────────────────────────────────────
def hoy():
    return datetime.now().date()

def fecha_str(d):
    if d is None:
        return "—"
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d).date()
        except Exception:
            return d
    return d.strftime("%d/%m/%Y")

def dias_restantes(ultima_fecha_str, frecuencia):
    if not ultima_fecha_str:
        return None
    try:
        ultima = datetime.fromisoformat(str(ultima_fecha_str)).date()
        prox   = ultima + timedelta(days=frecuencia)
        return (prox - hoy()).days
    except Exception:
        return None

def badge_dias(dias):
    if dias is None:
        return "Sin registro"
    if dias < 0:
        return f"🔴 Vencido hace {abs(dias)}d"
    if dias == 0:
        return "🟠 Vence HOY"
    if dias <= 2:
        return f"🟡 Vence en {dias}d"
    return f"🟢 Vence en {dias}d"

def calcular_comidas_pendientes(reo):
    return [c for c in reo.get("comidas_pagadas", []) if not c.get("consumida", False)]

def calcular_monto_reembolso(comidas_pendientes):
    return len(comidas_pendientes) * 2.50

def tiempos_pendientes_str(reo):
    pendientes = calcular_comidas_pendientes(reo)
    if not pendientes:
        return "Sin comidas pagadas"
    resumen = {}
    for c in pendientes:
        fecha = c["fecha"][:10]
        resumen.setdefault(fecha, []).append(c["tiempo"])
    lineas = []
    for f, tiempos in sorted(resumen.items()):
        d = datetime.fromisoformat(f).date()
        lineas.append(f"{d.strftime('%d/%m')} → {', '.join(tiempos)}")
    return " | ".join(lineas)

def buscar_reos(query, reos_dict):
    """Busca reos por nombre, apellido o celda. Retorna lista de (rid, reo)."""
    if not query or not query.strip():
        return list(reos_dict.items())
    q = query.strip().lower()
    resultados = []
    for rid, r in reos_dict.items():
        nombre_lower = r.get("nombre", "").lower()
        celda_lower  = str(r.get("celda", "")).lower()
        if q in nombre_lower or q in celda_lower or q in rid.lower():
            resultados.append((rid, r))
    return resultados

def generar_html_recibo(recibo):
    """Genera HTML imprimible de un comprobante."""
    num        = recibo.get("numero", "—")
    fecha_hora = recibo.get("fecha_hora", "—")
    reo_nombre = recibo.get("reo_nombre", "—")
    reo_id     = recibo.get("reo_id", "—")
    celda      = recibo.get("celda", "—")
    familiar   = recibo.get("familiar", "")
    comidas    = recibo.get("comidas", [])
    extras     = recibo.get("extras", [])
    total      = recibo.get("total", 0.0)
    notas      = recibo.get("notas", "")

    # Construir filas de comidas
    filas_comidas = ""
    if comidas:
        resumen_c = {}
        for c in comidas:
            resumen_c.setdefault(c["fecha"], []).append(c["tiempo"])
        for f, ts in sorted(resumen_c.items()):
            try:
                fd = datetime.fromisoformat(f).strftime("%d/%m/%Y")
            except Exception:
                fd = f
            filas_comidas += f"<tr><td>{fd}</td><td>{', '.join(ts)}</td><td>{len(ts)} × $2.50</td><td>${len(ts)*2.50:.2f}</td></tr>"

    # Construir filas de extras
    filas_extras = ""
    renovaciones = ""
    for ex in extras:
        prod  = ex.get("producto", "")
        precio = ex.get("precio", 0)
        prox   = ex.get("proxima_renovacion", "")
        filas_extras += f"<tr><td>{prod}</td><td>${ precio:.2f}</td></tr>"
        if prox:
            renovaciones += f"<li><b>{prod}</b>: próxima renovación <b>{prox}</b></li>"

    firma_html = f"""
    <div style="margin-top:32px;display:flex;gap:40px;">
      <div style="flex:1;text-align:center;">
        <div style="border-top:1px solid #333;padding-top:6px;font-size:11px;">Firma del encargado</div>
      </div>
      <div style="flex:1;text-align:center;">
        <div style="border-top:1px solid #333;padding-top:6px;font-size:11px;">
          {'Familiar / Representante: ' + familiar if familiar else 'Firma del familiar / representante'}
        </div>
      </div>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Comprobante {num} — Beraca Bistro</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Arial', sans-serif; font-size: 13px; color: #1a1a1a; background: white; padding: 30px; max-width: 680px; margin: auto; }}
  .encabezado {{ text-align: center; border-bottom: 2px solid #c8a96e; padding-bottom: 14px; margin-bottom: 18px; }}
  .encabezado h1 {{ font-size: 22px; letter-spacing: 1px; color: #7a4f1e; }}
  .encabezado p {{ font-size: 11px; color: #888; margin-top: 2px; }}
  .num-recibo {{ font-size: 13px; font-weight: bold; color: #444; margin-top: 6px; }}
  .seccion {{ margin-bottom: 16px; }}
  .seccion h3 {{ font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: #888; border-bottom: 1px solid #eee; padding-bottom: 4px; margin-bottom: 8px; }}
  .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px 20px; }}
  .info-grid .label {{ font-size: 11px; color: #999; }}
  .info-grid .val   {{ font-weight: 600; font-size: 13px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th {{ background: #f5ede0; text-align: left; padding: 6px 8px; font-size: 11px; color: #7a4f1e; }}
  td {{ padding: 5px 8px; border-bottom: 1px solid #f0ece6; }}
  .total-row {{ font-weight: bold; font-size: 14px; background: #fdf6ee; }}
  .total-row td {{ padding: 8px; border-top: 2px solid #c8a96e; }}
  .renovaciones {{ background: #f9f6f0; border-left: 3px solid #c8a96e; padding: 10px 14px; border-radius: 4px; font-size: 12px; }}
  .renovaciones ul {{ padding-left: 16px; margin-top: 4px; }}
  .notas {{ background: #fffdf9; border: 1px dashed #ddd; padding: 8px 12px; border-radius: 4px; font-size: 12px; color: #666; margin-top: 8px; }}
  .pie {{ text-align: center; margin-top: 28px; font-size: 10px; color: #bbb; border-top: 1px solid #eee; padding-top: 10px; }}
  @media print {{
    body {{ padding: 10px; }}
    button {{ display: none; }}
  }}
</style>
</head>
<body>

<div class="encabezado">
  <h1>🍽️ BERACA BISTRO</h1>
  <p>Servicio de alimentación y productos básicos</p>
  <div class="num-recibo">COMPROBANTE No. {num}</div>
</div>

<div class="seccion">
  <h3>Información del comprobante</h3>
  <div class="info-grid">
    <div><div class="label">Fecha y hora de emisión</div><div class="val">{fecha_hora}</div></div>
    <div><div class="label">No. de recibo</div><div class="val">{num}</div></div>
    <div><div class="label">Reo / Beneficiario</div><div class="val">{reo_nombre}</div></div>
    <div><div class="label">ID del reo</div><div class="val">{reo_id}</div></div>
    <div><div class="label">Celda</div><div class="val">{celda}</div></div>
    <div><div class="label">Familiar / Pagador</div><div class="val">{familiar if familiar else '—'}</div></div>
  </div>
</div>

{'<div class="seccion"><h3>Tiempos de comida pagados</h3><table><thead><tr><th>Fecha</th><th>Tiempos</th><th>Cantidad</th><th>Subtotal</th></tr></thead><tbody>' + filas_comidas + '</tbody></table></div>' if filas_comidas else ''}

{'<div class="seccion"><h3>Productos y extras</h3><table><thead><tr><th>Producto</th><th>Precio</th></tr></thead><tbody>' + filas_extras + '</tbody></table></div>' if filas_extras else ''}

<table>
  <tr class="total-row">
    <td colspan="3">TOTAL PAGADO</td>
    <td>${total:.2f}</td>
  </tr>
</table>

{'<div class="seccion" style="margin-top:16px"><h3>Fechas de renovación</h3><div class="renovaciones"><ul>' + renovaciones + '</ul></div></div>' if renovaciones else ''}

{'<div class="notas">📝 Notas: ' + notas + '</div>' if notas else ''}

{firma_html}

<div class="pie">
  Este comprobante es válido como constancia de pago. · Beraca Bistro
  <br>Emitido el {fecha_hora}
</div>

<br>
<div style="text-align:center;">
  <button onclick="window.print()" style="background:#c8a96e;color:white;border:none;padding:10px 28px;border-radius:6px;font-size:14px;cursor:pointer;">🖨️ Imprimir / Guardar PDF</button>
</div>

</body>
</html>"""
    return html

# ─────────────────────────────────────────────
#  ESTILOS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'DM Serif Display', serif; }

.metric-card {
    background: white; border-radius: 12px; padding: 16px 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08); margin-bottom: 12px;
}
.metric-card .label { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing:.05em; }
.metric-card .value { font-size: 28px; font-weight: 600; color: #1a1a1a; }

.reo-card {
    background: white; border-left: 4px solid #c8a96e; border-radius: 8px;
    padding: 14px 18px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.reo-card .nombre { font-weight: 600; font-size: 15px; }
.reo-card .celda  { font-size: 12px; color: #777; margin-top: 2px; }
.reo-card .razon  { font-size: 12px; color: #a0522d; margin-top: 4px; font-style: italic; }

.id-badge {
    display:inline-block; background:#f0e6d3; color:#7a4f1e;
    border-radius:20px; padding:2px 10px; font-size:12px; font-weight:600;
}
.reembolso-box {
    background:#f0fff4; border-left:4px solid #38a169; border-radius:8px;
    padding:14px 18px; margin:8px 0;
}
.alerta-roja    { background:#fff0f0; border-left:4px solid #e53e3e; border-radius:6px; padding:10px 14px; margin:4px 0; }
.alerta-naranja { background:#fffaf0; border-left:4px solid #dd6b20; border-radius:6px; padding:10px 14px; margin:4px 0; }
.alerta-amarilla{ background:#fffff0; border-left:4px solid #d69e2e; border-radius:6px; padding:10px 14px; margin:4px 0; }

.search-result {
    background:#f9f6f1; border:1px solid #e8dcc8; border-radius:8px;
    padding:12px 16px; margin:6px 0; cursor:pointer;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  CABECERA
# ─────────────────────────────────────────────
st.markdown("<h1 style='margin-bottom:0'>🍽️ Beraca Bistro</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='color:#888;margin-top:4px'>Sistema de gestión · {hoy().strftime('%d/%m/%Y')}</p>", unsafe_allow_html=True)
st.divider()

reos = st.session_state.reos

# ─────────────────────────────────────────────
#  MÉTRICAS RÁPIDAS
# ─────────────────────────────────────────────
total_reos      = len(reos)
alertas_activas = 0
for r in reos.values():
    for prod, freq in FRECUENCIAS.items():
        dias = dias_restantes(r.get(MAP_KEY[prod]), freq)
        if dias is not None and dias <= 2:
            alertas_activas += 1

ingresos_hoy = sum(
    c.get("monto", 0)
    for r in reos.values()
    for c in r.get("pagos", [])
    if str(c.get("fecha", ""))[:10] == str(hoy())
)

reembolsos_pendientes = sum(
    1 for r in reos.values()
    if r.get("reembolso_pendiente", False)
)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f'<div class="metric-card"><div class="label">Reos activos</div><div class="value">{total_reos}</div></div>', unsafe_allow_html=True)
with c2:
    color = "#e53e3e" if alertas_activas else "#48bb78"
    st.markdown(f'<div class="metric-card"><div class="label">⚠️ Alertas</div><div class="value" style="color:{color}">{alertas_activas}</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="metric-card"><div class="label">Ingresos hoy</div><div class="value">${ingresos_hoy:.2f}</div></div>', unsafe_allow_html=True)
with c4:
    color4 = "#e53e3e" if reembolsos_pendientes else "#48bb78"
    st.markdown(f'<div class="metric-card"><div class="label">💰 Reembolsos pend.</div><div class="value" style="color:{color4}">{reembolsos_pendientes}</div></div>', unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────
#  BUSCADOR GLOBAL (sidebar)
# ─────────────────────────────────────────────
st.sidebar.markdown("## 🔍 Buscar reo")
query_busqueda = st.sidebar.text_input("Nombre, apellido o celda", placeholder="Ej: González, celda 5...")

if query_busqueda:
    resultados = buscar_reos(query_busqueda, reos)
    if resultados:
        st.sidebar.markdown(f"**{len(resultados)} resultado(s):**")
        for rid, r in resultados:
            pend = len(calcular_comidas_pendientes(r))
            st.sidebar.markdown(f"""
**{r['nombre']}**  
`{rid}` · Celda {r['celda']} · 🍽️ {pend} comidas
""")
    else:
        st.sidebar.warning("Sin resultados.")

st.sidebar.divider()
st.sidebar.markdown("## 📋 Próximo ID")
proximo = f"BB-{st.session_state.contador['ultimo'] + 1:04d}"
st.sidebar.info(f"El próximo reo será: **{proximo}**")

# ─────────────────────────────────────────────
#  TABS PRINCIPALES
# ─────────────────────────────────────────────
tab_reos, tab_pagos, tab_ventas, tab_alertas, tab_reporte, tab_reembolsos, tab_comprobantes, tab_historico = st.tabs([
    "👥 Reos", "💳 Pago Comidas", "🛒 Ventas / Extras",
    "🔔 Alertas", "📊 Reporte", "💰 Reembolsos", "🧾 Comprobantes", "📁 Histórico"
])

# ══════════════════════════════════════════════
#  TAB 1 — GESTIÓN DE REOS
# ══════════════════════════════════════════════
with tab_reos:
    col_lista, col_form = st.columns([1.3, 1])

    with col_lista:
        st.subheader("Reos activos")

        # Buscador dentro del tab
        busq_tab = st.text_input("🔍 Filtrar por nombre, apellido o celda", placeholder="Buscar...", key="busq_tab_reos")
        resultados_tab = buscar_reos(busq_tab, reos)

        if not reos:
            st.info("No hay reos registrados.")
        elif not resultados_tab:
            st.warning("Sin resultados para esa búsqueda.")
        else:
            for rid, r in resultados_tab:
                pend = len(calcular_comidas_pendientes(r))
                razon_html = f'<div class="razon">📌 {r["razon_captura"]}</div>' if r.get("razon_captura") else ""
                reemb_html = ' 💰 <b style="color:#e53e3e">Reembolso pendiente</b>' if r.get("reembolso_pendiente") else ""
                st.markdown(f"""<div class="reo-card">
                    <span class="id-badge">{rid}</span>&nbsp;&nbsp;<span class="nombre">{r['nombre']}</span>
                    <div class="celda">Celda <b>{r['celda']}</b> &nbsp;·&nbsp; 🍽️ {pend} comidas pendientes{reemb_html}</div>
                    {razon_html}
                </div>""", unsafe_allow_html=True)

    with col_form:
        st.subheader("➕ Agregar nuevo reo")
        with st.form("form_nuevo_reo", clear_on_submit=True):
            nuevo_id_preview = f"BB-{st.session_state.contador['ultimo'] + 1:04d}"
            st.info(f"ID que se asignará: **{nuevo_id_preview}**")

            nnombre = st.text_input("Nombre completo *", key="inp_nuevo_nombre")
            ncelda  = st.text_input("Celda *", key="inp_nuevo_celda")
            nrazon  = st.text_input("Razón de captura (opcional)", placeholder="Ej: Robo agravado, homicidio...", key="inp_nuevo_razon")

            if st.form_submit_button("✅ Registrar reo"):
                if nnombre and ncelda:
                    nid = generar_id()
                    reos[nid] = {
                        "nombre":          nnombre,
                        "celda":           ncelda,
                        "razon_captura":   nrazon.strip() if nrazon else "",
                        "comidas_pagadas": [],
                        "pagos":           [],
                        "reembolsos":      [],
                        "reembolso_pendiente": False,
                        "ult_kit_limpieza":    None,
                        "ult_kit_ropa":        None,
                        "ult_fardo_agua":      None,
                        "ult_papel_higienico": None,
                        "fecha_ingreso":   str(hoy()),
                    }
                    guardar_estado()
                    st.success(f"✅ {nnombre} registrado con ID **{nid}**.")
                    st.rerun()
                else:
                    st.warning("Nombre y celda son obligatorios.")

        st.divider()
        st.subheader("🚪 Dar de baja / Traslado")
        if reos:
            opciones_baja = {f"{r['nombre']} · {rid}": rid for rid, r in reos.items()}
            sel_baja = st.selectbox("Seleccionar reo", list(opciones_baja.keys()), key="sel_baja")
            rid_baja = opciones_baja[sel_baja]
            reo_baja = reos[rid_baja]

            motivo = st.selectbox("Motivo de salida", ["Liberado", "Traslado", "Otro"], key="sel_motivo_baja")
            centro_destino = ""
            if motivo == "Traslado":
                centro_destino = st.text_input("Centro penal de destino *", placeholder="Ej: Centro Penal La Esperanza", key="inp_centro_destino")
            detalle_extra = st.text_input("Observaciones adicionales (opcional)", key="inp_detalle_baja")

            # Mostrar si hay comidas pendientes de reembolso
            pend_baja = calcular_comidas_pendientes(reo_baja)
            monto_remb = calcular_monto_reembolso(pend_baja)
            if pend_baja:
                st.markdown(f"""<div class="reembolso-box">
                    💰 <b>Comidas no consumidas: {len(pend_baja)}</b><br>
                    Monto a reembolsar al familiar: <b>${monto_remb:.2f}</b>
                </div>""", unsafe_allow_html=True)
                aplicar_reembolso = st.checkbox("Marcar reembolso como pendiente de pago al familiar", value=True, key="chk_aplicar_reembolso")
            else:
                aplicar_reembolso = False
                st.caption("Sin comidas pendientes — no hay reembolso.")

            if st.button("🗑️ Archivar y dar de baja"):
                if motivo == "Traslado" and not centro_destino.strip():
                    st.error("Indica el centro penal de destino.")
                else:
                    hist_entry = {
                        **reo_baja,
                        "id":             rid_baja,
                        "motivo_baja":    motivo,
                        "centro_destino": centro_destino.strip(),
                        "detalle_baja":   detalle_extra.strip(),
                        "fecha_baja":     str(datetime.now()),
                        "comidas_reembolsadas": len(pend_baja),
                        "monto_reembolso": monto_remb,
                    }
                    st.session_state.historico.append(hist_entry)
                    del reos[rid_baja]
                    guardar_estado()
                    msg = f"✅ {reo_baja['nombre']} archivado."
                    if motivo == "Traslado":
                        msg += f" Traslado a: {centro_destino}."
                    if aplicar_reembolso and monto_remb > 0:
                        msg += f" Reembolso pendiente: ${monto_remb:.2f}."
                    st.success(msg)
                    st.rerun()

# ══════════════════════════════════════════════
#  TAB 2 — PAGO DE COMIDAS
# ══════════════════════════════════════════════
with tab_pagos:
    st.subheader("Registrar pago de comidas")
    ORDEN_TIEMPOS = ["Desayuno", "Almuerzo", "Cena"]

    if not reos:
        st.info("No hay reos registrados.")
    else:
        # Búsqueda dentro del tab
        busq_pagos = st.text_input("🔍 Buscar reo", placeholder="Nombre, apellido o celda...", key="busq_pagos")
        resultados_pagos = buscar_reos(busq_pagos, reos)
        opciones_pagos = {f"{r['nombre']} — Celda {r['celda']} [{rid}]": rid for rid, r in resultados_pagos}

        if not opciones_pagos:
            st.warning("Sin resultados.")
        else:
            sel = st.selectbox("Seleccionar reo", list(opciones_pagos.keys()), key="sel_pagos")
            rid_sel = opciones_pagos[sel]
            reo_sel = reos[rid_sel]

            pend_act = calcular_comidas_pendientes(reo_sel)
            st.write(f"**Comidas pendientes de entrega:** {len(pend_act)}")
            if pend_act:
                resumen = {}
                for c in pend_act:
                    resumen.setdefault(c["fecha"][:10], []).append(c["tiempo"])
                for f, ts in sorted(resumen.items()):
                    d = datetime.fromisoformat(f).date()
                    st.markdown(f"- **{d.strftime('%d/%m/%Y')}**: {', '.join(ts)}")

            st.markdown("---")
            st.write("**Nuevo pago:**")

            col_a, col_b = st.columns(2)
            with col_a:
                fecha_inicio  = st.date_input("Desde (primer tiempo)", value=hoy(), min_value=hoy(), key="fi_pagos")
                primer_tiempo = st.selectbox("Primer tiempo del día inicial", ["Almuerzo", "Cena", "Desayuno"], key="sel_primer_tiempo")
            with col_b:
                n_dias = st.number_input("Días a pagar (máx. 15)", min_value=1, max_value=15, value=1, key="num_dias_pago")
                st.caption("Mínimo: 1 tiempo de comida.")

            st.write("**Selecciona los tiempos por día:**")
            comidas_a_pagar = []
            total_pago      = 0.0
            primer_idx      = ORDEN_TIEMPOS.index(primer_tiempo)

            for i in range(int(n_dias)):
                dia  = fecha_inicio + timedelta(days=i)
                cols = st.columns([2, 1, 1, 1])
                cols[0].write(f"📅 {dia.strftime('%a %d/%m')}")
                for j, tiempo in enumerate(ORDEN_TIEMPOS):
                    deshabilitado = (i == 0) and (j < primer_idx)
                    if deshabilitado:
                        cols[j+1].checkbox(tiempo, value=False, disabled=True, key=f"t_{rid_sel}_{i}_{tiempo}")
                    else:
                        val = cols[j+1].checkbox(tiempo, value=True, key=f"t_{rid_sel}_{i}_{tiempo}")
                        if val:
                            comidas_a_pagar.append({"fecha": str(dia), "tiempo": tiempo, "consumida": False})
                            total_pago += 2.50

            st.markdown(f"### 💰 Total: **${total_pago:.2f}** ({len(comidas_a_pagar)} tiempos)")

            if st.button("✅ Confirmar pago", key="btn_confirmar_pago"):
                if comidas_a_pagar:
                    reo_sel["comidas_pagadas"].extend(comidas_a_pagar)
                    reo_sel["pagos"].append({
                        "fecha":   str(datetime.now()),
                        "monto":   total_pago,
                        "detalle": f"{len(comidas_a_pagar)} tiempos desde {fecha_inicio}"
                    })
                    guardar_estado()
                    st.success(f"✅ {len(comidas_a_pagar)} comidas registradas. Total: ${total_pago:.2f}")
                    st.rerun()
                else:
                    st.warning("No seleccionaste ningún tiempo.")

            st.divider()
            st.subheader("✔️ Marcar comidas entregadas")
            if pend_act:
                for idx, c in enumerate(reo_sel["comidas_pagadas"]):
                    if not c.get("consumida"):
                        d = datetime.fromisoformat(c["fecha"]).date()
                        if st.button(f"Entregar — {d.strftime('%d/%m')} {c['tiempo']}", key=f"ent_{rid_sel}_{idx}"):
                            reos[rid_sel]["comidas_pagadas"][idx]["consumida"] = True
                            guardar_estado()
                            st.rerun()
            else:
                st.info("Sin comidas pendientes de entrega.")

# ══════════════════════════════════════════════
#  TAB 3 — VENTAS / EXTRAS
# ══════════════════════════════════════════════
with tab_ventas:
    st.subheader("Registrar venta de productos")
    if not reos:
        st.info("No hay reos registrados.")
    else:
        busq_ventas = st.text_input("🔍 Buscar reo", placeholder="Nombre, apellido o celda...", key="busq_ventas")
        resultados_ventas = buscar_reos(busq_ventas, reos)
        opciones_ventas = {f"{r['nombre']} — Celda {r['celda']} [{rid}]": rid for rid, r in resultados_ventas}

        if not opciones_ventas:
            st.warning("Sin resultados.")
        else:
            sel3   = st.selectbox("Seleccionar reo", list(opciones_ventas.keys()), key="sel_ventas")
            rid3   = opciones_ventas[sel3]
            reo3   = reos[rid3]
            producto = st.selectbox("Producto", list(MAP_KEY.keys()), key="sel_producto_venta")
            precio   = PRECIOS[producto]
            campo    = MAP_KEY[producto]
            dias_v   = dias_restantes(reo3.get(campo), FRECUENCIAS[producto])

            st.info(f"Precio: **${precio:.2f}**")
            if reo3.get(campo):
                st.markdown(f"Última entrega: **{fecha_str(reo3.get(campo))}** — {badge_dias(dias_v)}")
            else:
                st.caption("Sin registro previo.")

            if st.button(f"🛒 Registrar {producto}"):
                reos[rid3][campo] = str(datetime.now())
                reos[rid3]["pagos"].append({
                    "fecha":   str(datetime.now()),
                    "monto":   precio,
                    "detalle": producto
                })
                guardar_estado()
                st.success(f"✅ {producto} registrado para {reo3['nombre']}.")
                st.rerun()

# ══════════════════════════════════════════════
#  TAB 4 — ALERTAS
# ══════════════════════════════════════════════
with tab_alertas:
    st.subheader("🔔 Alertas y vencimientos")
    hay_alertas = False

    for rid, r in reos.items():
        alertas_reo = []
        for prod, freq in FRECUENCIAS.items():
            dias = dias_restantes(r.get(MAP_KEY[prod]), freq)
            if dias is not None and dias <= 3:
                alertas_reo.append((prod, dias))
        sin_comidas = len(calcular_comidas_pendientes(r)) == 0

        if alertas_reo or sin_comidas:
            hay_alertas = True
            with st.expander(f"⚠️ {r['nombre']} — Celda {r['celda']} [{rid}]"):
                if sin_comidas:
                    st.markdown('<div class="alerta-roja">🍽️ <b>Sin comidas pagadas</b> — Necesita recarga.</div>', unsafe_allow_html=True)
                for prod, dias in alertas_reo:
                    if dias < 0:
                        clase, msg = "alerta-roja",     f"🔴 <b>{prod}</b> — Vencido hace {abs(dias)} días"
                    elif dias == 0:
                        clase, msg = "alerta-naranja",  f"🟠 <b>{prod}</b> — Vence HOY"
                    else:
                        clase, msg = "alerta-amarilla", f"🟡 <b>{prod}</b> — Vence en {dias} días"
                    st.markdown(f'<div class="{clase}">{msg}</div>', unsafe_allow_html=True)

    if not hay_alertas:
        st.success("✅ Todo al día — sin alertas pendientes.")

# ══════════════════════════════════════════════
#  TAB 5 — REPORTE
# ══════════════════════════════════════════════
with tab_reporte:
    st.subheader("📊 Reporte general")
    if not reos:
        st.info("No hay datos.")
    else:
        # Filtro para el reporte
        busq_rep = st.text_input("🔍 Filtrar reporte", placeholder="Nombre, apellido o celda...", key="busq_reporte")
        resultados_rep = buscar_reos(busq_rep, reos)

        filas = []
        for rid, r in resultados_rep:
            pend      = calcular_comidas_pendientes(r)
            prox_limp = prox_ropa = "—"
            if r.get("ult_kit_limpieza"):
                prox_limp = (datetime.fromisoformat(r["ult_kit_limpieza"]).date() + timedelta(days=7)).strftime("%d/%m/%Y")
            if r.get("ult_kit_ropa"):
                prox_ropa = (datetime.fromisoformat(r["ult_kit_ropa"]).date() + timedelta(days=20)).strftime("%d/%m/%Y")

            filas.append({
                "ID":              rid,
                "Nombre":          r["nombre"],
                "Celda":           r["celda"],
                "Razón captura":   r.get("razon_captura", "—") or "—",
                "Comidas pagadas": len(pend),
                "Tiempos":         tiempos_pendientes_str(r),
                "Prox. Kit Limp.": prox_limp,
                "Prox. Kit Ropa":  prox_ropa,
                "Ult. Agua":       fecha_str(r.get("ult_fardo_agua")),
                "Ult. Papel":      fecha_str(r.get("ult_papel_higienico")),
                "Reembolso pend.": "Sí" if r.get("reembolso_pendiente") else "No",
                "Comprobantes":    len([rec for rec in st.session_state.recibos if rec.get("reo_id") == rid]),
            })

        df = pd.DataFrame(filas)
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Descargar CSV", data=csv, file_name=f"reporte_beraca_{hoy()}.csv", mime="text/csv")

# ══════════════════════════════════════════════
#  TAB 6 — REEMBOLSOS
# ══════════════════════════════════════════════
with tab_reembolsos:
    st.subheader("💰 Gestión de Reembolsos")
    st.caption("Genera reembolsos para reos que pagaron más días de alimentación de los que estuvieron recluidos.")

    if not reos:
        st.info("No hay reos registrados.")
    else:
        busq_remb = st.text_input("🔍 Buscar reo", placeholder="Nombre, apellido o celda...", key="busq_reembolso")
        resultados_remb = buscar_reos(busq_remb, reos)
        opciones_remb = {f"{r['nombre']} — Celda {r['celda']} [{rid}]": rid for rid, r in resultados_remb}

        if not opciones_remb:
            st.warning("Sin resultados.")
        else:
            sel_r  = st.selectbox("Seleccionar reo", list(opciones_remb.keys()), key="sel_reembolso")
            rid_r  = opciones_remb[sel_r]
            reo_r  = reos[rid_r]

            pend_r = calcular_comidas_pendientes(reo_r)
            monto_r = calcular_monto_reembolso(pend_r)

            col_i, col_d = st.columns(2)
            with col_i:
                st.metric("Comidas pagadas no consumidas", len(pend_r))
            with col_d:
                st.metric("Monto a reembolsar", f"${monto_r:.2f}")

            if pend_r:
                st.write("**Detalle de comidas a reembolsar:**")
                resumen_r = {}
                for c in pend_r:
                    resumen_r.setdefault(c["fecha"][:10], []).append(c["tiempo"])
                for f, ts in sorted(resumen_r.items()):
                    d = datetime.fromisoformat(f).date()
                    st.markdown(f"- **{d.strftime('%d/%m/%Y')}**: {', '.join(ts)}")

                st.markdown("---")
                motivo_remb = st.selectbox(
                    "Motivo del reembolso",
                    ["Reo liberado antes de lo esperado", "Reo trasladado", "Error en el pago", "Otro"],
                    key="sel_motivo_reembolso"
                )
                obs_remb = st.text_input("Observaciones adicionales (opcional)", key="inp_obs_reembolso")

                col_btn1, col_btn2 = st.columns(2)

                with col_btn1:
                    if st.button("✅ Confirmar reembolso completo", key="btn_reembolso_total"):
                        # Marcar todas las comidas pendientes como "reembolsadas"
                        for idx, c in enumerate(reos[rid_r]["comidas_pagadas"]):
                            if not c.get("consumida"):
                                reos[rid_r]["comidas_pagadas"][idx]["consumida"] = True
                                reos[rid_r]["comidas_pagadas"][idx]["reembolsada"] = True

                        reos[rid_r].setdefault("reembolsos", []).append({
                            "fecha":   str(datetime.now()),
                            "monto":   monto_r,
                            "comidas": len(pend_r),
                            "motivo":  motivo_remb,
                            "obs":     obs_remb,
                        })
                        reos[rid_r]["reembolso_pendiente"] = False
                        guardar_estado()
                        st.success(f"✅ Reembolso de ${monto_r:.2f} registrado para {reo_r['nombre']}.")
                        st.rerun()

                with col_btn2:
                    if st.button("🕐 Marcar como pendiente de entrega", key="btn_reembolso_pendiente"):
                        reos[rid_r]["reembolso_pendiente"] = True
                        reos[rid_r].setdefault("reembolsos", []).append({
                            "fecha":   str(datetime.now()),
                            "monto":   monto_r,
                            "comidas": len(pend_r),
                            "motivo":  motivo_remb,
                            "obs":     obs_remb,
                            "estado":  "pendiente",
                        })
                        guardar_estado()
                        st.warning(f"💰 Reembolso de ${monto_r:.2f} marcado como pendiente para {reo_r['nombre']}.")
                        st.rerun()
            else:
                st.info("Este reo no tiene comidas pendientes — no aplica reembolso.")

            # Historial de reembolsos del reo seleccionado
            hist_remb = reo_r.get("reembolsos", [])
            if hist_remb:
                st.divider()
                st.write("**Historial de reembolsos de este reo:**")
                for remb in reversed(hist_remb):
                    estado = remb.get("estado", "pagado")
                    color  = "#e53e3e" if estado == "pendiente" else "#38a169"
                    st.markdown(f"""
- **{remb['fecha'][:10]}** — ${remb['monto']:.2f} ({remb['comidas']} comidas) — 
<span style="color:{color};font-weight:600">{estado.upper()}</span> — {remb['motivo']}
""", unsafe_allow_html=True)

    st.divider()
    st.subheader("📋 Todos los reembolsos pendientes")
    pendientes_globales = [(rid, r) for rid, r in reos.items() if r.get("reembolso_pendiente")]
    if not pendientes_globales:
        st.success("✅ Sin reembolsos pendientes.")
    else:
        for rid, r in pendientes_globales:
            pend_g = calcular_comidas_pendientes(r)
            monto_g = calcular_monto_reembolso(pend_g)
            st.markdown(f"""<div class="reembolso-box">
                💰 <b>{r['nombre']}</b> &nbsp; <code>{rid}</code> — Celda {r['celda']}<br>
                Comidas sin consumir: <b>{len(pend_g)}</b> &nbsp;·&nbsp; Monto: <b>${monto_g:.2f}</b>
            </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
#  TAB 7 — COMPROBANTES
# ══════════════════════════════════════════════
with tab_comprobantes:
    st.subheader("🧾 Generar Comprobante de Pago")
    st.caption("Genera un recibo imprimible para el familiar que realizó el pago.")

    if not reos:
        st.info("No hay reos registrados.")
    else:
        col_form_rec, col_prev = st.columns([1, 1.2])

        with col_form_rec:
            busq_rec = st.text_input("🔍 Buscar reo", placeholder="Nombre, apellido o celda...", key="busq_comp")
            res_rec  = buscar_reos(busq_rec, reos)
            opc_rec  = {f"{r['nombre']} — Celda {r['celda']} [{rid}]": rid for rid, r in res_rec}

            if not opc_rec:
                st.warning("Sin resultados.")
            else:
                sel_rec = st.selectbox("Seleccionar reo", list(opc_rec.keys()), key="sel_comp_reo")
                rid_rec = opc_rec[sel_rec]
                reo_rec = reos[rid_rec]

                st.markdown("---")
                familiar_rec = st.text_input("Nombre del familiar / pagador (opcional)", key="inp_familiar_rec", placeholder="Ej: María López")
                notas_rec    = st.text_input("Notas adicionales (opcional)", key="inp_notas_rec", placeholder="Ej: Pago adelantado semana del 5 al 12")

                st.markdown("**¿Qué incluir en el comprobante?**")
                incluir_comidas = st.checkbox("Comidas pagadas (pendientes de entrega)", value=True, key="chk_rec_comidas")
                incluir_extras  = st.checkbox("Productos y extras recientes", value=True, key="chk_rec_extras")

                st.markdown("---")

                # Vista previa de lo que se incluirá
                comidas_rec = []
                if incluir_comidas:
                    comidas_rec = calcular_comidas_pendientes(reo_rec)
                    st.write(f"🍽️ Comidas pendientes: **{len(comidas_rec)}** × $2.50 = **${len(comidas_rec)*2.50:.2f}**")

                extras_rec = []
                total_extras_rec = 0.0
                if incluir_extras:
                    # Tomar los últimos pagos de productos (no comidas)
                    for pago in reo_rec.get("pagos", []):
                        det = pago.get("detalle", "")
                        if det in MAP_KEY:
                            prox = None
                            campo_k = MAP_KEY[det]
                            ult = reo_rec.get(campo_k)
                            if ult:
                                prox_d = datetime.fromisoformat(str(ult)).date() + timedelta(days=FRECUENCIAS[det])
                                prox = prox_d.strftime("%d/%m/%Y")
                            extras_rec.append({
                                "producto": det,
                                "precio":   pago.get("monto", PRECIOS.get(det, 0)),
                                "proxima_renovacion": prox or "",
                                "fecha_pago": pago.get("fecha","")[:10],
                            })
                            total_extras_rec += pago.get("monto", 0)
                    # Mostrar solo los últimos 5 (más recientes)
                    extras_rec = extras_rec[-5:]
                    if extras_rec:
                        st.write(f"📦 Extras incluidos: **{len(extras_rec)}** productos — **${total_extras_rec:.2f}**")

                total_rec = len(comidas_rec) * 2.50 + total_extras_rec
                st.markdown(f"### 💰 Total en comprobante: **${total_rec:.2f}**")

                if st.button("🧾 Generar comprobante", key="btn_generar_rec"):
                    num_rec    = generar_num_recibo()
                    fecha_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                    recibo_data = {
                        "numero":      num_rec,
                        "fecha_hora":  fecha_hora,
                        "reo_nombre":  reo_rec["nombre"],
                        "reo_id":      rid_rec,
                        "celda":       reo_rec["celda"],
                        "familiar":    familiar_rec,
                        "notas":       notas_rec,
                        "comidas":     comidas_rec,
                        "extras":      extras_rec,
                        "total":       total_rec,
                    }

                    html_rec = generar_html_recibo(recibo_data)

                    # Guardar en historial de recibos
                    st.session_state.recibos.append({
                        **recibo_data,
                        "n_comidas": len(comidas_rec),
                        "n_extras":  len(extras_rec),
                    })
                    guardar_estado()

                    st.session_state["ultimo_recibo_html"] = html_rec
                    st.session_state["ultimo_recibo_num"]  = num_rec
                    st.success(f"✅ Comprobante {num_rec} generado.")
                    st.rerun()

        with col_prev:
            st.markdown("**Vista previa y descarga:**")
            if "ultimo_recibo_html" in st.session_state:
                html_bytes = st.session_state["ultimo_recibo_html"].encode("utf-8")
                num_prev   = st.session_state.get("ultimo_recibo_num", "recibo")
                st.download_button(
                    label="⬇️ Descargar comprobante (HTML imprimible)",
                    data=html_bytes,
                    file_name=f"comprobante_{num_prev}.html",
                    mime="text/html",
                    key="btn_dl_recibo"
                )
                st.caption("Abre el archivo descargado en tu navegador y usa Ctrl+P / Cmd+P para imprimir o guardar como PDF.")

                # Previsualización embebida
                st.components.v1.html(st.session_state["ultimo_recibo_html"], height=600, scrolling=True)
            else:
                st.info("Aquí aparecerá la vista previa del comprobante una vez generado.")

        st.divider()
        st.subheader("📋 Historial de comprobantes emitidos")
        recibos_hist = st.session_state.recibos
        if not recibos_hist:
            st.info("Aún no se han generado comprobantes.")
        else:
            busq_rec_hist = st.text_input("🔍 Filtrar por reo o número", key="busq_rec_hist", placeholder="Nombre, ID o REC-...")
            filas_rec = []
            for rec in reversed(recibos_hist):
                if busq_rec_hist:
                    q = busq_rec_hist.lower()
                    if not any(q in str(v).lower() for v in [rec.get("reo_nombre",""), rec.get("reo_id",""), rec.get("numero",""), rec.get("familiar","")]):
                        continue
                filas_rec.append({
                    "No. Recibo":   rec.get("numero"),
                    "Fecha/Hora":   rec.get("fecha_hora"),
                    "Reo":          rec.get("reo_nombre"),
                    "ID":           rec.get("reo_id"),
                    "Celda":        rec.get("celda"),
                    "Familiar":     rec.get("familiar") or "—",
                    "Comidas":      rec.get("n_comidas", 0),
                    "Extras":       rec.get("n_extras", 0),
                    "Total":        f"${rec.get('total', 0):.2f}",
                })
            if filas_rec:
                df_rec = pd.DataFrame(filas_rec)
                st.dataframe(df_rec, use_container_width=True)
                csv_rec = df_rec.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Descargar historial comprobantes CSV", data=csv_rec, file_name="comprobantes_beraca.csv", mime="text/csv", key="dl_hist_rec")
            else:
                st.warning("Sin resultados.")

# ══════════════════════════════════════════════
#  TAB 8 — HISTÓRICO
# ══════════════════════════════════════════════
with tab_historico:
    st.subheader("📁 Registro histórico de bajas")
    hist = st.session_state.historico

    if not hist:
        st.info("Sin registros históricos aún.")
    else:
        busq_hist = st.text_input("🔍 Filtrar histórico", placeholder="Nombre, ID o centro penal...", key="busq_hist")

        filas_h = []
        for h in hist:
            if busq_hist:
                q = busq_hist.lower()
                if not any(q in str(v).lower() for v in [h.get("nombre",""), h.get("id",""), h.get("centro_destino",""), h.get("celda","")]):
                    continue
            filas_h.append({
                "ID":             h.get("id"),
                "Nombre":         h.get("nombre"),
                "Celda":          h.get("celda"),
                "Razón captura":  h.get("razon_captura", "—") or "—",
                "Motivo baja":    h.get("motivo_baja"),
                "Centro destino": h.get("centro_destino", "—") or "—",
                "Observaciones":  h.get("detalle_baja", "—") or "—",
                "Fecha ingreso":  h.get("fecha_ingreso", "—"),
                "Fecha baja":     h.get("fecha_baja", "")[:10],
                "Comidas reimb.": h.get("comidas_reembolsadas", 0),
                "Monto reimb.":   f"${h.get('monto_reembolso', 0):.2f}",
                "Comprobantes":   len([rec for rec in st.session_state.recibos if rec.get("reo_id") == h.get("id")]),
            })

        if not filas_h:
            st.warning("Sin resultados para esa búsqueda.")
        else:
            df_h = pd.DataFrame(filas_h)
            st.dataframe(df_h, use_container_width=True)
            csv_h = df_h.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Descargar histórico CSV", data=csv_h, file_name="historico_beraca.csv", mime="text/csv")
