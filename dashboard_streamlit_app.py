import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import os

# --- CONFIGURACIÓ DE PÀGINA ---
st.set_page_config(layout="wide", page_title="BCN Mobilitat & Sostenibilitat")

# ==============================================================================
# 1. NOMS DE ZONES
# ==============================================================================
NOMS_ZONES = {
    0: "Residencial / Zona alta",
    1: "Centre Neuràlgic",
    2: "Vida de Barri",
    3: "Perifèria / Zona Tranquila",
    4: "Zones d'Alta Saturació / Turisme",
}

# ==============================================================================
# 2. GLOSSARI (Explicacions Barra Lateral)
# ==============================================================================
EXPLICACIONS = {
    "Centre Neuràlgic": "Cor de la ciutat (Eixample). Màxim volum de viatges i connectivitat (PageRank).",
    "Perifèria / Zona Tranquila": "Zones allunyades (Torre Baró, Vallbona). Volum molt baix però distàncies de viatge molt llargues.",
    "Zones d'Alta Saturació / Turisme": "Zones que reben una quantitat massiva de gent en proporció a la seva mida (Casc Antic, Barceloneta). Tenen la pressió més alta.",
    "Vida de Barri": "Barris densos amb molta activitat interna (Gràcia, Sants). Distàncies de viatge molt curtes (proximitat).",
    "Residencial / Zona alta": "Barris tranquils i ben connectats (Sarrià). Sense saturació turística."
}

# ==============================================================================
# 3. COLORS D'ALT CONTRAST
# ==============================================================================
COLOR_MAP = {
    "Centre Neuràlgic": "#E63946",                  # VERMELL
    "Perifèria / Zona Tranquila": "#2A9D8F",        # VERD
    "Vida de Barri": "#F4A261",                     # TARONJA
    "Residencial / Zona alta": "#457B9D",           # BLAU
    "Zones d'Alta Saturació / Turisme": "#9B5DE5",  # LILA
    "General": "#CCCCCC",
    "Altres": "#CCCCCC"
}

# --- FITXERS ---
FILE_CSV = "dades_dashboard_completes.csv"
FILE_GEO = "barris.geojson"

# --- CÀRREGA DE DADES ---
@st.cache_data
def load_data():
    if not os.path.exists(FILE_CSV) or not os.path.exists(FILE_GEO):
        return None, f"❌ FALTEN FITXERS: Assegura't de tenir '{FILE_CSV}' i '{FILE_GEO}'."

    try:
        # 1. Carregar CSV
        df = pd.read_csv(FILE_CSV)
        col_nom = df.columns[0]
        df = df.rename(columns={col_nom: 'Nom_Barri'})
        df['id_match'] = df['Nom_Barri'].astype(str).str.strip().str.lower()

        # NETEJA DE SEGURETAT
        cols_numeriques = ['in_total_viajes', 'num_paradas_tmb', 'presion_tmb', 'avg_distance_in', 'pagerank', 'entropy_in']
        for col in cols_numeriques:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 2. Carregar Mapa
        gdf = gpd.read_file(FILE_GEO)
        geo_col = next((c for c in ['n_barri', 'NOM', 'barrio', 'Name'] if c in gdf.columns), None)
        if not geo_col: return None, "Error: No columna noms GeoJSON"
        gdf['id_match'] = gdf[geo_col].astype(str).str.strip().str.lower()

        # 3. Merge i Reprojecció
        merged = gdf.merge(df, on='id_match', how='left')
        if merged.crs and merged.crs.to_string() != "EPSG:4326":
            merged = merged.to_crs(epsg=4326)
        
        merged['presion_tmb'] = merged['presion_tmb'].fillna(0)
        
        # 4. Assignar Noms
        if 'cluster_kmeans' in merged.columns:
            merged['cluster_kmeans'] = pd.to_numeric(merged['cluster_kmeans'], errors='coerce').fillna(-1).astype(int)
            merged['Nom_Zona'] = merged['cluster_kmeans'].map(NOMS_ZONES).fillna("Altres")
            merged = merged.sort_values('cluster_kmeans')
        else:
            merged['Nom_Zona'] = "General"

        # 5. Centre Mapa
        if not merged.geometry.is_empty.all():
            centroid = merged.geometry.centroid
            center_lat = centroid.y.mean()
            center_lon = centroid.x.mean()
        else:
            center_lat, center_lon = 41.39, 2.17

        return merged, (center_lat, center_lon)

    except Exception as e:
        return None, f"Error: {e}"

# --- INICI APP ---
data_loaded = load_data()
if not data_loaded: st.stop()
gdf, map_center = data_loaded

if isinstance(gdf, str):
    st.error(gdf)
    st.stop()

# ==============================================================================
# 🎯 BARRA LATERAL (ESTIL MILLORAT)
# ==============================================================================
with st.sidebar:
    st.title("ℹ️ Llegenda de Zones")
    st.markdown("Categories identificades segons patrons de mobilitat (IA).")
    
    st.markdown("---")
    
    for zona, descripcio in EXPLICACIONS.items():
        color = COLOR_MAP.get(zona, "#333")
        st.markdown(
            f"""
            <div style="margin-bottom: 20px;">
                <div style="display: flex; align-items: center; margin-bottom: 5px;">
                    <span style="display: inline-block; width: 15px; height: 15px; background-color: {color}; border-radius: 50%; margin-right: 10px;"></span>
                    <strong style="font-size: 16px; color: #FFFFFF;">{zona}</strong>
                </div>
                <div style="font-size: 14px; color: #F0F0F0; margin-left: 25px; line-height: 1.4;">
                    {descripcio}
                </div>
            </div>
            """, 
            unsafe_allow_html=True
        )
    
    st.markdown("---")
    st.caption("UPF - SmartMove")

# ==============================================================================
# COS PRINCIPAL
# ==============================================================================

st.title("SMARTMOVE: Mobilitat i Sostenibilitat per Barris a Barcelona")
# (Hem eliminat els KPIs d'aquí sota per netejar la vista)

st.divider()

# --- PESTANYES ---
tab_map, tab_scatter, tab_ranking = st.tabs(["🗺️ Mapa de Zones", "⚖️ Eficiència", "📊 Rànquing i Identificació"])

# TAB 1: MAPA
with tab_map:
    col_sel, col_viz = st.columns([1, 4])
    with col_sel:
        metric = st.selectbox("Pintar per:", ["Nom_Zona", "presion_tmb", "in_total_viajes"], index=0)
        
        with st.expander("ℹ️ Llegenda de variables", expanded=True):
            st.markdown("""
            * **🏃 in_total_viajes (Demanda):**
              Volum total de persones que arriben al barri.
            
            * **🔥 presion_tmb (Saturació):** `Viatges / Parades`. 
              Indica si la infraestructura està sobrecarregada (Vermell = Saturat).
            """)
    
    with col_viz:
        gdf_map = gdf.set_index('Nom_Barri')
        
        color_kw = {}
        if metric == "Nom_Zona":
            color_kw = {"color_discrete_map": COLOR_MAP}
        elif metric == "presion_tmb":
             color_kw = {"color_continuous_scale": "RdYlBu_r"}
        
        fig_map = px.choropleth_mapbox(
            gdf_map, geojson=gdf_map.geometry, locations=gdf_map.index,
            color=metric, hover_name=gdf_map.index,
            hover_data=['in_total_viajes', 'presion_tmb', 'Nom_Zona'],
            mapbox_style="carto-positron",
            center={"lat": map_center[0], "lon": map_center[1]}, zoom=11.5, opacity=0.6,
            title=f"Mapa: {metric}",
            **color_kw
        )
        fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=600)
        st.plotly_chart(fig_map, use_container_width=True)

# TAB 2: SCATTER
with tab_scatter:
    st.subheader("Anàlisi d'Eficiència (Inversió vs Ús)")
    fig_sc = px.scatter(
        gdf, x="num_paradas_tmb", y="in_total_viajes",
        color="Nom_Zona", 
        color_discrete_map=COLOR_MAP,
        hover_name="Nom_Barri",
        trendline="ols", 
        trendline_scope="overall",       
        trendline_color_override="gray", 
        height=600,
        labels={"num_paradas_tmb": "Oferta (Parades)", "in_total_viajes": "Demanda (Viatges)"}
    )
    fig_sc.update_traces(marker=dict(size=12, opacity=0.8, line=dict(width=1, color='DarkSlateGrey')))
    st.plotly_chart(fig_sc, use_container_width=True)

# TAB 3: RÀNQUING
with tab_ranking:
    st.subheader("🏆 Top Barris per Volum (Rànquing)")
    top_n = st.slider("Nombre de barris a mostrar:", 5, 50, 20)
    df_top = gdf.sort_values('in_total_viajes', ascending=True).tail(top_n)
    
    fig_bar = px.bar(
        df_top,
        x="in_total_viajes",
        y="Nom_Barri",
        color="Nom_Zona",
        color_discrete_map=COLOR_MAP,
        orientation='h',
        height=600,
        text="in_total_viajes",
        title=f"Top {top_n} Barris amb més viatges"
    )
    fig_bar.update_traces(texttemplate='%{text:.2s}', textposition='outside')
    st.plotly_chart(fig_bar, use_container_width=True)
    
    st.divider()

    st.subheader("🕵️ Identificació Tècnica (Semàfor)")
    
    # Explicació tècnica de les columnes
    st.info("""
    **Diccionari de variables tècniques:**
    * **in_total_viajes:** Demanda total (persones que arriben).
    * **avg_distance_in:** Distància mitjana recorreguda pels usuaris (km).
    * **pagerank:** Importància a la xarxa (Nusos de comunicació).
    * **presion_tmb:** Ràtio de saturació (Viatges per parada).
    """)

    if 'cluster_kmeans' in gdf.columns:
        cols_analisi = ['in_total_viajes', 'avg_distance_in', 'pagerank', 'presion_tmb']
        cols_existents = [c for c in cols_analisi if c in gdf.columns]
        
        perfil = gdf.groupby('cluster_kmeans')[cols_existents].mean()
        perfil = perfil[perfil.index.isin(NOMS_ZONES.keys())]
        perfil['Nom Actual'] = perfil.index.map(NOMS_ZONES)
        
        format_dict = {col: "{:.2f}" for col in cols_existents}
        
        st.dataframe(
            perfil.style.background_gradient(cmap='YlOrRd', subset=cols_existents)
                  .format(format_dict),
            use_container_width=True
        )
