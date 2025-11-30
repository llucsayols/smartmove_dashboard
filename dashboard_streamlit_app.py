import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import os

# --- CONFIGURACIÓ DE PÀGINA ---
st.set_page_config(layout="wide", page_title="BCN Mobilitat: Residents vs Turistes")

# ==============================================================================
# 1. DEFINICIONS I ESTILS
# ==============================================================================
NOMS_ZONES = {
    0: "Residencial / Zona alta",
    1: "Centre Neuràlgic",
    2: "Vida de Barri",
    3: "Perifèria / Zona Tranquila",
    4: "Zones d'Alta Saturació / Turisme",
}

COLOR_MAP = {
    "Centre Neuràlgic": "#E63946",         
    "Perifèria / Zona Tranquila": "#2A9D8F",
    "Vida de Barri": "#F4A261",            
    "Residencial / Zona alta": "#457B9D",  
    "Zones d'Alta Saturació / Turisme": "#9B5DE5",
    "General": "#CCCCCC",
    "Altres": "#CCCCCC"
}

# --- RUTES DELS FITXERS ---
FILE_CSV = "dades_dashboard_completes.csv"
FILE_GEO = "barris.geojson"

# --- CÀRREGA DE DADES ---
@st.cache_data
def load_data():
    if not os.path.exists(FILE_CSV) or not os.path.exists(FILE_GEO):
        return None, f"❌ Error: Falten els fitxers de dades ({FILE_CSV} o {FILE_GEO})."

    try:
        # 1. Carregar Dades
        df = pd.read_csv(FILE_CSV)
        
        # Normalitzar noms
        df.columns = df.columns.str.strip()
        # Assegurem que tenim la columna clau 'Nom_Barri'
        if 'Nom_Barri' not in df.columns:
             # Si per algun motiu la primera es diu diferent, la renomem
             df = df.rename(columns={df.columns[0]: 'Nom_Barri'})

        df['id_match'] = df['Nom_Barri'].astype(str).str.strip().str.lower()

        # 2. Carregar Mapa
        gdf = gpd.read_file(FILE_GEO)
        geo_col = next((c for c in ['n_barri', 'NOM', 'barrio', 'Name'] if c in gdf.columns), None)
        if not geo_col: return None, "Error: El GeoJSON no té columna de noms."
        gdf['id_match'] = gdf[geo_col].astype(str).str.strip().str.lower()

        # 3. Merge
        merged = gdf.merge(df, on='id_match', how='left')
        
        # Neteja de nuls
        cols_num = ['res_viajes', 'tur_viajes', 'in_total_viajes', 'num_paradas_tmb', 'presion_tmb']
        for c in cols_num:
            if c in merged.columns:
                merged[c] = pd.to_numeric(merged[c], errors='coerce').fillna(0)

        # 4. Assignar Zones
        if 'cluster_kmeans' in merged.columns:
            merged['cluster_kmeans'] = pd.to_numeric(merged['cluster_kmeans'], errors='coerce').fillna(-1).astype(int)
            merged['Nom_Zona'] = merged['cluster_kmeans'].map(NOMS_ZONES).fillna("Altres")
        else:
            merged['Nom_Zona'] = "General"

        # Coordenades
        if merged.crs and merged.crs.to_string() != "EPSG:4326":
             merged = merged.to_crs(epsg=4326)
             
        centroid = merged.geometry.centroid
        return merged, (centroid.y.mean(), centroid.x.mean())

    except Exception as e:
        return None, f"Error de càrrega: {e}"

# --- INICI ---
data_loaded = load_data()
if not data_loaded: st.stop()
gdf, map_center = data_loaded

if isinstance(gdf, str):
    st.error(gdf)
    st.stop()

# ==============================================================================
# SIDEBAR
# ==============================================================================
with st.sidebar:
    st.header("Paràmetres")
    st.markdown("---")
    st.markdown("**Llegenda de Zones:**")
    for z, color in COLOR_MAP.items():
        if z not in ["General", "Altres"]:
            st.markdown(f"<span style='color:{color}'>■</span> {z}", unsafe_allow_html=True)

# ==============================================================================
# MAIN
# ==============================================================================
st.title("SmartMove: Sotenibilitat i Mobilitat Urbana")
st.markdown("Anàlisi de fluxos de **Residents vs Turistes** i la pressió sobre el transport.")
st.divider() 

tab1, tab2, tab3 = st.tabs(["🗺️ Mapa General", "⚖️ Oferta vs Demanda", "🏆 Rànquing de Volum"])

# --- TAB 1: MAPA ---
with tab1:
    col1, col2 = st.columns([1, 3])
    with col1:
        tema = st.radio("Visualitzar:", ["Zona (Cluster)", "Volum Total", "Pressió Transport"])
        
        # Explicació contextual
        if tema == "Pressió Transport":
            st.info("""
            **🔥 Què és la Pressió (presion_tmb)?**
            
            És una ràtio que mesura la intensitat d'ús de la infraestructura:
            
            $$
            \\text{Pressió} = \\frac{\\text{Volum Total de Viatges}}{\\text{Nombre de Parades/Estacions}}
            $$
            
            * **Valors alts (Vermell):** Indiquen un possible risc de saturació, on molta gent depèn de poques parades.
            * **Valors baixos (Blau):** Indiquen una bona cobertura de transport respecte a la demanda.
            """)
        elif tema == "Volum Total":
            st.info("Suma total de viatges (Residents + Turistes) que tenen aquest barri com a destinació.")
        
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
            cm = "RdYlBu_r"
            is_cat = False
            
    with col2:
        gdf_map = gdf.set_index('Nom_Barri')
        
        args = {
            "geojson": gdf_map.geometry,
            "locations": gdf_map.index,
            "color": col,
            "hover_name": gdf_map.index,
            "hover_data": ["res_viajes", "tur_viajes", "num_paradas_tmb"],
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

# --- TAB 2: SCATTER (Supply vs Demand) ---
with tab2:
    st.subheader("Eficiència: Infraestructura vs Ús Real")
    
    # Etiquetes intel·ligents (Top 10%)
    limit_x = gdf['num_paradas_tmb'].quantile(0.90)
    limit_y = gdf['in_total_viajes'].quantile(0.90)
    
    gdf['label'] = gdf.apply(lambda x: x['Nom_Barri'] if (x['in_total_viajes'] > limit_y or x['num_paradas_tmb'] > limit_x) else "", axis=1)
    
    fig_sc = px.scatter(
        gdf,
        x="num_paradas_tmb",
        y="in_total_viajes",
        color="Nom_Zona",
        size="tur_viajes", # La mida del punt indica el pes del turisme
        color_discrete_map=COLOR_MAP,
        text="label",
        hover_name="Nom_Barri",
        hover_data=["res_viajes", "tur_viajes"],
        trendline="ols",
        trendline_scope="overall",
        trendline_color_override="gray",
        height=600,
        labels={
            "num_paradas_tmb": "Oferta (Parades)",
            "in_total_viajes": "Demanda Total (Viatges)",
            "tur_viajes": "Volum Turístic"
        }
    )
    fig_sc.update_traces(textposition='top center', marker=dict(opacity=0.8, line=dict(width=1, color='DarkSlateGrey')))
    st.plotly_chart(fig_sc, use_container_width=True)
    st.caption("* La mida del cercle representa el volum de turistes.")

# --- TAB 3: RÀNQUING (MODIFICAT PER VOLUM) ---
with tab3:
    st.subheader("📊 Top Barris per Volum de Viatges")
    
    # Selector
    top_n = st.slider("Nombre de barris:", 5, 30, 15)
    
    # 1. Ordenem per VOLUM TOTAL
    df_rank = gdf.sort_values('in_total_viajes', ascending=True).tail(top_n) # tail perquè en horitzontal el gran queda a dalt si fem ascending
    
    # 2. Gràfic de Barres Apilades (Stacked) per veure la composició
    # Per fer-ho fàcil amb plotly express, cal fer un 'melt' (transformar a format llarg)
    df_long = df_rank.melt(
        id_vars=['Nom_Barri'], 
        value_vars=['res_viajes', 'tur_viajes'],
        var_name='Tipus_Usuari', 
        value_name='Viatges'
    )
    
    # Canviem noms per a la llegenda
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
        color_discrete_map={'Residents 🏠': '#457B9D', 'Turistes 📷': '#E63946'},
        text_auto='.2s' # Format compacte (k, M)
    )
    
    # Ordenar eix Y pel total (suma de residents + turistes)
    # Com que df_rank ja estava ordenat per 'in_total_viajes', utilitzem el seu ordre
    fig_bar.update_layout(yaxis={'categoryorder': 'array', 'categoryarray': df_rank['Nom_Barri']})
    
    st.plotly_chart(fig_bar, use_container_width=True)
    
    # Taula de dades
    st.markdown("#### Dades detallades")
    cols_show = ['Nom_Barri', 'Nom_Zona', 'in_total_viajes', 'res_viajes', 'tur_viajes', 'presion_tmb']
    
    # Mostrem els de dalt de tot, ordenats de major a menor
    df_table = gdf.sort_values('in_total_viajes', ascending=False).head(top_n)[cols_show]
    
    st.dataframe(
        df_table.style.background_gradient(subset=['in_total_viajes'], cmap='Greens'),
        use_container_width=True
    )
