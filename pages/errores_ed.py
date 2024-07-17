import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from google.cloud import bigquery
from datetime import datetime, timedelta
import plotly.express as px
from plotly.subplots import make_subplots
import base64
from google.cloud import bigquery
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
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

# Conexión onexión a BigQuery
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=credentials)
fecha_actual = datetime.now().strftime('%Y-%m-%d')

ed_proyectos = """
SELECT R.alias AS proyecto
FROM parkimovil-app.geosek_raspis.log LS
JOIN parkimovil-app.geosek_raspis.raspis R
    ON LS.QR = R.qr
GROUP BY R.alias;
"""

errores_ed = """
SELECT LS.function_ AS tipo_error
FROM parkimovil-app.geosek_raspis.log LS
JOIN parkimovil-app.geosek_raspis.raspis R
    ON LS.QR = R.qr
GROUP BY LS.function_
"""

proyectos_ed = client.query(ed_proyectos).to_dataframe()

errores_ed = client.query(errores_ed).to_dataframe()

list_proyectos_ed = proyectos_ed['proyecto'].unique().tolist()
list_errores_ed = errores_ed['tipo_error'].unique().tolist()
list_errores_ed = list(set(error.strip() for error in list_errores_ed))

@st.cache_data
# Función para obtener datos de errores por proyecto
def proyectos_errores(proyecto, error, intervalo_tiempo):
    if intervalo_tiempo == 'Mensual':
        date_format = "%Y-%m"
        group_by_clause = "FORMAT_TIMESTAMP('%Y-%m', TIMESTAMP_ADD(date, INTERVAL -6 HOUR))"
    else:  # Diario
        date_format = "%Y-%m-%d"
        group_by_clause = "FORMAT_TIMESTAMP('%Y-%m-%d', TIMESTAMP_ADD(date, INTERVAL -6 HOUR))"

    count_error = f"""
        SELECT {group_by_clause} AS fecha, COUNT(function_) AS errores
        FROM parkimovil-app.geosek_raspis.log LS
        JOIN parkimovil-app.geosek_raspis.raspis R
            ON LS.QR = R.qr
        WHERE EXTRACT(DATE FROM date) >= '2024-01-01' 
            AND TRIM(R.alias) LIKE '{proyecto}' 
            AND TRIM(LS.function_) LIKE '{error}'
        GROUP BY {group_by_clause}
        ORDER BY fecha ASC;
    """
    df_proyectos_errores_ed = client.query(count_error).to_dataframe()
    return df_proyectos_errores_ed

@st.cache_data
def tipo_errores_ed(proyecto):
    errores_proyectos_ed = f"""
    SELECT LS.function_ AS tipo, COUNT(function_) AS cantidad
    FROM parkimovil-app.geosek_raspis.log LS
    JOIN parkimovil-app.geosek_raspis.raspis R
        ON LS.QR = R.qr
    WHERE TRIM(R.alias) LIKE '{proyecto}' AND EXTRACT(DATE FROM date) = CURRENT_DATE('America/Mexico_City')
    GROUP BY LS.function_
    """

    df_tipo_errores_ed = client.query(errores_proyectos_ed).to_dataframe()
    return df_tipo_errores_ed

@st.cache_data
def errores_hora(proyecto):
    errores_horas = f"""
    SELECT
    EXTRACT(DATE FROM LS.date) AS fecha,
    EXTRACT(HOUR FROM LS.date) AS hora,
    COUNT(function_) AS lecturas,
    SUM(CASE WHEN LS.function_ = 'open' THEN 1 ELSE 0 END) AS lecturas_correctas,
    SUM(CASE WHEN LS.function_ != 'open' THEN 1 ELSE 0 END) AS lecturas_error,
    ((SUM(CASE WHEN LS.function_ != 'open' THEN 1 ELSE 0 END) * 100) / COUNT(function_)) AS porcentaje_error,
    SUM(CASE WHEN LS.function_ = 'open_error_500' THEN 1 ELSE 0 END) AS desconexion,
    SUM(CASE WHEN LS.function_ = 'open_error_501' THEN 1 ELSE 0 END) AS errores_de_presencia,
    COUNT(CASE WHEN LS.function_ NOT IN ('open_error_500', 'open_error_501', 'open') THEN 1 ELSE NULL END) AS otros_errores
    FROM
    parkimovil-app.geosek_raspis.log LS
    JOIN
    parkimovil-app.geosek_raspis.raspis R
    ON LS.QR = R.qr
    WHERE
        TRIM(R.alias) LIKE '{proyecto}'
        AND EXTRACT(DATE FROM LS.date) = CURRENT_DATE('America/Mexico_City')
    GROUP BY
        fecha, hora
    ORDER BY
        fecha, hora;
    """

    df_errores_hora = client.query(errores_horas).to_dataframe()
    return df_errores_hora

st.title('Visualizador de Errores')
proyecto_seleccionada = st.selectbox('Selecciona una ciudad:', list_proyectos_ed)
error_seleccionado = st.selectbox('Selecciona un tipo de error:', list_errores_ed)
intervalo_tiempo = st.radio('Selecciona el intervalo de tiempo:', ['Diario', 'Mensual'])

df_error_proyecto = proyectos_errores(proyecto_seleccionada, error_seleccionado, intervalo_tiempo)

df_tipo_errores_proyecto = tipo_errores_ed(proyecto_seleccionada)

df_errores_hora = errores_hora(proyecto_seleccionada)

# Crear el gráfico
custom_colors = ['#050039', '#FF5A00', '#4E71B7', '#F98200', '#EFA21B']

error_title = f'{proyecto_seleccionada.title()}'
fig = px.bar(df_error_proyecto, x='fecha', y='errores', title=error_title)

fig.add_trace(
    go.Scatter(
        x=df_error_proyecto['fecha'],
        y=df_error_proyecto['errores'],
        mode='lines+markers',
        name='Lectura',
        line=dict(color='#FF5A00')
    )
)

# Actualizar el eje x con el selector de rango de fechas
if intervalo_tiempo == 'Diario':
    date_format = "%d/%m/%Y"
else:  # Mensual
    date_format = "%B, %Y"

fig.update_xaxes(
    rangeslider_visible=True,
    tickformat=date_format
)

tipo_fig = go.Figure(data=[go.Pie(labels=df_tipo_errores_proyecto['tipo'],
                                  values=df_tipo_errores_proyecto['cantidad'],
                                  marker=dict(colors=custom_colors))])

tipo_fig.update_traces(hole=.4, hoverinfo="label+percent")
tipo_fig.update_layout(title_text=f'Operaciones en {fecha_actual}')

tabla_datos = go.Table(header=dict(values=['Tipo Lectura', 'Cantidad']),
                       cells=dict(values=[df_tipo_errores_proyecto['tipo'],
                                          df_tipo_errores_proyecto['cantidad']]))

fig_tabla = make_subplots(rows=1, cols=2, specs=[[{'type':'domain'}, {'type':'table'}]])

fig_tabla.add_trace(tipo_fig.data[0], row=1, col=1)
fig_tabla.add_trace(tabla_datos, row=1, col=2)

fig_tabla.update_layout(title_text=f'Operaciones - {fecha_actual}', height=600)

# Mostrar el gráfico
st.plotly_chart(fig, use_container_width=True)
st.plotly_chart(fig_tabla, use_container_width=True)

st.write(df_errores_hora)

@st.cache_data
def get_binary_file_downloader_html(bin_file, file_label='File'):
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{bin_file}">{file_label}</a>'
    return href

if st.button('Descargar tabla como Excel'):
        with pd.ExcelWriter('errores_hora.xlsx', engine='xlsxwriter') as writer:
            df_errores_hora.to_excel(writer, index=False)
        st.success('Tabla descargada exitosamente!')
        st.markdown(get_binary_file_downloader_html('errores_hora.xlsx', 'Descargar tabla como Excel'), unsafe_allow_html=True)

@st.cache_data
def errores_diario(proyecto):
    query_errores_diario = f"""
    SELECT
    EXTRACT(DATE FROM LS.date) AS fecha,
    COUNT(function_) AS lecturas,
    SUM(CASE WHEN LS.function_ = 'open' THEN 1 ELSE 0 END) AS lecturas_correctas,
    SUM(CASE WHEN LS.function_ != 'open' THEN 1 ELSE 0 END) AS lecturas_error,
    ((SUM(CASE WHEN LS.function_ != 'open' THEN 1 ELSE 0 END) * 100) / COUNT(function_)) AS porcentaje_error,
    SUM(CASE WHEN LS.function_ = 'open_error_500' THEN 1 ELSE 0 END) AS desconexion,
    SUM(CASE WHEN LS.function_ = 'open_error_501' THEN 1 ELSE 0 END) AS errores_de_presencia,
    COUNT(CASE WHEN LS.function_ NOT IN ('open_error_500', 'open_error_501', 'open') THEN 1 ELSE NULL END) AS otros_errores
    FROM
    parkimovil-app.geosek_raspis.log LS
    JOIN
    parkimovil-app.geosek_raspis.raspis R
    ON LS.QR = R.qr
    WHERE
        TRIM(R.alias) LIKE '{proyecto}'
        AND EXTRACT(DATE FROM LS.date) = CURRENT_DATE('America/Mexico_City')
    GROUP BY
        fecha
    ORDER BY
        fecha;
    """

    df_errores_diario = client.query(query_errores_diario).to_dataframe()
    return df_errores_diario

df_errores_diario = errores_diario(proyecto_seleccionada)

st.write(df_errores_diario)