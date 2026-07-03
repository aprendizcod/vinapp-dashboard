import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sqlite3
import json
import io

# 1. CONFIGURACIÓN VISUAL (ESTILO ELITE VINAPP)
st.set_page_config(page_title="VinApp Intelligence Pro", layout="wide")

AZUL_VINAPP = "#0033a0"
AZUL_CLARO = "#1e4fd1"
FONDO = "#f8fafc"
VERDE_EXITO = "#10b981"
ROJO_ALERTA = "#ef4444"

st.markdown(f"""
    <style>
    .main {{ background-color: {FONDO}; font-family: 'Inter', sans-serif; }}
    .stMetric {{ background-color: white; padding: 24px; border-radius: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 5px solid {AZUL_VINAPP}; }}
    .ganador {{ color: #f59e0b; font-weight: bold; font-size: 1.1rem; }}
    .card-resumen {{
        background-color: white; padding: 20px; border-radius: 15px; border: 1px solid #e2e8f0; 
        text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }}
    .delta-up {{ color: {VERDE_EXITO}; font-weight: bold; font-size: 0.9rem; }}
    .delta-down {{ color: {ROJO_ALERTA}; font-weight: bold; font-size: 0.9rem; }}
    </style>
    """, unsafe_allow_html=True)

# 2. GESTIÓN DE BASE DE DATOS
def init_db():
    conn = sqlite3.connect('vinapp_corporate_db.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS ventas 
                 (mes_id TEXT PRIMARY KEY, data_json TEXT, mapa_json TEXT, eficiencias TEXT)''')
    conn.commit()
    return conn

def save_to_db(mes_id, df, mapa, eficiencias):
    conn = init_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO ventas VALUES (?, ?, ?, ?)", 
              (mes_id, df.to_json(), json.dumps(mapa), json.dumps(eficiencias)))
    conn.commit()
    conn.close()

def load_all_from_db():
    conn = init_db()
    try: return pd.read_sql_query("SELECT * FROM ventas", conn)
    except: return pd.DataFrame()
    finally: conn.close()

# 3. PROCESAMIENTO DE DATOS (ESPECIAL PARA ABRIL Y ARCHIVOS DIFÍCILES)
def clean_currency(value):
    if pd.isna(value): return 0.0
    clean = str(value).replace('$', '').replace('.', '').replace(',', '.').strip()
    try: return float(clean)
    except: return 0.0

def process_file(file):
    tablas = pd.read_html(file)
    df = max(tablas, key=len)
    
    # Escaneo para encontrar encabezados reales
    for i in range(min(15, len(df))):
        fila = [str(x).upper() for x in df.iloc[i].values]
        if 'VALOR' in fila or 'PLAN' in fila or 'FECHA' in fila:
            df.columns = df.iloc[i]
            df = df[i+1:].reset_index(drop=True)
            break
    
    cols = [str(c).strip().upper() for c in df.columns]
    final_cols = []
    counts = {}
    for col in cols:
        if col in counts:
            counts[col] += 1
            final_cols.append(f"{col}_{counts[col]}")
        else:
            counts[col] = 0; final_cols.append(col)
    df.columns = final_cols

    c = {
        'v': next((col for col in df.columns if 'VALOR' in col), None),
        'f': next((col for col in df.columns if 'FECHA' in col), None),
        'vend': next((col for col in df.columns if 'VENDEDOR' in col and 'UPGRADE' not in col), None),
        'plan': next((col for col in df.columns if 'PLAN' in col and 'UPGRADE' not in col), None),
        'fuente': next((col for col in df.columns if 'FUENTE' in col), None),
        'ciudad': next((col for col in df.columns if 'CIUDAD' in col), None),
        'freq': next((col for col in df.columns if any(x in col for x in ['FRECUENCIA', 'PAGO', 'RECURRENCIA'])), None),
        'rest': next((col for col in df.columns if any(x in col for x in ['RESTAURANTE', 'CLIENTE', 'NOMBRE'])), None)
    }

    df[c['v']] = df[c['v']].apply(clean_currency)
    df[c['f']] = pd.to_datetime(df[c['f']], dayfirst=True, errors='coerce')
    df = df.dropna(subset=[c['f']])
    df = df[df[c['v']] > 0]
    return df, c

# --- CARGA DE DATOS DESDE LA MEMORIA (CORRECCIÓN CLOUD) ---
historico = load_all_from_db()
meses_db = {}

if not historico.empty:
    for _, row in historico.iterrows():
        # USAMOS io.StringIO para que Streamlit Cloud no busque un archivo inexistente
        df_mes = pd.read_json(io.StringIO(row['data_json']))
        mapa_mes = json.loads(row['mapa_json'])
        ef_mes = json.loads(row['eficiencias'])
        df_mes[mapa_mes['f']] = pd.to_datetime(df_mes[mapa_mes['f']], unit='ms')
        meses_db[row['mes_id']] = {"df": df_mes, "mapa": mapa_mes, "ef": ef_mes}

# --- SIDEBAR ADMIN ---
with st.sidebar:
    st.title("VinApp Admin")
    pwd = st.text_input("Contraseña Administrador", type="password")
    if pwd == "vinapp2026":
        st.subheader("Subir Reporte")
        f_in = st.file_uploader("HTML del Mes", type="html")
        if f_in:
            df_n, mapa_n = process_file(f_in)
            if not df_n.empty:
                nombre_detectado = df_n[mapa_n['f']].min().strftime('%B %Y')
                st.success(f"Detectado: {nombre_detectado}")
                
                # Datos del embudo con llaves únicas para evitar bloqueos
                l = st.number_input("Leads", value=200, key="leads_new")
                d = st.number_input("Demos", value=50, key="demos_new")
                a = st.number_input("Asistió", value=20, key="asist_new")
                c_v = st.number_input("Compró", value=len(df_n), key="comp_new")
                
                if st.button("Guardar en Nube"):
                    save_to_db(nombre_detectado, df_n, mapa_n, {'leads':l, 'demos':d, 'asist':a, 'comp':c_v})
                    st.rerun()

# --- DASHBOARD ---
if meses_db:
    ordenados = sorted(meses_db.keys(), key=lambda x: datetime.strptime(x, '%B %Y'))
    tabs = st.tabs([f"📅 {m}" for m in ordenados])

    for i, mes_key in enumerate(ordenados):
        with tabs[i]:
            data = meses_db[mes_key]; df = data["df"]; c = data["mapa"]; ef = data["ef"]
            prev = meses_db[ordenados[i-1]] if i > 0 else None
            ventas_act = df[c['v']].sum(); lic_act = len(df); t_prom_act = ventas_act/lic_act

            # --- KPIs SUPERIORES ---
            k1, k2, k3 = st.columns(3)
            if prev:
                v_ant = prev["df"][prev["mapa"]['v']].sum()
                k1.metric("VENTAS TOTALES", f"$ {ventas_act:,.0f}", f"{((ventas_act-v_ant)/v_ant)*100:+.1f}%")
            else: k1.metric("VENTAS TOTALES", f"$ {ventas_act:,.0f}")
            k2.metric("LICENCIAS NUEVAS", lic_act)
            k3.metric("TICKET PROMEDIO", f"$ {t_prom_act:,.0f}")

            # --- EMBUDO DINÁMICO ---
            st.divider()
            f1, f2 = st.columns([2, 1])
            with f1:
                st.subheader("🌪️ Embudo de Ventas")
                fig_f = go.Figure(go.Funnel(
                    y = ["Leads", "Demos", "Asistió", "Compró"],
                    x = [ef['leads'], ef['demos'], ef['asist'], ef['comp']],
                    marker = {"color": [AZUL_VINAPP, AZUL_CLARO, "#4b7aed", VERDE_EXITO]}
                ))
                st.plotly_chart(fig_f, use_container_width=True)
            with f2:
                st.subheader("Eficiencia")
                t_asist = (ef['asist']/ef['demos']*100) if ef['demos']>0 else 0
                t_conv = (ef['comp']/ef['asist']*100) if ef['asist']>0 else 0
                st.metric("TASA ASISTENCIA", f"{t_asist:.1f}%")
                st.metric("INASISTENCIA", f"{ef['demos']-ef['asist']} pros.", f"{(1-t_asist/100)*100:.1f}%", delta_color="inverse")
                st.metric("TASA CIERRE", f"{t_conv:.1f}%")

            # --- CONTRIBUCIÓN FUENTE ---
            st.divider()
            st.subheader("📈 Contribución por Canal (Fuente)")
            f_df = df.groupby(c['fuente']).agg(Transacciones=(c['v'], 'count'), Ingresos=(c['v'], 'sum')).reset_index().sort_values('Ingresos', ascending=False)
            f_df['% Total'] = (f_df['Ingresos']/ventas_act*100).map("{:.1f}%".format)
            fa, fb = st.columns(2)
            with fa: st.table(f_df.assign(Ingresos=f_df['Ingresos'].map("$ {:,.0f}".format)))
            with fb: st.plotly_chart(px.bar(f_df, x=c['fuente'], y='Ingresos', color_discrete_sequence=[AZUL_VINAPP]), use_container_width=True)

            # --- PLANES (TABLA + ESTRELLA) ---
            st.divider()
            st.subheader("📦 Ventas por Plan")
            p1, p2 = st.columns(2)
            p_df = df.groupby(c['plan']).agg(Cantidad=(c['v'], 'count'), Aporte=(c['v'], 'sum')).reset_index().sort_values('Aporte', ascending=False)
            with p1: st.plotly_chart(px.bar(p_df, x=c['plan'], y='Cantidad', text_auto=True, color_discrete_sequence=[AZUL_CLARO]), use_container_width=True)
            with p2:
                p_df['🌟'] = p_df['Aporte'].apply(lambda x: '🌟' if x == p_df['Aporte'].max() else '')
                st.table(p_df.assign(Aporte=p_df['Aporte'].map("$ {:,.0f}".format)))

            # --- VENDEDORES ---
            st.divider()
            st.subheader("👤 Rendimiento Vendedores")
            v1, v2 = st.columns(2)
            v_df = df.groupby(c['vend']).agg(Licencias=(c['v'], 'count'), Aporte=(c['v'], 'sum')).reset_index().sort_values('Aporte', ascending=False)
            with v1: st.plotly_chart(px.bar(v_df, x=c['vend'], y='Aporte', text_auto='.2s', color_discrete_sequence=[AZUL_VINAPP]), use_container_width=True)
            with v2:
                v_df['🌟'] = v_df['Aporte'].apply(lambda x: '🌟' if x == v_df['Aporte'].max() else '')
                st.table(v_df.assign(Aporte=v_df['Aporte'].map("$ {:,.0f}".format)))

            # --- CIUDAD Y RECURRENCIA ---
            st.divider()
            cc1, cc2 = st.columns(2)
            with cc1:
                st.markdown("### 📍 Ingresos por Ciudad")
                city_df = df.groupby(c['ciudad']).agg(Ventas=(c['v'], 'count'), Aporte=(c['v'], 'sum')).reset_index().sort_values('Aporte', ascending=False)
                city_df['🌟'] = city_df['Aporte'].apply(lambda x: '🌟' if x == city_df['Aporte'].max() else '')
                st.table(city_df.assign(Aporte=city_df['Aporte'].map("$ {:,.0f}".format)))
            with cc2:
                st.markdown("### 💰 Ingresos por Frecuencia")
                freq_df = df.groupby(c['freq'])[c['v']].sum().reset_index().sort_values(c['v'], ascending=False)
                st.plotly_chart(px.pie(freq_df, names=c['freq'], values=c['v'], hole=0.4, color_discrete_sequence=px.colors.sequential.Blues_r), use_container_width=True)

            # --- RESUMEN DE CRECIMIENTO VS ANTERIOR ---
            st.divider()
            st.subheader("📊 Resumen de Crecimiento vs Mes Anterior")
            if prev:
                cr1, cr2, cr3 = st.columns(3)
                v_ant = prev["df"][prev["mapa"]['v']].sum(); l_ant = len(prev["df"]); t_ant = v_ant/l_ant
                def render_res(tit, act, ant, iso=True):
                    d = ((act-ant)/ant)*100
                    cl = "delta-up" if d>=0 else "delta-down"
                    val = f"$ {act:,.0f}" if iso else f"{act}"
                    return f"<div class='card-resumen'><p>{tit}</p><h3>{val}</h3><p class='{cl}'>{d:+.1f}%</p></div>"
                cr1.markdown(render_res("Ventas", ventas_act, v_ant), unsafe_allow_html=True)
                cr2.markdown(render_res("Licencias", lic_act, l_ant, False), unsafe_allow_html=True)
                cr3.markdown(render_res("Ticket Prom.", t_prom_act, t_ant), unsafe_allow_html=True)
            else: st.info("Sin mes anterior para comparar.")

            # --- EXPLORADOR ---
            st.divider()
            st.subheader("🔍 Explorador Detallado")
            cat = st.selectbox("Filtrar por:", ["Plan", "Fuente", "Vendedor"], key=f"cat_{i}")
            mapa_f = {"Plan": c['plan'], "Fuente": c['fuente'], "Vendedor": c['vend']}
            elec = st.selectbox(f"Seleccionar {cat}:", df[mapa_f[cat]].unique(), key=f"elec_{i}")
            st.dataframe(df[df[mapa_f[cat]] == elec][[c['rest'], c['v'], c['f'], c['ciudad']]], use_container_width=True)

    # --- EVOLUCIÓN HISTÓRICA FINAL ---
    st.divider()
    st.header("📈 Evolución Histórica: Ingresos vs Licencias")
    h_data = []
    for k in ordenados:
        v_m = meses_db[k]["df"][meses_db[k]["mapa"]['v']].sum()
        l_m = len(meses_db[k]["df"])
        h_data.append({"Mes": k, "Ingresos": v_m, "Licencias": l_m})
    df_h = pd.DataFrame(h_data)
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Bar(x=df_h['Mes'], y=df_h['Ingresos'], name="Ingresos ($)", marker_color=AZUL_VINAPP))
    fig_hist.add_trace(go.Scatter(x=df_h['Mes'], y=df_h['Licencias'], name="Licencias (und)", yaxis="y2", line=dict(color=VERDE_EXITO, width=4)))
    fig_hist.update_layout(
        yaxis=dict(title="Ingresos ($)", titlefont=dict(color=AZUL_VINAPP), tickfont=dict(color=AZUL_VINAPP)),
        yaxis2=dict(title="Licencias (und)", titlefont=dict(color=VERDE_EXITO), tickfont=dict(color=VERDE_EXITO), overlaying='y', side='right'),
        template="plotly_white", legend=dict(orientation="h", y=1.1)
    )
    st.plotly_chart(fig_hist, use_container_width=True)

else:
    st.warning("Aún no hay datos cargados. El administrador debe subir los archivos en el panel lateral.")
