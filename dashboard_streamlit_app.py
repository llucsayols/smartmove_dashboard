import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import os

# --- CONFIGURACIÓ DE PÀGINA ---
st.set_page_config(layout="wide", page_title="BCN Mobilitat: Residents vs Turistes")

# ==============================================================================
# 1. DEFINICIONS DE ZONES (Clusters)
# ==============================================================================
# Diccionari per mapar els números de cluster a noms entenedors
NOMS_ZONES = {
    0: "Residencial / Zona alta",
    1: "Centre Neuràlgic",
    2: "Vida de Barri",
    3: "Perifèria / Zona Tranquila",
    4: "Zones d'Alta Saturació / Turisme",
}

# Explicació de cada zona per a la barra lateral
EXPLICACIONS_ZONES = {
    "Centre Neuràlgic": """ 
    Tenen el màxim volum de viatges (tothom hi passa) i una connectivitat (PageRank) molt alta.
    """,
    "Zones d'Alta Saturació / Turisme": """
    Reben una quantitat massiva de visitants en comparació amb la seva població resident.
    Tenen la pressió sobre l'espai públic més alta.
    """,
    "Vida de Barri": """
    Tenen molta activitat, però és sobretot interna i de proximitat.
    Les distàncies de viatge són curtes i la ràtio residents/turistes és equilibrada.
    """,
    "Residencial / Zona alta": """
    Són àrees tranquil·les, ben connectades, però que no actuen com a nusos de pas ni com a grans atraccions turístiques.
    """,
    "Perifèria / Zona Tranquila": """
    Tenen un volum de viatges molt baix, però les distàncies que han de recórrer els usuaris per arribar-hi són les més llargues.
    """
}

# Colors consistents per a tot el dashboard
COLOR_MAP = {
    "Centre Neuràlgic": "#E63946",         # Vermell
    "Perifèria / Zona Tranquila": "#2A9D8F", # Verd
    "Vida de Barri": "#F4A261",            # Taronja
    "Residencial / Zona alta": "#457B9D",  # Blau
    "Zones d'Alta Saturació / Turisme": "#9B5DE5", # Lila
    "General": "#CCCCCC",
    "Altres": "#CCCCCC"
}

# --- RUTES DELS FITXERS ---
FILE_CSV = "dades_dashboard_completes.csv"
FILE_GEO = "barris.geojson"

# --- CÀRREGA DE DADES ---
@st.cache_data
def load_data():
    # Comprovem que els fitxers existeixin al repositori
    if not os.path.exists(FILE_CSV) or not os.path.exists(FILE_GEO):
        return None, f"❌ Error: Falten els fitxers de dades ({FILE_CSV} o {FILE_GEO})."

    try:
        # 1. Carregar CSV de Dades
        df = pd.read_csv(FILE_CSV)
        
        # Neteja bàsica de noms de columna
        df.columns = df.columns.str.strip()
        if 'Nom_Barri' not in df.columns:
             # Si la primera columna té un nom estrany, la renomem a Nom_Barri
             df = df.rename(columns={df.columns[0]: 'Nom_Barri'})

        # Creem un ID en minúscules per fer el 'merge' sense problemes
        df['id_match'] = df['Nom_Barri'].astype(str).str.strip().str.lower()

        # 2. Carregar GeoJSON (Mapa)
        gdf = gpd.read_file(FILE_GEO)
        # Busquem la columna de nom al GeoJSON (sol dir-se 'n_barri' o 'NOM')
        geo_col = next((c for c in ['n_barri', 'NOM', 'barrio', 'Name'] if c in gdf.columns), None)
        if not geo_col: return None, "Error: El GeoJSON no té columna de noms."
        gdf['id_match'] = gdf[geo_col].astype(str).str.strip().str.lower()

        # 3. Unir Dades i Mapa (Merge)
        merged = gdf.merge(df, on='id_match', how='left')
        
        # Convertim columnes numèriques i omplim buits amb 0
        cols_num = ['res_viajes', 'tur_viajes', 'in_total_viajes', 'num_paradas_tmb', 'presion_tmb']
        for c in cols_num:
            if c in merged.columns:
                merged[c] = pd.to_numeric(merged[c], errors='coerce').fillna(0)

        # 4. Assignar Noms de Zona (Cluster)
        if 'cluster_kmeans' in merged.columns:
            merged['cluster_kmeans'] = pd.to_numeric(merged['cluster_kmeans'], errors='coerce').fillna(-1).astype(int)
            merged['Nom_Zona'] = merged['cluster_kmeans'].map(NOMS_ZONES).fillna("Altres")
        else:
            merged['Nom_Zona'] = "General"

        # Calculem el centre del mapa per centrar la visualització inicial
        if merged.crs and merged.crs.to_string() != "EPSG:4326":
             merged = merged.to_crs(epsg=4326)
        centroid = merged.geometry.centroid
        
        return merged, (centroid.y.mean(), centroid.x.mean())

    except Exception as e:
        return None, f"Error de càrrega: {e}"

# --- INICIALITZACIÓ ---
data_loaded = load_data()
if not data_loaded: st.stop()
gdf, map_center = data_loaded

# Si load_data retorna un missatge d'error (string), el mostrem i parem
if isinstance(gdf, str):
    st.error(gdf)
    st.stop()

# ==============================================================================
# BARRA LATERAL (LLEGENDA I EXPLICACIONS)
# ==============================================================================
with st.sidebar:
    st.title("ℹ️ Llegenda de Zones")
    st.markdown("L'algoritme ha agrupat els barris en 5 perfils segons el seu comportament:")
    st.markdown("---")
    
    # Mostrem la llegenda amb els colors i les explicacions
    for zona, descripcio in EXPLICACIONS_ZONES.items():
        color = COLOR_MAP.get(zona, "#333")
        st.markdown(
            f"""
            <div style="margin-bottom: 15px; border-left: 5px solid {color}; padding-left: 10px;">
                <h4 style="color: {color}; margin: 0;">{zona}</h4>
                <span style="font-size: 0.9em; color: #DDD;">{descripcio}</span>
            </div>
            """, 
            unsafe_allow_html=True
        )
    
    st.markdown("---")
    st.caption("Projecte SmartMove Analysis")

# ==============================================================================
# PÀGINA PRINCIPAL
# ==============================================================================
st.title("SmartMove: Sotenibilitat i Mobilitat Urbana")
st.markdown("Anàlisi de fluxos de Residents vs Turistes i la pressió sobre el transport.")
st.divider()

# Pestanyes de navegació
tab1, tab2, tab3 = st.tabs(["🗺️ Mapa General", "⚖️ Oferta vs Demanda", "🏆 Rànquing de Volum"])

# --- PESTANYA 1: MAPA ---
with tab1:
    col1, col2 = st.columns([1, 3])
    with col1:
        st.subheader("Configuració")
        tema = st.radio("Pintar barris per:", ["Zona (Cluster)", "Volum Total", "Pressió Transport"])
        
        # Quadre d'informació dinàmic segons el que es triï
        if tema == "Pressió Transport":
            st.info("""
            **🔥 Què és la Pressió?**
            
            Indica la intensitat d'ús de la infraestructura de transport.
            
            $$
            \\text{Pressió} = \\frac{\\text{Viatges Totals}}{\\text{Parades}}
            $$
            
            * **Alta (Vermell):** Molts viatges per a poques parades (Risc de saturació).
            * **Baixa (Blau):** Bona cobertura de transport per la demanda que hi ha.
            """)
        elif tema == "Volum Total":
            st.info("""
            **🏃 Volum Total**
            
            Suma de tots els viatges que tenen aquest barri com a destinació final.
            
            $$
            \\text{Total} = \\text{Residents} + \\text{Turistes}
            $$
            """)
        
        # Configuració de colors per al mapa
        if tema == "Zona (Cluster)":
            col = "Nom_Zona"
            cm = COLOR_MAP
            is_cat = True
        elif tema == "Volum Total":
            col = "in_total_viajes"
            cm = "Viridis"
            is_cat = False
        else:
            col = "presion_tmb"
            cm = "RdYlBu_r" # Vermell = Alta pressió
            is_cat = False
            
    with col2:
        gdf_map = gdf.set_index('Nom_Barri')
        
        # Preparem dades pel tooltip (el que es veu al passar el ratolí)
        hover = ["num_paradas_tmb", "presion_tmb"]
        if "res_viajes" in gdf.columns: hover += ["res_viajes", "tur_viajes"]

        # Creem el mapa
        args = {
            "geojson": gdf_map.geometry,
            "locations": gdf_map.index,
            "color": col,
            "hover_name": gdf_map.index,
            "hover_data": hover,
            "mapbox_style": "carto-positron",
            "center": {"lat": map_center[0], "lon": map_center[1]},
            "zoom": 11.5,
            "opacity": 0.7,
            "height": 600
        }
        
        if is_cat:
            fig = px.choropleth_mapbox(gdf_map, color_discrete_map=cm, **args)
        else:
            fig = px.choropleth_mapbox(gdf_map, color_continuous_scale=cm, **args)
            
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig, use_container_width=True)

# --- PESTANYA 2: SCATTER (Supply vs Demand) ---
with tab2:
    st.subheader("Eficiència: Infraestructura vs Ús Real")
    
    # Càlcul de límits per etiquetar només els barris extrems (Top 10%)
    limit_x = gdf['num_paradas_tmb'].quantile(0.90)
    limit_y = gdf['in_total_viajes'].quantile(0.90)
    
    # Creem etiqueta només si supera algun límit
    gdf['label'] = gdf.apply(lambda x: x['Nom_Barri'] if (x['in_total_viajes'] > limit_y or x['num_paradas_tmb'] > limit_x) else "", axis=1)
    
    # Definim la mida del punt segons el volum de turistes (si tenim la dada)
    size_col = "tur_viajes" if "tur_viajes" in gdf.columns else None
    
    fig_sc = px.scatter(
        gdf,
        x="num_paradas_tmb",      # Eix X: Oferta
        y="in_total_viajes",      # Eix Y: Demanda Total
        color="Nom_Zona",         # Color: Cluster
        size=size_col,            # Mida: Volum de Turistes
        color_discrete_map=COLOR_MAP,
        text="label",             # Etiqueta: Nom del barri (només extrems)
        hover_name="Nom_Barri",
        trendline="ols",          # Línia de tendència
        trendline_scope="overall",
        trendline_color_override="gray",
        height=600,
        labels={
            "num_paradas_tmb": "Oferta (Nombre de Parades)",
            "in_total_viajes": "Demanda Total (Viatges)",
            "tur_viajes": "Volum Turístic",
            "Nom_Zona": "Tipus de Zona"
        }
    )
    
    # Millores estètiques
    fig_sc.update_traces(textposition='top center', marker=dict(opacity=0.8, line=dict(width=1, color='DarkSlateGrey')))
    
    st.plotly_chart(fig_sc, use_container_width=True)
    
    if size_col:
        st.info("ℹ️ **Nota:** La mida del cercle indica el volum de **Turistes**. Barris com l'Eixample tenen cercles grans perquè actuen com a nusos de transport i atracció turística.")

# --- PESTANYA 3: RÀNQUING (STACKED BAR) ---
with tab3:
    st.subheader("🏆 Top Barris per Volum de Viatges")
    
    # Slider per triar quants barris veure
    top_n = st.slider("Nombre de barris a mostrar:", 5, 30, 15)
    
    # 1. Ordenem les dades pel VOLUM TOTAL
    df_rank = gdf.sort_values('in_total_viajes', ascending=True).tail(top_n) 
    
    # 2. Gràfic de Barres Apilades (Residents + Turistes)
    if "res_viajes" in gdf.columns and "tur_viajes" in gdf.columns:
        # Transformem les dades per al gràfic (melt)
        df_long = df_rank.melt(
            id_vars=['Nom_Barri'], 
            value_vars=['res_viajes', 'tur_viajes'],
            var_name='Tipus_Usuari', 
            value_name='Viatges'
        )
        
        # Canviem noms per a la llegenda perquè quedi bonic
        df_long['Tipus_Usuari'] = df_long['Tipus_Usuari'].replace({
            'res_viajes': 'Residents 🏠', 
            'tur_viajes': 'Turistes 📷'
        })

        fig_bar = px.bar(
            df_long,
            x="Viatges",
            y="Nom_Barri",
            color="Tipus_Usuari",
            orientation='h',
            height=600,
            title=f"Top {top_n} Barris amb més moviment (Desglossat)",
            # Colors personalitzats per a les barres
            color_discrete_map={'Residents 🏠': '#457B9D', 'Turistes 📷': '#E63946'},
            text_auto='.2s' # Format automàtic (M, k)
        )
    else:
        # Si no tenim dades desglossades, mostrem barra simple
        fig_bar = px.bar(
            df_rank,
            x="in_total_viajes",
            y="Nom_Barri",
            color="Nom_Zona",
            orientation='h',
            height=600,
            color_discrete_map=COLOR_MAP
        )

    # Assegurem que l'ordre visual és correcte (de major a menor)
    fig_bar.update_layout(yaxis={'categoryorder': 'array', 'categoryarray': df_rank['Nom_Barri']})
    
    st.plotly_chart(fig_bar, use_container_width=True)
    
    # 3. Taula de Dades
    st.markdown("#### Dades detallades")
    
    # Columnes a mostrar a la taula
    cols_show = ['Nom_Barri', 'Nom_Zona', 'in_total_viajes']
    if "res_viajes" in gdf.columns: cols_show += ['res_viajes', 'tur_viajes']
    cols_show.append('presion_tmb')
    
    # Mostrem la taula ordenada
    df_table = gdf.sort_values('in_total_viajes', ascending=False).head(top_n)[cols_show]
    
    # Format de taula amb gradient de color
    st.dataframe(
        df_table.style.background_gradient(subset=['in_total_viajes'], cmap='Greens'),
        use_container_width=True
    )
