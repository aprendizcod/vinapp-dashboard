import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sqlite3
import json

# 1. CONFIGURACIÓN Y ESTILO ELITE
st.set_page_config(page_title="VinApp Intelligence Pro", layout="wide")

AZUL_VINAPP = "#0033a0"
FONDO = "#f0f4fb"

# Estilos CSS
st.markdown(f"""
    <style>
    .main {{ background-color: {FONDO}; font-family: 'Inter', sans-serif; }}
    .stMetric {{ background-color: white; padding: 24px; border-radius: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eef2ff; }}
    .ganador-text {{ color: #f59e0b; font-weight: bold; }}
    </style>
    """, unsafe_allow_html=True)

# 2. GESTIÓN DE BASE DE DATOS (LA MEMORIA)
def init_db():
    conn = sqlite3.connect('vinapp_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS ventas 
                 (mes_id TEXT, data_json TEXT, mapa_json TEXT, eficiencias TEXT)''')
    conn.commit()
    return conn

def save_to_db(mes_id, df, mapa, eficiencias):
    conn = init_db()
    c = conn.cursor()
    # Guardamos como JSON para persistencia sencilla
    data_json = df.to_json()
    mapa_json = json.dumps(mapa)
    eficiencias_json = json.dumps(eficiencias)
    c.execute("INSERT OR REPLACE INTO ventas VALUES (?, ?, ?, ?)", 
              (mes_id, data_json, mapa_json, eficiencias_json))
    conn.commit()
    conn.close()

def load_all_from_db():
    conn = init_db()
    df_list = pd.read_sql_query("SELECT * FROM ventas", conn)
    conn.close()
    return df_list

# 3. PROCESAMIENTO DE ARCHIVOS
def clean_currency(value):
    if pd.isna(value): return 0.0
    clean = str(value).replace('$', '').replace('.', '').replace(',', '.').strip()
    try: return float(clean)
    except: return 0.0

def process_file(file):
    tablas = pd.read_html(file)
    df = max(tablas, key=len)
    if 'VALOR' in df.iloc[0].values or 'PLAN' in df.iloc[0].values:
        df.columns = df.iloc[0]; df = df[1:].reset_index(drop=True)
    
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

# --- APP PRINCIPAL ---
st.title("🏆 VinApp Business Intelligence")

# Cargar datos históricos de la base de datos
datos_historicos = load_all_from_db()
meses_disponibles = {}

if not datos_historicos.empty:
    for _, row in datos_historicos.iterrows():
        df_mes = pd.read_json(row['data_json'])
        mapa_mes = json.loads(row['mapa_json'])
        eficiencias_mes = json.loads(row['eficiencias'])
        # Asegurar formato de fecha al recargar
        df_mes[mapa_mes['f']] = pd.to_datetime(df_mes[mapa_mes['f']], unit='ms')
        meses_disponibles[row['mes_id']] = {"df": df_mes, "mapa": mapa_mes, "eficiencia": eficiencias_mes}

# SIDEBAR PARA ADMINISTRADOR (TÚ)
with st.sidebar:
    st.header("⚙️ Panel de Control")
    password = st.text_input("Contraseña Administrador", type="password")
    
    if password == "vinapp2026": # Puedes cambiar esta clave
        st.subheader("Cargar Nuevo Mes")
        nuevo_file = st.file_uploader("Subir reporte HTML", type=["html"])
        if nuevo_file:
            df_new, mapa_new = process_file(nuevo_file)
            mes_nombre = df_new[mapa_new['f']].min().strftime('%B %Y')
            
            # Inputs del embudo
            st.info(f"Configurando {mes_nombre}")
            l = st.number_input("Contactos", value=200)
            d = st.number_input("Demos", value=50)
            a = st.number_input("Asistió", value=20)
            c = st.number_input("Compró", value=5)
            
            if st.button("Guardar Mes en Memoria"):
                efs = {'leads': l, 'demos': d, 'asist': a, 'comp': c}
                save_to_db(mes_nombre, df_new, mapa_new, efs)
                st.success("¡Datos guardados! Refresca la página.")

# --- VISUALIZACIÓN ---
if meses_disponibles:
    fechas_keys = sorted(meses_disponibles.keys(), key=lambda x: datetime.strptime(x, '%B %Y'))
    tabs = st.tabs(fechas_keys)

    for idx, nombre_mes in enumerate(fechas_keys):
        with tabs[idx]:
            # Lógica de Dashboard (igual a la anterior, usando meses_disponibles[nombre_mes])
            data = meses_disponibles[nombre_mes]
            df = data["df"]
            c = data["mapa"]
            ef = data["eficiencia"]
            
            # --- Aquí va todo el bloque de KPIs y Gráficas que ya teníamos ---
            st.header(f"Reporte de {nombre_mes}")
            
            # Ejemplo rápido de KPI
            v_total = df[c['v']].sum()
            st.metric("VENTAS TOTALES", f"$ {v_total:,.0f}")
            
            # (Resto de gráficas iguales al código anterior...)
            st.info("Utiliza el panel lateral para cargar nuevos meses.")
            st.dataframe(df) # Tabla de ejemplo

else:
    st.warning("Aún no hay datos cargados. El administrador debe subir los archivos en el panel lateral.")