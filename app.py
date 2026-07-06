import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import io
import re

# 1. CONFIGURACIÓN VISUAL ELITE
st.set_page_config(page_title="VinApp Intelligence Pro v18", layout="wide")

AZUL_VINAPP = "#0033a0"
AZUL_CLARO = "#1e4fd1"
FONDO = "#f8fafc"
VERDE_EXITO = "#10b981"
ROJO_ALERTA = "#ef4444"

# --- BLOQUE DE SEGURIDAD ---
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    st.markdown(f"<div style='text-align:center;padding:50px;'><h1 style='color:{AZUL_VINAPP};'>VinApp Global BI</h1></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        pin = st.text_input("Clave de Acceso Institucional:", type="password")
        if st.button("Entrar"):
            if pin.strip() == "vinapp_elena":
                st.session_state.auth = True
                st.rerun()
            else: st.error("Clave incorrecta")
    st.stop()

# --- CONEXIÓN GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        df = conn.read(spreadsheet=st.secrets["gsheet_url"], worksheet="VENTAS", ttl=0)
        return df.dropna(subset=['MES_ID'])
    except: return pd.DataFrame()

# --- PROCESADOR HTML (LIMPIEZA DE TOTALES) ---
def clean_currency(value):
    if pd.isna(value): return 0.0
    clean = re.sub(r'[^\d]', '', str(value))
    try: return float(clean)
    except: return 0.0

def process_html(file):
    tablas = pd.read_html(file)
    df = max(tablas, key=len)
    
    # Buscar encabezados reales
    for i in range(min(20, len(df))):
        fila = [str(x).upper() for x in df.iloc[i].values]
        if 'VALOR' in fila or 'PLAN' in fila or 'RESTAURANTE' in fila:
            df.columns = df.iloc[i]
            df = df[i+1:].reset_index(drop=True)
            break
    
    df.columns = [str(c).strip().upper() for c in df.columns]
    f_c = lambda ks: next((c for c in df.columns if any(k in c for k in ks)), None)
    
    cv, cf, cvend = f_c(['VALOR', 'TOTAL']), f_c(['FECHA', 'DIA']), f_c(['VENDEDOR'])
    cp, cfue, cc = f_c(['PLAN']), f_c(['FUENTE']), f_c(['CIUDAD'])
    cr, cfr = f_c(['RESTAURANTE', 'CLIENTE']), f_c(['PAGO', 'FRECUENCIA'])

    # --- FILTRO ANTIDUPLICADOS (TOTALES) ---
    # Convertimos valor a número primero
    df[cv] = df[cv].apply(clean_currency)
    
    # ELIMINAMOS cualquier fila que parezca un resumen o total
    # Si el restaurante está vacío, o dice "TOTAL", "SUMA", o si el valor es igual a la suma de la columna (duplicado)
    df = df[df[cr].notna()] # Elimina filas donde el nombre del restaurante es vacío
    df = df[~df[cr].astype(str).str.contains("TOTAL|SUMA|RECUENTO|VALOR|RESULTADO", case=False, na=False)]
    df = df[df[cv] > 0] # Solo filas con valor positivo (transacciones reales)
    
    # Intento de parsear fecha
    df[cf] = pd.to_datetime(df[cf], dayfirst=True, errors='coerce')
    
    return df, {'v':cv, 'f':cf, 'vend':cvend, 'plan':cp, 'fuente':cfue, 'ciudad':cc, 'rest':cr, 'freq':cfr}

# --- PANEL ADMINISTRADOR ---
with st.sidebar:
    st.title("🛡️ Admin Panel")
    if st.text_input("Clave Edición:", type="password") == "vinapp2026":
        with st.expander("⬆️ Subir / Corregir Mes", expanded=True):
            f = st.file_uploader("HTML del Mes", type="html")
            if f:
                df_raw, c_map = process_html(f)
                
                # Detección de mes
                valid_dates = df_raw[c_map['f']].dropna()
                if not valid_dates.empty:
                    m_id = valid_dates.min().strftime('%B %Y')
                    st.success(f"Mes detectado: {m_id}")
                else:
                    st.warning("No se detectó fecha automática.")
                    mes_n = st.selectbox("Mes:", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
                    anio_n = st.selectbox("Año:", ["2026", "2027"])
                    m_id = f"{mes_n} {anio_n}"

                st.markdown("### Datos del Embudo")
                co = st.number_input("1. Contactos", 0, 10000, 200)
                ag = st.number_input("2. Agendó Demo", 0, 10000, 50)
                asi = st.number_input("3. Asistió", 0, 10000, 20)
                com = st.number_input("4. Compró", 0, 10000, len(df_raw))

                if st.button("Guardar en Google Sheets"):
                    df_to_save = pd.DataFrame({
                        'MES_ID': m_id,
                        'FECHA': df_raw[c_map['f']].astype(str),
                        'RESTAURANTE': df_raw[c_map['rest']],
                        'VALOR': df_raw[c_map['v']],
                        'VENDEDOR': df_raw[c_map['vend']],
                        'PLAN': df_raw[c_map['plan']],
                        'FUENTE': df_raw[c_map['fuente']],
                        'CIUDAD': df_raw[c_map['ciudad']],
                        'FRECUENCIA': df_raw[c_map['freq']],
                        'CONTACTOS': co, 'AGENDO': ag, 'ASISTIO': asi, 'COMPRO': com
                    })
                    master = load_data()
                    if not master.empty: master = master[master['MES_ID'] != m_id]
                    final = pd.concat([master, df_to_save], ignore_index=True)
                    conn.update(spreadsheet=st.secrets["gsheet_url"], worksheet="VENTAS", data=final)
                    st.success("¡Información Sincronizada!"); st.rerun()

# --- CUERPO DASHBOARD ---
master_db = load_data()

if not master_db.empty:
    # Estilos CSS para el Dashboard
    st.markdown("""<style>
    .stMetric { background-color: white; border-radius: 15px; border-top: 5px solid #0033a0; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .card-resumen { background-color: white; padding: 20px; border-radius: 15px; border: 1px solid #e2e8f0; text-align: center; }
    .ganador { color: #f59e0b; font-weight: bold; }
    </style>""", unsafe_allow_html=True)

    master_db['FECHA'] = pd.to_datetime(master_db['FECHA'], errors='coerce')
    meses_lista = sorted(master_db['MES_ID'].unique(), key=lambda x: datetime.strptime(x, '%B %Y'))
    tabs = st.tabs([f"📊 {m}" for m in meses_lista])

    for i, m_sel in enumerate(meses_lista):
        with tabs[i]:
            df = master_db[master_db['MES_ID'] == m_sel]
            df_p = master_db[master_db['MES_ID'] == meses_lista[i-1]] if i > 0 else None
            v_act, l_act = df['VALOR'].sum(), len(df)
            t_act = v_act/l_act if l_act>0 else 0
            
            st.title(f"Dashboard {m_sel}")
            
            # KPIs
            k1, k2, k3 = st.columns(3)
            k1.metric("VENTAS TOTALES", f"$ {v_act:,.0f}")
            k2.metric("LICENCIAS NUEVAS", l_act)
            k3.metric("TICKET PROMEDIO", f"$ {t_act:,.0f}")

            # 1. EMBUDO COMPLETO
            st.divider()
            st.subheader("🌪️ Análisis de Embudo")
            e1, e2 = st.columns([2,1])
            with e1:
                ef = {'co': df['CONTACTOS'].iloc[0], 'ag': df['AGENDO'].iloc[0], 'as': df['ASISTIO'].iloc[0], 'cp': df['COMPRO'].iloc[0]}
                fig_f = go.Figure(go.Funnel(y=["Contactos", "Agendó", "Asistió", "Compró"], x=[ef['co'], ef['ag'], ef['as'], ef['cp']], 
                                          marker={"color": [AZUL_VINAPP, AZUL_CLARO, "#4b7aed", VERDE_EXITO]},
                                          textinfo = "value+percent initial"))
                st.plotly_chart(fig_f, use_container_width=True)
            with e2:
                st.markdown("#### Eficiencia Operativa")
                t_asist = (ef['as']/ef['ag']*100) if ef['ag']>0 else 0
                ina_p = ((ef['ag'] - ef['as'])/ef['ag']*100) if ef['ag']>0 else 0
                st.metric("TASA ASISTENCIA", f"{t_asist:.1f}%")
                st.metric("INA-SISTENCIA (%)", f"{ina_p:.1f}%", f"{int(ef['ag']-ef['as'])} personas", delta_color="inverse")
                st.metric("TASA CIERRE (COMPRÓ)", f"{(ef['cp']/ef['as']*100):.1f}%")

            # 2. TABLAS Y GRÁFICAS (CON 🌟)
            st.divider()
            st.subheader("📦 Detalle por Plan y Vendedor")
            col_p1, col_p2 = st.columns(2)
            p_df = df.groupby('PLAN').agg(Cantidad=('VALOR','count'), Aporte=('VALOR','sum')).reset_index().sort_values('Aporte', ascending=False)
            with col_p1: st.plotly_chart(px.bar(p_df, x='PLAN', y='Cantidad', text_auto=True, color_discrete_sequence=[AZUL_CLARO], title="Cantidad por Plan"), use_container_width=True)
            with col_p2:
                p_df['🌟'] = p_df['Aporte'].apply(lambda x: '🌟' if x == p_df['Aporte'].max() else '')
                st.table(p_df.assign(Aporte=p_df['Aporte'].map("$ {:,.0f}".format)))

            col_v1, col_v2 = st.columns(2)
            v_df = df.groupby('VENDEDOR').agg(Licencias=('VALOR','count'), Aporte=('VALOR','sum')).reset_index().sort_values('Aporte', ascending=False)
            with col_v1: st.plotly_chart(px.bar(v_df, x='VENDEDOR', y='Aporte', text_auto='.2s', color_discrete_sequence=[AZUL_VINAPP], title="Aporte por Vendedor"), use_container_width=True)
            with col_v2:
                v_df['🌟'] = v_df['Licencias'].apply(lambda x: '🌟' if x == v_df['Licencias'].max() else '')
                st.table(v_df.assign(Aporte=v_df['Aporte'].map("$ {:,.0f}".format)))

            # 3. CIUDAD TABLA TÉCNICA
            st.subheader("📍 Desempeño por Ciudad")
            ci_df = df.groupby('CIUDAD').agg(Ventas=('VALOR','count'), Aporte=('VALOR','sum')).reset_index().sort_values('Aporte', ascending=False)
            ci_df['🌟'] = ci_df['Aporte'].apply(lambda x: '🌟' if x == ci_df['Aporte'].max() else '')
            st.table(ci_df.assign(Aporte=ci_df['Aporte'].map("$ {:,.0f}".format)))

            # 4. RESUMEN CRECIMIENTO
            if df_p is not None:
                st.divider()
                st.subheader("📊 Resumen de Crecimiento vs Mes Anterior")
                cr1, cr2, cr3 = st.columns(3)
                v_ant, l_ant = df_p['VALOR'].sum(), len(df_p)
                t_ant = v_ant/l_ant if l_ant>0 else 0
                def res_card(tit, act, ant, iso=True):
                    d = ((act-ant)/ant*100) if ant>0 else 0
                    color = "delta-up" if d>=0 else "delta-down"
                    val = f"$ {act:,.0f}" if iso else f"{act}"
                    return f"<div class='card-resumen'><p>{tit}</p><h3>{val}</h3><p class='{color}'>{d:+.1f}%</p></div>"
                cr1.markdown(res_card("Crecimiento Ventas", v_act, v_ant), unsafe_allow_html=True)
                cr2.markdown(res_card("Licencias Nuevas", l_act, l_ant, False), unsafe_allow_html=True)
                cr3.markdown(res_card("Ticket Promedio", t_act, t_ant), unsafe_allow_html=True)

            # 5. CONSTRUCTOR DIDÁCTICO (FILTRADO POR MES)
            with st.expander("🎨 Constructor de Gráficas Manual"):
                cx = st.selectbox(f"Categoría:", ["VENDEDOR", "PLAN", "FUENTE", "CIUDAD"], key=f"cxx_{i}")
                st.plotly_chart(px.bar(df.groupby(cx)['VALOR'].sum().reset_index(), x=cx, y='VALOR', color=cx, text_auto='.2s'))

    # 6. EVOLUCIÓN HISTÓRICA FINAL
    st.divider()
    st.header("📈 Evolución Histórica: Ingresos vs Licencias")
    h_data = master_db.groupby('MES_ID').agg({'VALOR':'sum', 'RESTAURANTE':'count'}).reset_index()
    h_data['ORDEN'] = h_data['MES_ID'].apply(lambda x: datetime.strptime(x, '%B %Y'))
    h_data = h_data.sort_values('ORDEN')
    fig_h = go.Figure()
    fig_h.add_trace(go.Bar(x=h_data['MES_ID'], y=h_data['VALOR'], name="Ingresos ($)", marker_color=AZUL_VINAPP))
    fig_h.add_trace(go.Scatter(x=h_data['MES_ID'], y=h_data['RESTAURANTE'], name="Licencias (und)", yaxis="y2", line=dict(color=VERDE_EXITO, width=4)))
    fig_h.update_layout(
        yaxis=dict(title=dict(text="Ingresos ($)", font=dict(color=AZUL_VINAPP)), tickfont=dict(color=AZUL_VINAPP)),
        yaxis2=dict(title=dict(text="Licencias (und)", font=dict(color=VERDE_EXITO)), tickfont=dict(color=VERDE_EXITO), overlaying='y', side='right'),
        template="plotly_white", legend=dict(orientation="h", y=1.1)
    )
    st.plotly_chart(fig_h, use_container_width=True)

else: st.warning("Sube el primer reporte en el Admin")
