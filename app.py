import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import io
import re

# 1. ESTILO VISUAL ELITE (AZUL VINAPP)
st.set_page_config(page_title="VinApp Global BI Pro", layout="wide")

AZUL_VINAPP = "#0033a0"
AZUL_CLARO = "#1e4fd1"
FONDO = "#f8fafc"
VERDE_EXITO = "#10b981"
ROJO_ALERTA = "#ef4444"

# --- BLOQUE DE SEGURIDAD (JEFES) ---
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

# --- CONEXIÓN A GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception:
    st.error("Error de conexión. Verifica el archivo secrets.toml o los Secrets en Streamlit Cloud.")
    st.stop()

def load_data():
    try:
        # Lee la pestaña VENTAS. ttl=0 para que siempre traiga lo último
        df = conn.read(spreadsheet=st.secrets["gsheet_url"], worksheet="VENTAS", ttl=0)
        return df.dropna(subset=['MES_ID'])
    except Exception:
        return pd.DataFrame()

# --- CSS PARA TARJETAS ---
st.markdown(f"""
    <style>
    .main {{ background-color: {FONDO}; }}
    .stMetric {{ background-color: white; padding: 20px; border-radius: 15px; border-top: 5px solid {AZUL_VINAPP}; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
    .ganador {{ color: #f59e0b; font-weight: bold; }}
    .card-resumen {{ background-color: white; padding: 20px; border-radius: 15px; border: 1px solid #e2e8f0; text-align: center; }}
    .delta-up {{ color: {VERDE_EXITO}; font-weight: bold; }}
    .delta-down {{ color: {ROJO_ALERTA}; font-weight: bold; }}
    </style>
    """, unsafe_allow_html=True)

# --- PROCESADOR DE HTML ---
def clean_currency(value):
    if pd.isna(value): return 0.0
    clean = re.sub(r'[^\d]', '', str(value))
    try: return float(clean)
    except: return 0.0

def process_html(file):
    tablas = pd.read_html(file)
    df = max(tablas, key=len)
    for i in range(min(20, len(df))):
        fila = [str(x).upper() for x in df.iloc[i].values]
        if 'VALOR' in fila or 'PLAN' in fila or 'RESTAURANTE' in fila:
            df.columns = df.iloc[i]; df = df[i+1:].reset_index(drop=True); break
    df.columns = [str(c).strip().upper() for c in df.columns]
    f_col = lambda ks: next((c for c in df.columns if any(k in c for k in ks)), None)
    
    c_v = f_col(['VALOR', 'TOTAL'])
    c_f = f_col(['FECHA', 'DIA'])
    c_vend = f_col(['VENDEDOR'])
    c_p = f_col(['PLAN'])
    c_fue = f_col(['FUENTE'])
    c_c = f_col(['CIUDAD'])
    c_r = f_col(['RESTAURANTE', 'CLIENTE'])
    c_fr = f_col(['PAGO', 'FRECUENCIA'])

    df[c_v] = df[c_v].apply(clean_currency)
    df[c_f] = pd.to_datetime(df[c_f], dayfirst=True, errors='coerce')
    df = df.dropna(subset=[c_f]).query(f"{c_v} > 0")

    return pd.DataFrame({
        'FECHA': df[c_f].astype(str), 'RESTAURANTE': df[c_r], 'VALOR': df[c_v],
        'VENDEDOR': df[c_vend], 'PLAN': df[c_p], 'FUENTE': df[c_fue],
        'CIUDAD': df[c_c], 'FRECUENCIA': df[c_fr]
    })

# --- PANEL ADMIN (SIDEBAR) ---
with st.sidebar:
    st.title("Admin Panel")
    pwd = st.text_input("Clave Edición:", type="password")
    if pwd == "vinapp2026":
        with st.expander("Subir Nuevo HTML", expanded=True):
            f_in = st.file_uploader("Archivo HTML", type="html")
            if f_in:
                df_n = process_html(f_in)
                m_id = pd.to_datetime(df_n['FECHA']).min().strftime('%B %Y')
                st.info(f"Detectado: {m_id}")
                st.markdown("### Datos del Embudo")
                c_1 = st.number_input("Contactos", value=200)
                c_2 = st.number_input("Agendó Demo", value=50)
                c_3 = st.number_input("Asistió", value=20)
                c_4 = st.number_input("Compró", value=len(df_n)) # SE AGREGÓ COMPRÓ
                
                if st.button("Guardar en Google Sheets"):
                    df_n['MES_ID'], df_n['CONTACTOS'], df_n['AGENDO'], df_n['ASISTIO'], df_n['COMPRO'] = m_id, c_1, c_2, c_3, c_4
                    master = load_data()
                    if not master.empty: master = master[master['MES_ID'] != m_id]
                    final = pd.concat([master, df_n], ignore_index=True)
                    conn.update(spreadsheet=st.secrets["gsheet_url"], worksheet="VENTAS", data=final)
                    st.success("¡Datos guardados!"); st.rerun()

# --- DASHBOARD ---
df_master = load_data()
if not df_master.empty:
    df_master['FECHA'] = pd.to_datetime(df_master['FECHA'])
    meses_ord = sorted(df_master['MES_ID'].unique(), key=lambda x: datetime.strptime(x, '%B %Y'))
    tabs = st.tabs([f"📊 {m}" for m in meses_ord])

    for i, m_sel in enumerate(meses_ord):
        with tabs[i]:
            df = df_master[df_master['MES_ID'] == m_sel]
            df_prev = df_master[df_master['MES_ID'] == meses_ord[i-1]] if i > 0 else None
            
            v_act, l_act = df['VALOR'].sum(), len(df)
            t_act = v_act/l_act if l_act>0 else 0

            st.header(f"Dashboard Comercial - {m_sel}")
            k1, k2, k3 = st.columns(3)
            k1.metric("VENTAS TOTALES", f"$ {v_act:,.0f}")
            k2.metric("LICENCIAS NUEVAS", l_act)
            k3.metric("TICKET PROMEDIO", f"$ {t_act:,.0f}")

            # 1. EMBUDO (CON COMPRÓ)
            st.divider()
            st.subheader("🌪️ Embudo Dinámico")
            e1, e2 = st.columns([2,1])
            with e1:
                ef = {'co': df['CONTACTOS'].iloc[0], 'ag': df['AGENDO'].iloc[0], 'as': df['ASISTIO'].iloc[0], 'cp': df['COMPRO'].iloc[0]}
                fig_f = go.Figure(go.Funnel(y=["Contactos", "Agendó", "Asistió", "Compró"], x=[ef['co'], ef['ag'], ef['as'], ef['cp']], marker={"color": [AZUL_VINAPP, AZUL_CLARO, "#4b7aed", VERDE_EXITO]}))
                st.plotly_chart(fig_f, use_container_width=True)
            with e2:
                st.metric("TASA ASISTENCIA", f"{(ef['as']/ef['ag']*100):.1f}%" if ef['ag']>0 else "0%")
                st.metric("INASISTENCIA", f"{int(ef['ag']-ef['as'])} pros.", delta_color="inverse")
                st.metric("TASA CIERRE (COMPRÓ)", f"{(ef['cp']/ef['as']*100):.1f}%" if ef['as']>0 else "0%")

            # 2. PLANES Y VENDEDORES
            st.divider()
            c_p1, c_p2 = st.columns(2)
            with c_p1:
                st.markdown("### Ventas por Plan")
                p_df = df.groupby('PLAN').agg(Cant=('VALOR','count'), Aporte=('VALOR','sum')).reset_index().sort_values('Aporte', ascending=False)
                st.plotly_chart(px.bar(p_df, x='PLAN', y='Cant', text_auto=True, color_discrete_sequence=[AZUL_CLARO]), use_container_width=True)
            with c_p2:
                p_df['🌟'] = p_df['Aporte'].apply(lambda x: '🌟' if x == p_df['Aporte'].max() else '')
                st.table(p_df.assign(Aporte=p_df['Aporte'].map("$ {:,.0f}".format)))

            # Vendedores
            st.divider()
            c_v1, c_v2 = st.columns(2)
            with c_v1:
                st.markdown("### Desempeño Vendedores")
                v_df = df.groupby('VENDEDOR').agg(Lic=('VALOR','count'), Aporte=('VALOR','sum')).reset_index().sort_values('Aporte', ascending=False)
                st.plotly_chart(px.bar(v_df, x='VENDEDOR', y='Aporte', text_auto='.2s', color_discrete_sequence=[AZUL_VINAPP]), use_container_width=True)
            with c_v2:
                v_df['🌟'] = v_df['Lic'].apply(lambda x: '🌟' if x == v_df['Lic'].max() else '')
                st.table(v_df.assign(Aporte=v_df['Aporte'].map("$ {:,.0f}".format)))

            # CIUDAD TABLA (TAL CUAL PEDISTE)
            st.subheader("📍 Desempeño por Ciudad")
            ci_df = df.groupby('CIUDAD').agg(Ventas=('VALOR','count'), Aporte=('VALOR','sum')).reset_index().sort_values('Aporte', ascending=False)
            ci_df['🌟'] = ci_df['Aporte'].apply(lambda x: '🌟' if x == ci_df['Aporte'].max() else '')
            st.table(ci_df.assign(Aporte=ci_df['Aporte'].map("$ {:,.0f}".format)))

            # 3. RESUMEN CRECIMIENTO VS MES ANTERIOR
            st.divider()
            st.subheader("📊 Resumen de Crecimiento vs Mes Anterior")
            if df_prev is not None:
                cr1, cr2, cr3 = st.columns(3)
                v_ant, l_ant = df_prev['VALOR'].sum(), len(df_prev)
                t_ant = v_ant/l_ant if l_ant>0 else 0
                def metric_card(tit, act, ant, iso=True):
                    d = ((act-ant)/ant*100) if ant>0 else 0
                    cl = "delta-up" if d>=0 else "delta-down"
                    val = f"$ {act:,.0f}" if iso else f"{act}"
                    return f"<div class='card-resumen'><p>{tit}</p><h3>{val}</h3><p class='{cl}'>{d:+.1f}%</p></div>"
                cr1.markdown(metric_card("Ventas", v_act, v_ant), unsafe_allow_html=True)
                cr2.markdown(metric_card("Licencias", l_act, l_ant, False), unsafe_allow_html=True)
                cr3.markdown(metric_card("Ticket Prom.", t_act, t_ant), unsafe_allow_html=True)
            else: st.info("Sin mes anterior para comparar.")

    # 4. EVOLUCIÓN HISTÓRICA FINAL
    st.divider()
    st.header("📈 Evolución Histórica: Ingresos vs Licencias")
    h_data = df_master.groupby('MES_ID').agg({'VALOR':'sum', 'RESTAURANTE':'count'}).reset_index()
    h_data['ORDEN'] = h_data['MES_ID'].apply(lambda x: datetime.strptime(x, '%B %Y'))
    h_data = h_data.sort_values('ORDEN')
    fig_h = go.Figure()
    fig_h.add_trace(go.Bar(x=h_data['MES_ID'], y=h_data['VALOR'], name="Ingresos", marker_color=AZUL_VINAPP))
    fig_h.add_trace(go.Scatter(x=h_data['MES_ID'], y=h_data['RESTAURANTE'], name="Licencias", yaxis="y2", line=dict(color=VERDE_EXITO, width=4)))
    fig_h.update_layout(yaxis=dict(title="Ingresos ($)"), yaxis2=dict(title="Licencias", overlaying='y', side='right'), template="plotly_white", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig_h, use_container_width=True)

else: st.warning("Sube un mes en el panel Administrador para activar el Dashboard.")
