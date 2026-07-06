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

# --- BLOQUE DE SEGURIDAD (ENTRADA JEFES) ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.markdown(f"""
        <div style='text-align:center;padding:50px;'>
            <h1 style='color:{AZUL_VINAPP};'>VinApp Global BI</h1>
            <p style='color:#64748b;'>Sistema Privado de Inteligencia de Negocios</p>
        </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        pin = st.text_input("Clave de Acceso Institucional:", type="password")
        if st.button("Entrar al Dashboard"):
            if pin.strip() == "vinapp_elena":
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("⚠️ Clave incorrecta.")
    st.stop()

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_all_data():
    try:
        # Lee la pestaña VENTAS de tu Google Sheet
        df = conn.read(spreadsheet=st.secrets["gsheet_url"], worksheet="VENTAS", ttl=0)
        return df.dropna(subset=['MES_ID'])
    except Exception:
        return pd.DataFrame()

# --- CSS PARA TARJETAS Y TABLAS ---
st.markdown(f"""
    <style>
    .main {{ background-color: {FONDO}; font-family: 'Inter', sans-serif; }}
    .stMetric {{ background-color: white; padding: 20px; border-radius: 15px; border-top: 5px solid {AZUL_VINAPP}; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
    .ganador {{ color: #f59e0b; font-weight: bold; }}
    .card-resumen {{ background-color: white; padding: 20px; border-radius: 15px; border: 1px solid #e2e8f0; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }}
    .delta-up {{ color: {VERDE_EXITO}; font-weight: bold; font-size: 0.9rem; }}
    .delta-down {{ color: {ROJO_ALERTA}; font-weight: bold; font-size: 0.9rem; }}
    .stTable {{ background-color: white; border-radius: 15px; overflow: hidden; }}
    </style>
    """, unsafe_allow_html=True)

# --- PROCESADOR DE HTML (INTELIGENCIA PARA ABRIL) ---
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
        if any(k in fila for k in ['VALOR', 'PLAN', 'RESTAURANTE']):
            df.columns = df.iloc[i]; df = df[i+1:].reset_index(drop=True); break
    df.columns = [str(c).strip().upper() for c in df.columns]
    f_col = lambda ks: next((c for c in df.columns if any(k in c for k in ks)), None)
    
    cv, cf, cvend = f_col(['VALOR', 'TOTAL']), f_col(['FECHA', 'DIA']), f_col(['VENDEDOR'])
    cp, cfue, cc = f_col(['PLAN']), f_col(['FUENTE']), f_col(['CIUDAD'])
    cr, cfr = f_col(['RESTAURANTE', 'CLIENTE']), f_col(['PAGO', 'FRECUENCIA'])

    df[cv] = df[cv].apply(clean_currency)
    df[cf] = pd.to_datetime(df[cf], dayfirst=True, errors='coerce')
    df = df.dropna(subset=[cf]).query(f"{cv} > 0")

    return pd.DataFrame({
        'FECHA': df[cf].astype(str), 'RESTAURANTE': df[cr], 'VALOR': df[cv],
        'VENDEDOR': df[cvend], 'PLAN': df[cp], 'FUENTE': df[cfue],
        'CIUDAD': df[cc], 'FRECUENCIA': df[cfr]
    })

# --- BARRA LATERAL (ELENA ADMIN) ---
with st.sidebar:
    st.title("⚙️ Elena Admin")
    admin_pwd = st.text_input("Contraseña de Edición:", type="password")
    if admin_pwd == "vinapp2026":
        with st.expander("⬆️ Cargar Nuevo Mes", expanded=True):
            f_in = st.file_uploader("Subir HTML", type="html")
            if f_in:
                df_n = process_html(f_in)
                m_id = pd.to_datetime(df_n['FECHA']).min().strftime('%B %Y')
                st.info(f"Configurando: {m_id}")
                c_1 = st.number_input("Contactos", 200)
                c_2 = st.number_input("Agendó Demo", 50)
                c_3 = st.number_input("Asistió", 20)
                c_4 = st.number_input("Compró", len(df_n))
                if st.button("Guardar en Google Sheets"):
                    df_n['MES_ID'], df_n['CONTACTOS'], df_n['AGENDO'], df_n['ASISTIO'], df_n['COMPRO'] = m_id, c_1, c_2, c_3, c_4
                    master_db = load_all_data()
                    if not master_db.empty: master_db = master_db[master_db['MES_ID'] != m_id]
                    final_df = pd.concat([master_db, df_n], ignore_index=True)
                    conn.update(spreadsheet=st.secrets["gsheet_url"], worksheet="VENTAS", data=final_df)
                    st.success("¡Información Sincronizada!"); st.rerun()

    st.divider()
    if st.button("Cerrar Sesión"):
        st.session_state.auth = False
        st.rerun()

# --- DASHBOARD ---
df_master = load_all_data()

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

            # --- KPIs SUPERIORES ---
            k1, k2, k3 = st.columns(3)
            k1.metric("VENTAS TOTALES", f"$ {v_act:,.0f}")
            k2.metric("LICENCIAS NUEVAS", l_act)
            k3.metric("TICKET PROMEDIO", f"$ {t_act:,.0f}")

            # --- 1. EMBUDO (Contactos-Agendó-Asistió-Compró) ---
            st.divider()
            st.subheader("🌪️ Análisis de Embudo: Contactos - Agendó - Asistió - Compró")
            e1, e2 = st.columns([2,1])
            with e1:
                ef = {'co': df['CONTACTOS'].iloc[0], 'ag': df['AGENDO'].iloc[0], 'as': df['ASISTIO'].iloc[0], 'cp': df['COMPRO'].iloc[0]}
                fig_f = go.Figure(go.Funnel(y=["Contactos", "Agendó", "Asistió", "Compró"], x=[ef['co'], ef['ag'], ef['as'], ef['cp']], marker={"color": [AZUL_VINAPP, AZUL_CLARO, "#4b7aed", VERDE_EXITO]}))
                st.plotly_chart(fig_f, use_container_width=True)
            with e2:
                st.metric("TASA ASISTENCIA", f"{(ef['as']/ef['ag']*100):.1f}%" if ef['ag']>0 else "0%")
                st.metric("INASISTENCIA", f"{int(ef['ag']-ef['as'])} pros.", delta_color="inverse")
                st.metric("TASA DE CIERRE (COMPRÓ)", f"{(ef['cp']/ef['as']*100):.1f}%" if ef['as']>0 else "0%")

            # --- 2. CONTRIBUCIÓN POR FUENTE ---
            st.divider()
            st.subheader("📈 Contribución por Canal (Fuente)")
            f_df = df.groupby('FUENTE').agg(Ventas=('VALOR','count'), Aporte=('VALOR','sum')).reset_index().sort_values('Aporte', ascending=False)
            f_df['🌟'] = f_df['Aporte'].apply(lambda x: '🌟' if x == f_df['Aporte'].max() else '')
            f_c1, f_c2 = st.columns(2)
            with f_c1: st.plotly_chart(px.bar(f_df, x='FUENTE', y='Aporte', color_discrete_sequence=[AZUL_VINAPP]), use_container_width=True)
            with f_c2: st.table(f_df.assign(Aporte=f_df['Aporte'].map("$ {:,.0f}".format)))

            # --- 3. VENTAS POR PLAN (TABLA + GRÁFICA) ---
            st.divider()
            st.subheader("📦 Ventas por Plan")
            p_df = df.groupby('PLAN').agg(Cantidad=('VALOR','count'), Aporte=('VALOR','sum')).reset_index().sort_values('Aporte', ascending=False)
            p_df['🌟'] = p_df['Aporte'].apply(lambda x: '🌟' if x == p_df['Aporte'].max() else '')
            p_c1, p_c2 = st.columns(2)
            with p_c1: st.plotly_chart(px.bar(p_df, x='PLAN', y='Cantidad', text_auto=True, color_discrete_sequence=[AZUL_CLARO]), use_container_width=True)
            with p_c2: st.table(p_df.assign(Aporte=p_df['Aporte'].map("$ {:,.0f}".format)))

            # --- 4. VENTAS POR VENDEDOR ---
            st.divider()
            st.subheader("👤 Rendimiento por Vendedor")
            v_df = df.groupby('VENDEDOR').agg(Licencias=('VALOR','count'), Aporte=('VALOR','sum')).reset_index().sort_values('Aporte', ascending=False)
            v_df['🌟'] = v_df['Licencias'].apply(lambda x: '🌟' if x == v_df['Licencias'].max() else '')
            v_c1, v_c2 = st.columns(2)
            with v_c1: st.plotly_chart(px.bar(v_df, x='VENDEDOR', y='Aporte', text_auto='.2s', color_discrete_sequence=[AZUL_VINAPP]), use_container_width=True)
            with v_c2: st.table(v_df.assign(Aporte=v_df['Aporte'].map("$ {:,.0f}".format)))

            # --- 5. CIUDAD ---
            st.subheader("📍 Desempeño por Ciudad")
            ci_df = df.groupby('CIUDAD').agg(Ventas=('VALOR','count'), Aporte=('VALOR','sum')).reset_index().sort_values('Aporte', ascending=False)
            ci_df['🌟'] = ci_df['Aporte'].apply(lambda x: '🌟' if x == ci_df['Aporte'].max() else '')
            st.table(ci_df.assign(Aporte=ci_df['Aporte'].map("$ {:,.0f}".format)))

            # --- 6. RESUMEN CRECIMIENTO VS MES ANTERIOR ---
            if df_prev is not None:
                st.divider()
                st.subheader("📊 Resumen de Crecimiento vs Mes Anterior")
                cr1, cr2, cr3 = st.columns(3)
                v_ant, l_ant = df_prev['VALOR'].sum(), len(df_prev)
                t_ant = v_ant/l_ant if l_ant>0 else 0
                def r_card(tit, act, ant, iso=True):
                    d = ((act-ant)/ant*100) if ant>0 else 0
                    color = "delta-up" if d>=0 else "delta-down"
                    val = f"$ {act:,.0f}" if iso else f"{act}"
                    return f"<div class='card-resumen'><p>{tit}</p><h3>{val}</h3><p class='{color}'>{d:+.1f}%</p></div>"
                cr1.markdown(r_card("Crecimiento Ventas", v_act, v_ant), unsafe_allow_html=True)
                cr2.markdown(r_card("Licencias Nuevas", l_act, l_ant, False), unsafe_allow_html=True)
                cr3.markdown(r_card("Ticket Promedio", t_act, t_ant), unsafe_allow_html=True)

            # --- 7. EXPLORADOR (ZOOM) ---
            st.divider()
            st.subheader("🔍 Explorador Detallado de Clientes")
            cat_z = st.selectbox("Filtrar clientes por:", ["PLAN", "FUENTE", "VENDEDOR"], key=f"z_{i}")
            val_z = st.selectbox(f"Seleccionar {cat_z}:", df[cat_z].unique(), key=f"v_{i}")
            st.dataframe(df[df[cat_z] == val_z][['RESTAURANTE', 'VALOR', 'FECHA', 'CIUDAD']], use_container_width=True)

    # --- 8. EVOLUCIÓN HISTÓRICA FINAL ---
    st.divider()
    st.header("📈 Evolución Histórica: Ingresos vs Licencias")
    h_data = df_master.groupby('MES_ID').agg({'VALOR':'sum', 'RESTAURANTE':'count'}).reset_index()
    h_data['ORDEN'] = h_data['MES_ID'].apply(lambda x: datetime.strptime(x, '%B %Y'))
    h_data = h_data.sort_values('ORDEN')
    fig_h = go.Figure()
    fig_h.add_trace(go.Bar(x=h_data['MES_ID'], y=h_data['VALOR'], name="Ingresos", marker_color=AZUL_VINAPP))
    fig_h.add_trace(go.Scatter(x=h_data['MES_ID'], y=h_data['RESTAURANTE'], name="Licencias", yaxis="y2", line=dict(color=VERDE_EXITO, width=4)))
    fig_h.update_layout(
        yaxis=dict(title=dict(text="Ingresos ($)", font=dict(color=AZUL_VINAPP)), tickfont=dict(color=AZUL_VINAPP)),
        yaxis2=dict(title=dict(text="Licencias (und)", font=dict(color=VERDE_EXITO)), tickfont=dict(color=VERDE_EXITO), overlaying='y', side='right'),
        template="plotly_white", legend=dict(orientation="h", y=1.1)
    )
    st.plotly_chart(fig_h, use_container_width=True)

    # --- 9. CONSTRUCTOR DIDÁCTICO DE GRÁFICAS (A MEDIDA) ---
    st.divider()
    with st.expander("🎨 Constructor de Gráficas Manual (Revisión de Información)"):
        st.info("Usa este panel para crear cualquier gráfica que no esté arriba.")
        col_x = st.selectbox("1. Categoría (Eje X):", ["VENDEDOR", "PLAN", "FUENTE", "CIUDAD", "FRECUENCIA"])
        col_y = st.selectbox("2. Medida (Eje Y):", ["VALOR (Dinero)", "Licencias (Cantidad)"])
        tipo_g = st.radio("3. Estilo:", ["Barras", "Torta", "Línea"], horizontal=True)
        
        y_label = 'VALOR' if "VALOR" in col_y else 'RESTAURANTE'
        cust_df = df_master.groupby(col_x).agg({y_label: 'sum' if y_label=='VALOR' else 'count'}).reset_index()
        
        if tipo_g == "Barras": st.plotly_chart(px.bar(cust_df, x=col_x, y=y_label, color=col_x, text_auto='.2s'))
        elif tipo_g == "Torta": st.plotly_chart(px.pie(cust_df, names=col_x, values=y_label, hole=0.4))
        else: st.plotly_chart(px.line(cust_df, x=col_x, y=y_label, markers=True))

else:
    st.warning("👋 i love you)
