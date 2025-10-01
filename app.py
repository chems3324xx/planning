import streamlit as st
import pandas as pd

st.set_page_config(page_title="Simulateur Planning Maintenance", layout="wide")
st.title("🛠️ Simulateur de Planning Maintenance")

uploaded_file = st.file_uploader("📂 Importer un fichier Excel ou CSV", type=["xlsx", "csv"])

def load_df(file):
    if file.name.lower().endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)

if uploaded_file:
    try:
        df = load_df(uploaded_file)
    except Exception as e:
        st.error(f"Erreur de lecture du fichier : {e}")
        st.stop()

    st.success("✅ Fichier importé")
    st.caption("Aperçu brut (tel que dans le fichier) :")
    st.dataframe(df.head(20), use_container_width=True)

    # Sélecteurs de colonnes (robuste si les noms varient)
    st.subheader("Colonnes à utiliser")
    col_site = st.selectbox("Colonne du site", options=list(df.columns), index=max(0, list(df.columns).index("Description site")) if "Description site" in df.columns else 0)
    # Détection d'une colonne nombre d'équipements
    sugg_equip = None
    for c in df.columns:
        if "equip" in c.lower() or "équip" in c.lower():
            sugg_equip = c; break
    col_equip = st.selectbox("Colonne du nombre d'équipements", options=list(df.columns), index=list(df.columns).index(sugg_equip) if sugg_equip else 0)

    # Convertir la colonne équipements en numérique
    df[col_equip] = pd.to_numeric(df[col_equip], errors="coerce").fillna(0)

    # Agrégation par site
    sites = (
        df.groupby(col_site, dropna=False)[col_equip]
          .sum()
          .reset_index()
          .rename(columns={col_site: "Site", col_equip: "Total équipements"})
    )

    # Calcul de durée par site : 15 min/équipement + 10 min fixes
    sites["Durée estimée (h)"] = sites["Total équipements"] * (15/60) + (10/60)

    st.subheader("Clients agrégés (1 ligne par site)")
    c1, c2 = st.columns(2)
    c1.metric("Nombre de sites", f"{len(sites)}")
    c2.metric("Total équipements", f"{int(sites['Total équipements'].sum())}")

    st.dataframe(sites.sort_values("Total équipements", ascending=False), use_container_width=True, height=500)

    # Export
    st.download_button(
        "💾 Télécharger la liste agrégée (CSV)",
        data=sites.to_csv(index=False).encode("utf-8"),
        file_name="sites_agreges.csv",
        mime="text/csv"
    )

else:
    st.info("Veuillez importer un fichier pour commencer.")
