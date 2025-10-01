import streamlit as st
import pandas as pd
import datetime as dt

st.set_page_config(page_title="Simulateur Planning Maintenance", layout="wide")
st.title("🛠️ Simulateur de Planning Maintenance")

uploaded_file = st.file_uploader("📂 Importer un fichier Excel ou CSV", type=["xlsx", "csv"])

def load_df(file):
    if file.name.lower().endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)

# ---------- Paramètres ----------
st.sidebar.header("Paramètres planning")
start_date = st.sidebar.date_input("📅 Date de début", value=dt.date.today())
weeks_to_show = st.sidebar.number_input("Nombre de semaines à afficher", 1, 26, 8, 1)
reserve_h = st.sidebar.number_input("Réserve dépannage (h/j ouvré)", 0.0, 6.0, 1.5, 0.5)

st.sidebar.caption("Rythme hebdo (heures) :")
h_mon = st.sidebar.number_input("Lundi", 0.0, 12.0, 8.0, 0.5)
h_tue = st.sidebar.number_input("Mardi", 0.0, 12.0, 8.0, 0.5)
h_wed = st.sidebar.number_input("Mercredi", 0.0, 12.0, 8.0, 0.5)
h_thu = st.sidebar.number_input("Jeudi", 0.0, 12.0, 8.0, 0.5)
h_fri = st.sidebar.number_input("Vendredi", 0.0, 12.0, 7.0, 0.5)
day_pattern = {0:h_mon,1:h_tue,2:h_wed,3:h_thu,4:h_fri}  # 0=Lundi … 4=Vendredi

small_thresh = st.sidebar.number_input("Seuil 'petit client' (nb équipements)", 1, 100, 8, 1)
off_text = st.sidebar.text_area("Jours OFF (JJ/MM/AAAA, séparés par virgules)", "")

def parse_off_days(text):
    s = set()
    for tok in text.replace("\n", ",").split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            d = dt.datetime.strptime(tok, "%d/%m/%Y").date()
            s.add(d)
        except:
            pass
    return s

off_days = parse_off_days(off_text)

def cap_for_day(d: dt.date) -> float:
    wd = d.weekday()
    if wd > 4:  # samedi/dimanche
        return 0.0
    raw = day_pattern.get(wd, 0.0)
    if raw <= 0:
        return 0.0
    if d in off_days:
        return 0.0
    return max(0.0, raw - reserve_h)

WEEKDAYS_FR = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]

# ---------- Corps ----------
if uploaded_file:
    try:
        df = load_df(uploaded_file)
    except Exception as e:
        st.error(f"Erreur de lecture du fichier : {e}")
        st.stop()

    st.success("✅ Fichier importé")
    st.caption("Aperçu brut :")
    st.dataframe(df.head(20), use_container_width=True)

    # Sélecteurs colonnes (empêche la même colonne 2x)
    st.subheader("Colonnes à utiliser")
    col_site = st.selectbox("Colonne du site", options=list(df.columns))
    options_equip = [c for c in df.columns if c != col_site]

    # suggestion auto si 'équip' détecté
    sugg_equip = None
    for c in options_equip:
        if "equip" in c.lower() or "équip" in c.lower():
            sugg_equip = c; break

    col_equip = st.selectbox(
        "Colonne du nombre d'équipements",
        options=options_equip,
        index=options_equip.index(sugg_equip) if sugg_equip in options_equip else 0
    )

    # Nettoyage / agrégation
    df[col_equip] = pd.to_numeric(df[col_equip], errors="coerce").fillna(0)
    sites = (
        df.groupby(col_site, dropna=False)[col_equip]
          .sum()
          .reset_index()
          .rename(columns={col_site: "Site", col_equip: "Total équipements"})
    )

    # Durée par site (h) : 15 min/équip + 10 min fixes
    sites["Durée (h)"] = sites["Total équipements"] * (15/60) + (10/60)
    # Info rapide
    c1,c2 = st.columns(2)
    c1.metric("Nombre de sites", f"{len(sites)}")
    c2.metric("Total équipements", f"{int(sites['Total équipements'].sum())}")

    # File de travail (on commence par les plus chronophages)
    queue = (sites.sort_values("Durée (h)", ascending=False)
                  .assign(Heures_restantes=lambda x: x["Durée (h)"])
                  .to_dict(orient="records"))

    # Génération du calendrier (Lun→Ven, nb semaines choisi)
    start = start_date
    # aligne sur un lundi visuel (optionnel)
    # while start.weekday() != 0: start -= dt.timedelta(days=1)

    days = []
    d = start
    for _ in range(weeks_to_show * 7):
        days.append(d)
        d += dt.timedelta(days=1)

    # Planning = liste de blocs alloués {date, jour, site, heures}
    allocations = []

    for d in days:
        if d.weekday() > 4:
            continue  # we ignore weekends in visual plan
        cap = cap_for_day(d)
        if d in off_days:
            allocations.append({
                "Date": d.strftime("%d/%m/%Y"),
                "Jour": WEEKDAYS_FR[d.weekday()],
                "Site": "OFF (RTT/Formation/Férié)",
                "Heures": 0.0
            })
            continue
        # Remplissage de la journée
        safety = 0
        while cap > 1e-9 and queue and safety < 2000:
            safety += 1
            # 1) petit client non entamé qui tient en entier
            pick_idx = None
            for idx, it in enumerate(queue):
                if it["Total équipements"] < small_thresh and abs(it["Heures_restantes"] - it["Durée (h)"]) < 1e-9:
                    if it["Heures_restantes"] <= cap + 1e-9:
                        pick_idx = idx
                        break
            # 2) sinon, prendre le premier
            if pick_idx is None:
                pick_idx = 0

            cur = queue[pick_idx]
            # allocation
            if cur["Total équipements"] < small_thresh and abs(cur["Heures_restantes"] - cur["Durée (h)"]) < 1e-9:
                alloc = cur["Heures_restantes"]  # on place en une fois
            else:
                alloc = min(cap, cur["Heures_restantes"])

            allocations.append({
                "Date": d.strftime("%d/%m/%Y"),
                "Jour": WEEKDAYS_FR[d.weekday()],
                "Site": cur["Site"],
                "Heures": round(float(alloc), 2)
            })
            cap -= alloc
            cur["Heures_restantes"] -= alloc
            if cur["Heures_restantes"] <= 1e-6:
                queue.pop(pick_idx)

    plan_df = pd.DataFrame(allocations)

    st.subheader("Planning visuel (semaine par semaine)")
    # construire un tableau par semaine (lundi→vendredi)
    if plan_df.empty:
        st.info("Aucune allocation sur la période affichée.")
    else:
        # grouper par semaine ISO
        plan_df["Date_dt"] = pd.to_datetime(plan_df["Date"], format="%d/%m/%Y")
        plan_df["Semaine"] = plan_df["Date_dt"].dt.isocalendar().week
        plan_df["Année"] = plan_df["Date_dt"].dt.isocalendar().year

        weeks = plan_df.drop_duplicates(["Année","Semaine"])[["Année","Semaine"]].sort_values(["Année","Semaine"]).values.tolist()

        for (year, week) in weeks:
            st.markdown(f"### Semaine {int(week)} — {int(year)}")
            # construit une grille L→V
            grid = {d: [] for d in ["Lundi","Mardi","Mercredi","Jeudi","Vendredi"]}
            sub = plan_df[(plan_df["Année"]==year) & (plan_df["Semaine"]==week)]
            for _, r in sub.iterrows():
                if r["Jour"] in grid:
                    label = f'{r["Date"]} — {r["Site"]} ({r["Heures"]}h)'
                    grid[r["Jour"]].append(label)
            # afficher en colonnes
            cols = st.columns(5)
            for i, dayname in enumerate(["Lundi","Mardi","Mercredi","Jeudi","Vendredi"]):
                with cols[i]:
                    st.markdown(f"**{dayname}**")
                    if grid[dayname]:
                        for line in grid[dayname]:
                            st.write("• " + line)
                    else:
                        st.caption("—")

    # Exports
    st.subheader("Exports")
    if not plan_df.empty:
        st.download_button(
            "📄 Télécharger planning (CSV)",
            data=plan_df[["Date","Jour","Site","Heures"]].to_csv(index=False).encode("utf-8"),
            file_name="planning.csv",
            mime="text/csv"
        )
    st.download_button(
        "💾 Télécharger sites agrégés (CSV)",
        data=sites.to_csv(index=False).encode("utf-8"),
        file_name="sites_agreges.csv",
        mime="text/csv"
    )

else:
    st.info("Veuillez importer un fichier pour commencer.")
