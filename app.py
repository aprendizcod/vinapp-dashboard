import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import io
import re

# 1. CONFIGURACIÓN VISUAL ELITE
st.set_page_config(page_title="VinApp Intelligence Pro v17", layout="wide")

AZUL_VINAPP = "#0033a0"
AZUL_CLARO = "#1e4fd1"
FONDO = "#f8fafc"
VERDE_EXITO = "#10b981"
ROJO_ALERTA = "#ef4444"

# --- SEGURIDAD ---
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    st.markdown(f"<h1 style='text-align:center;color:{AZUL_VINAPP};'>VinApp Global BI</h1>", unsafe_allow_html=True)
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

# --- PROCESADOR HTML MEJORADO ---
def clean_currency(value):
    if pd.isna(value): return 0.0
    clean = re.sub(r'[^\d]', '', str(value))
    try: return float(clean)
    except: return 0.0

def process_html(file):
    tablas = pd.read_html(file)
    df = max(tablas, key=len)
    
    # Detección de cabecera real
    header_found = False
    for i in range(min(20, len(df))):
        fila = [str(x).upper() for x in df.iloc[i].values]
        if 'VALOR' in fila or 'PLAN' in fila or 'RESTAURANTE' in fila:
            df.columns = df.iloc[i]
            df = df[i+1:].reset_index(drop=True)
            header_found = True
            break
    
    df.columns = [str(c).strip().upper() for c in df.columns]
    f_c = lambda ks: next((c for c in df.columns if any(k in c for k in ks)), None)
    
    cv, cf, cvend = f_c(['VALOR', 'TOTAL']), f_c(['FECHA', 'DIA']), f_c(['VENDEDOR'])
    cp, cfue, cc = f_c(['PLAN']), f_c(['FUENTE']), f_c(['CIUDAD'])
    cr, cfr = f_c(['RESTAURANTE', 'CLIENTE']), f_c(['PAGO', 'FRECUENCIA'])

    # Limpieza de filas de "TOTAL" para evitar duplicados en Mayo
    df[cv] = df[cv].apply(clean_currency)
    df = df[~df[cr].astype(str).str.contains("TOTAL|SUMA|RECUENTO|VALOR", case=False, na=False)]
    df = df[df[cv] > 0]
    
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
                
                # --- SOLUCIÓN AL ERROR DE NAT ---
                # Intentamos detectar el mes, si no, lo pedimos manual
                valid_dates = df_raw[c_map['f']].dropna()
                if not valid_dates.empty:
                    mes_detectado = valid_dates.min().strftime('%B %Y')
                    st.success(f"Mes detectado: {mes_detectado}")
                    m_id = mes_detectado
                else:
                    st.warning("No pude detectar la fecha automáticamente.")
                    mes_nombre = st.selectbox("Selecciona el Mes:", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
                    anio_nombre = st.selectbox("Selecciona el Año:", ["2026", "2027"])
                    m_id = f"{mes_nombre} {anio_nombre}"

                st.markdown("### Datos del Embudo")
                co = st.number_input("1. Contactos", 0, 10000, 200)
                ag = st.number_input("2. Agendó Demo", 0, 10000, 50)
                asi = st.number_input("3. Asistió", 0, 10000, 20)
                com = st.number_input("4. Compró", 0, 10000, len(df_raw)) # LIBRE

                if st.button("Guardar en Google Sheets"):
                    # Preparar dataframe final para subir
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
                    st.success(f"¡{m_id} guardado con éxito!"); st.rerun()

# --- CUERPO DASHBOARD ---
master_db = load_data()

if not master_db.empty:
    master_db['FECHA'] = pd.to_datetime(master_db['FECHA'], errors='coerce')
    # Ordenar meses por fecha real
    meses_lista = sorted(master_db['MES_ID'].unique(), key=lambda x: datetime.strptime(x, '%B %Y'))
    tabs = st.tabs([f"📊 {m}" for m in meses_lista])

    for i, m_sel in enumerate(meses_lista):
        with tabs[i]:
            df = master_db[master_db['MES_ID'] == m_sel]
            df_p = master_db[master_db['MES_ID'] == meses_lista[i-1]] if i > 0 else None
            
            v_act, l_act = df['VALOR'].sum(), len(df)
            t_act = v_act/l_act if l_act>0 else 0
            
            st.title(f"Reporte {m_sel}")
            
            # KPIs
            k1, k2, k3 = st.columns(3)
            k1.metric("VENTAS TOTALES", f"$ {v_act:,.0f}")
            k2.metric("LICENCIAS NUEVAS", l_act)
            k3.metric("TICKET PROMEDIO", f"$ {t_act:,.0f}")

            # EMBUDO COMPLETO
            st.divider()
            st.subheader("🌪️ Embudo: Contactos - Agendó - Asistió - Compró")
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

            # PLANES Y VENDEDORES
            st.divider()
            st.subheader("📦 Análisis por Plan")
            p_df = df.groupby('PLAN').agg(Cant=('VALOR','count'), Aporte=('VALOR','sum')).reset_index().sort_values('Aporte', ascending=False)
            p_df['🌟'] = p_df['Aporte'].apply(lambda x: '🌟' if x == p_df['Aporte'].max() else '')
            pc1, pc2 = st.columns(2)
            with pc1: st.plotly_chart(px.bar(p_df, x='PLAN', y='Cant', text_auto=True, color_discrete_sequence=[AZUL_CLARO]), use_container_width=True)
            with pc2: st.table(p_df.assign(Aporte=p_df['Aporte'].map("$ {:,.0f}".format)))

            st.divider()
            st.subheader("👤 Desempeño Vendedores")
            v_df = df.groupby('VENDEDOR').agg(Licencias=('VALOR','count'), Aporte=('VALOR','sum')).reset_index().sort_values('Aporte', ascending=False)
            v_df['🌟'] = v_df['Aporte'].apply(lambda x: '🌟' if x == v_df['Aporte'].max() else '')
            vc1, vc2 = st.columns(2)
            with vc1: st.plotly_chart(px.bar(v_df, x='VENDEDOR', y='Aporte', text_auto='.2s', color_discrete_sequence=[AZUL_VINAPP]), use_container_width=True)
            with vc2: st.table(v_df.assign(Aporte=v_df['Aporte'].map("$ {:,.0f}".format)))

            # CIUDAD
            st.divider()
            st.subheader("📍 Desempeño por Ciudad")
            ci_df = df.groupby('CIUDAD').agg(Ventas=('VALOR','count'), Aporte=('VALOR','sum')).reset_index().sort_values('Aporte', ascending=False)
            ci_df['🌟'] = ci_df['Aporte'].apply(lambda x: '🌟' if x == ci_df['Aporte'].max() else '')
            st.table(ci_df.assign(Aporte=ci_df['Aporte'].map("$ {:,.0f}".format)))

            # RESUMEN CRECIMIENTO
            if df_p is not None:
                st.divider()
                st.subheader("📊 Crecimiento vs Mes Anterior")
                cr1, cr2, cr3 = st.columns(3)
                v_ant, l_ant = df_p['VALOR'].sum(), len(df_p)
                t_ant = v_ant/l_ant if l_ant>0 else 0
                def res_card(tit, act, ant, iso=True):
                    d = ((act-ant)/ant*100) if ant>0 else 0
                    color = "delta-up" if d>=0 else "delta-down"
                    val = f"$ {act:,.0f}" if iso else f"{act}"
                    return f"<div class='card-resumen'><p>{tit}</p><h3>{val}</h3><p class='{color}'>{d:+.1f}%</p></div>"
                cr1.markdown(res_card("Ventas", v_act, v_ant), unsafe_allow_html=True)
                cr2.markdown(res_card("Licencias", l_act, l_ant, False), unsafe_allow_html=True)
                cr3.markdown(res_card("Ticket Promedio", t_act, t_ant), unsafe_allow_html=True)

            # CONSTRUCTOR DINÁMICO (FILTRADO POR MES)
            with st.expander("🎨 Constructor de Gráficas de este mes"):
                cx = st.selectbox(f"Categoría:", ["VENDEDOR", "PLAN", "FUENTE", "CIUDAD"], key=f"cx_{i}")
                st.plotly_chart(px.bar(df.groupby(cx)['VALOR'].sum().reset_index(), x=cx, y='VALOR', color=cx, text_auto='.2s'))

    # HISTÓRICO FINAL
    st.divider()
    st.header("📈 Evolución Histórica: Ingresos vs Licencias")
    h_data = master_db.groupby('MES_ID').agg({'VALOR':'sum', 'RESTAURANTE':'count'}).reset_index()
    h_data['ORDEN'] = h_data['MES_ID'].apply(lambda x: datetime.strptime(x, '%B %Y'))
    h_data = h_data.sort_values('ORDEN')
    fig_h = go.Figure()
    fig_h.add_trace(go.Bar(x=h_data['MES_ID'], y=h_data['VALOR'], name="Ingresos", marker_color=AZUL_VINAPP))
    fig_h.add_trace(go.Scatter(x=h_data['MES_ID'], y=h_data['RESTAURANTE'], name="Licencias", yaxis="y2", line=dict(color=VERDE_EXITO, width=4)))
    fig_h.update_layout(yaxis=dict(title="Dinero ($)"), yaxis2=dict(title="Licencias", overlaying='y', side='right'), template="plotly_white", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig_h, use_container_width=True)

else: st.warning("carga el primer mes en el panel Admin.")
