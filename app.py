import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Simulateur Planning Maintenance", layout="wide")

st.title("🛠️ Simulateur de Planning Maintenance")

uploaded_file = st.file_uploader("📂 Importer un fichier Excel ou CSV", type=["xlsx", "csv"])

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.success("✅ Fichier importé avec succès !")
    st.write("Aperçu des données :", df.head())

    # Exemple de mini-calcul (tu remplaceras par ton algo complet)
    df["Durée estimée (h)"] = df[df.columns[1]] * 0.25
    st.write("Tableau avec estimation :", df)

    st.download_button(
        label="💾 Télécharger le CSV avec estimation",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="planning.csv",
        mime="text/csv"
    )
else:
    st.info("Veuillez importer un fichier pour commencer.")
