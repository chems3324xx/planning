import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Simulateur Planning Maintenance", layout="wide")
st.title("🛠️ Simulateur de Planning Maintenance")

uploaded_file = st.file_uploader("📂 Importer un fichier Excel ou CSV", type=["xlsx", "csv"])

def get_dataframe(file):
    if file.name.lower().endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)

if uploaded_file:
    try:
        df = get_dataframe(uploaded_file)
    except Exception as e:
        st.error(f"Erreur de lecture du fichier : {e}")
        st.stop()

    st.success("✅ Fichier importé")
    st.write("Aperçu :", df.head())

    # 1) Détecter une colonne “Nombre d'Equipements” sinon laisser choisir
    default_col = None
    for col in df.columns:
        if col.strip().lower().replace("’","'") in ["nombre d'equipements", "nombre d'équipements", "nb equipements", "nb équipements", "equipements", "équipements"]:
            default_col = col
            break

    numeric_cols = [c for c in df.columns if pd.to_numeric(df[c], errors="coerce").notna().sum() > 0]
    col_choisie = st.selectbox(
        "Colonne contenant le **nombre d'équipements**",
        options=numeric_cols if numeric_cols else list(df.columns),
        index=(numeric_cols.index(default_col) if default_col in numeric_cols else 0) if numeric_cols else 0
    )

    # 2) Conversion en numérique sécurisée
    nb_equip = pd.to_numeric(df[col_choisie], errors="coerce").fillna(0)

    # 3) Estimation simple: 15 min par équipement + 10 min par client
    # -> 0.25 h par équipement + 0.1667 h fixes
    df_out = df.copy()
    df_out["Durée estimée (h)"] = nb_equip * 0.25 + (10/60)

    st.write("Résultat :", df_out.head())

    st.download_button(
        "💾 Télécharger le CSV avec estimation",
        data=df_out.to_csv(index=False).encode("utf-8"),
        file_name="planning.csv",
        mime="text/csv",
    )
else:
    st.info("Veuillez importer un fichier pour commencer.")
