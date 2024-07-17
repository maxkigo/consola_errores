import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from google.cloud import bigquery
from datetime import datetime, timedelta
import plotly.express as px
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from google.oauth2 import service_account

st.set_page_config(
    page_title="Kigo - Monitoreo",
    page_icon="👋",
    layout="wide"
)

st.sidebar.success("Monitoreo de Errores")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.write()

with col2:
    st.image('https://main.d1jmfkauesmhyk.amplifyapp.com/img/logos/logos.png')

with col3:
    st.title('Kigo Analítica')

with col4:
    st.write()

credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=credentials)

servicio_seleccionado = st.selectbox('Seleccione Servicio:', ('CONTROL DE ACCESOS', 'ESTACIONAMIENTO DIGITAL'))

def servicio_consola(servicio):
    if servicio == 'CONTROL DE ACCESOS':
        lecturas_proyectos = "FROM parkimovil-app.geosek_raspis.log_sek LS"
    else:
        lecturas_proyectos = "FROM parkimovil-app.geosek_raspis.log LS"

    servicio_consola = f"""
SELECT proyecto, tipo_lectura, SUM(lectura) AS cantidad 
FROM (
    SELECT TRIM(R.alias) AS proyecto, TRIM(LS.function_) AS tipo_lectura, COUNT(*) AS lectura
    {lecturas_proyectos}
    JOIN parkimovil-app.geosek_raspis.raspis R ON LS.QR = R.qr
    WHERE EXTRACT(DATE FROM date) = CURRENT_DATE('America/Mexico_City')
    GROUP BY TRIM(R.alias), TRIM(LS.function_)
) AS combined_results
GROUP BY proyecto, tipo_lectura
ORDER BY cantidad DESC;
"""
    df_servicio_consola = client.query(servicio_consola).to_dataframe()
    return df_servicio_consola

df_servicio_consola = servicio_consola(servicio_seleccionado)

types_function = df_servicio_consola['tipo_lectura'].unique().tolist()
types_function = list(set(lectura.strip() for lectura in types_function))

pivot_table = pd.pivot_table(df_servicio_consola, values='cantidad', index='proyecto', columns='tipo_lectura', fill_value=0).reset_index()

def top_n_proyectos_con_lectura_open(df, n):
    # Filtrar solo las columnas relevantes que contengan "open"
    open_columns = [col for col in df.columns if 'open' in col]

    # Calcular la suma de tipos de lectura "open" para cada proyecto
    df['total_open_lectura'] = df[open_columns].sum(axis=1)

    # Ordenar los proyectos por la suma de tipos de lectura "open" en orden descendente
    df_sorted = df.sort_values(by='total_open_lectura', ascending=False)

    # Seleccionar los primeros N proyectos de la lista ordenada
    top_n_proyectos = df_sorted.head(n)

    return top_n_proyectos

# Ejemplo de uso: Mostrar los top 5 proyectos con más tipos de lectura "open"
n_top = 20
top_proyectos_open = top_n_proyectos_con_lectura_open(pivot_table, n_top)

def plot_heatmap(ax, project_names, data):
    # Define colors for heatmap using Viridis
    cmap = plt.get_cmap('viridis')

    # Extract project names and type of readings
    projects = project_names
    types_of_readings = data.columns

    # Transpose the data to match the new axis orientation
    data_t = data.T

    # Iterate over projects
    for i, type_of_reading in enumerate(types_of_readings):
        # Get data for the current type of reading
        type_data = data_t.iloc[i].values

        # Get values for the x and y axes
        x = np.arange(len(projects))
        y = [i] * len(projects)

        # Normalize data for coloring
        norm = plt.Normalize(type_data.min(), type_data.max())
        colors = cmap(norm(type_data))

        # Plot the markers for the selected type of reading
        ax.scatter(x, y, color=colors, s=120, alpha=0.7)

    # Remove all spines
    ax.set_frame_on(False)

    # Set grid lines with some transparency
    ax.grid(alpha=0.4)

    # Make sure grid lines are behind other objects
    ax.set_axisbelow(True)

    # Set position for x ticks
    ax.set_xticks(np.arange(len(projects)))

    # Set labels for the x ticks (the names of the projects)
    ax.set_xticklabels(projects, rotation=90, ha='right')

    # Set position for y ticks
    ax.set_yticks(np.arange(len(types_of_readings)))

    # Set labels for the y ticks (the types of readings)
    ax.set_yticklabels(types_of_readings)

    # Set label for horizontal axis.
    ax.set_xlabel("Proyecto", loc="right")

    # Set label for vertical axis.
    ax.set_ylabel("Tipo de Lectura")

    return ax

st.write("Monitoreo de Lecturas de Top", n_top, "proyectos:")

fig, ax = plt.subplots(figsize=(12, 10))
project_names = top_proyectos_open['proyecto']
data = top_proyectos_open.drop(columns='proyecto')  # Exclude the column 'proyecto'
plot_heatmap(ax, project_names, data)
plt.title("Mapa de Calor Lecturas por Proyecto")
plt.tight_layout()
st.pyplot(fig)
