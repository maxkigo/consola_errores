import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from google.cloud import bigquery
from datetime import datetime
import plotly.express as px
from plotly.subplots import make_subplots
import requests
import json
from google.oauth2 import service_account

st.set_page_config(layout="wide")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.write()

with col2:
    st.image('https://main.d1jmfkauesmhyk.amplifyapp.com/img/logos/logos.png')

with col3:
    st.title('Kigo Analítica')

with col4:
    st.write()

# Create API client.
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=credentials)

# Configuración del bot de Telegram
TELEGRAM_BOT_TOKEN = st.secrets["telegram"]["BOT_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["telegram"]["CHAT_ID"]

# Función para enviar mensaje a Telegram
def enviar_alerta_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto
    })
    headers = {
        'Content-Type': 'application/json'
    }
    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        print("Mensaje de alerta enviado a Telegram.")
    else:
        print(f"Error al enviar el mensaje a Telegram: {response.status_code} - {response.text}")

@st.cache_data(ttl=3600)  # Cache data for one hour
def errores_diario_todos():
    query_errores_diario = """
    SELECT
        R.alias AS proyecto,
        EXTRACT(DATE FROM LS.date) AS fecha,
        COUNT(function_) AS lecturas,
        SUM(CASE WHEN LS.function_ = 'open' THEN 1 ELSE 0 END) AS lecturas_correctas,
        SUM(CASE WHEN LS.function_ != 'open' THEN 1 ELSE 0 END) AS lecturas_error,
        ((SUM(CASE WHEN LS.function_ != 'open' THEN 1 ELSE 0 END) * 100) / COUNT(function_)) AS porcentaje_error
    FROM
        parkimovil-app.geosek_raspis.log LS
    JOIN
        parkimovil-app.geosek_raspis.raspis R
    ON
        LS.QR = R.qr
    WHERE
        EXTRACT(DATE FROM LS.date) = CURRENT_DATE('America/Mexico_City')
    GROUP BY
        R.alias, fecha
    ORDER BY
        fecha, lecturas DESC;
    """
    df_errores_diario_todos = client.query(query_errores_diario).to_dataframe()
    return df_errores_diario_todos

# Singleton to track if an alert was sent in the current hour
def get_alert_sent_status():
    if 'alert_status' not in st.session_state:
        st.session_state.alert_status = {'sent': False, 'timestamp': None}
    return st.session_state.alert_status

alert_status = get_alert_sent_status()
current_time = datetime.now()

df_errores_diario_todos = errores_diario_todos()

# Verificar si hay algún proyecto con más del 5% de errores
proyectos_con_errores_altos = df_errores_diario_todos[df_errores_diario_todos['porcentaje_error'] > 5]

# Check if an alert needs to be sent
if not proyectos_con_errores_altos.empty:
    if (alert_status['timestamp'] is None or
            (current_time - alert_status['timestamp']).total_seconds() >= 3600):

        # Preparar el mensaje de alerta
        mensaje_alerta = "Se han detectado los siguientes proyectos con más del 5% de errores:\n\n"
        for idx, row in proyectos_con_errores_altos.iterrows():
            mensaje_alerta += f"Proyecto: {row['proyecto']}, Porcentaje de Error: {row['porcentaje_error']}%\n"

        # Enviar el mensaje de alerta a Telegram
        enviar_alerta_telegram(mensaje_alerta)

        # Update alert status
        alert_status['sent'] = True
        alert_status['timestamp'] = current_time

# Mostrar la tabla en Streamlit
st.write(df_errores_diario_todos)
