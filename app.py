import streamlit as st
import pandas as pd
import datetime as dt
import calendar

st.set_page_config(page_title="Simulateur Planning Maintenance", layout="wide")
st.title("🛠️ Simulateur de Planning Maintenance")

# ---------- Chargement ----------
uploaded_file = st.file_uploader("📂 Importer un fichier Excel ou CSV", type=["xlsx", "csv"])

def load_df(file):
    if file.name.lower().endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)

# ---------- Paramètres (barre latérale) ----------
st.sidebar.header("Paramètres planning")
reserve_h = st.sidebar.number_input("Réserve dépannage (h/j ouvré)", 0.0, 6.0, 1.5, 0.5)
lunch_h   = st.sidebar.number_input("Pause déjeuner (h)", 0.0, 3.0, 1.0, 0.25)

st.sidebar.caption("Rythme hebdo (heures sur place, avant réserve & pause) :")
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
    raw = float(day_pattern.get(wd, 0.0))
    if raw <= 0 or d in off_days:
        return 0.0
    cap = raw - reserve_h - lunch_h
    return max(0.0, cap)

WEEKDAYS_FR = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]

# ---------- Corps ----------
if not uploaded_file:
    st.info("Veuillez importer votre **fichier d’origine** (avec `Description site`, `Nombre de VE`/`Nombre d'Equipements`, `Mois VE`).")
    st.stop()

# Lecture
try:
    df = load_df(uploaded_file)
except Exception as e:
    st.error(f"Erreur de lecture du fichier : {e}")
    st.stop()

# ---------- Détection colonnes (fixes, sans filtres) ----------
def norm(s: str) -> str:
    return s.strip().lower().replace("’","'")

# Colonne Site (fixe -> Description site)
if "Description site" in df.columns:
    col_site = "Description site"
else:
    # secours: 1ère colonne qui contient 'site'
    candidates = [c for c in df.columns if "site" in norm(c)]
    if not candidates:
        st.error("Colonne 'Description site' introuvable et aucune colonne 'site' détectée.")
        st.stop()
    col_site = candidates[0]

# Colonne Nb équipements (fixe -> Nombre de VE, sinon Nombre d'Equipements)
if "Nombre de VE" in df.columns:
    col_equip = "Nombre de VE"
elif "Nombre d'Equipements" in df.columns:
    col_equip = "Nombre d'Equipements"
else:
    # secours: 1ère colonne contenant “equip/équip”
    candidates = [c for c in df.columns if ("equip" in norm(c) or "équip" in norm(c))]
    if not candidates:
        st.error("Aucune colonne de nombre d'équipements détectée (ni 'Nombre de VE' ni 'Nombre d'Equipements').")
        st.stop()
    col_equip = candidates[0]

# Colonne Mois VE (exigée)
if "Mois VE" in df.columns:
    col_month = "Mois VE"
else:
    st.error("Colonne 'Mois VE' introuvable (dates/mois à honorer).")
    st.stop()

st.success("✅ Fichier importé (colonnes détectées automatiquement)")
with st.expander("Aperçu du fichier (20 premières lignes)"):
    st.dataframe(df.head(20), use_container_width=True)

# ---------- Nettoyage & agrégation par (Site, Mois) ----------
df[col_equip] = pd.to_numeric(df[col_equip], errors="coerce").fillna(0)

# Transformer 'Mois VE' en date de début de mois
def parse_month_cell(x):
    if pd.isna(x):
        return None
    # essais courants: '10/2025', '2025-10', 'octobre 2025', '01/10/2025', etc.
    txt = str(x).strip()
    # Essai 1: JJ/MM/AAAA
    for fmt in ("%d/%m/%Y","%Y-%m-%d","%m/%Y","%b %Y","%B %Y"):
        try:
            d = dt.datetime.strptime(txt, fmt).date()
            # normalise au 1er du mois
            return dt.date(d.year, d.month, 1)
        except:
            pass
    # Si c'est déjà un timestamp Excel/pandas
    try:
        d = pd.to_datetime(x, dayfirst=True, errors="coerce")
        if pd.notna(d):
            d = d.date()
            return dt.date(d.year, d.month, 1)
    except:
        pass
    return None

df["_MoisDebut"] = df[col_month].apply(parse_month_cell)
if df["_MoisDebut"].isna().all():
    st.error("Impossible d'interpréter 'Mois VE'. Formats acceptés: JJ/MM/AAAA, MM/AAAA, AAAA-MM, 'octobre 2025', etc.")
    st.stop()

agg = (
    df.dropna(subset=["_MoisDebut"])
      .groupby([col_site, "_MoisDebut"], dropna=False)[col_equip]
      .sum()
      .reset_index()
      .rename(columns={col_site: "Site", col_equip: "Total équipements", "_MoisDebut":"Mois"})
)

# Durée par site (h) : 15 min/équip + 10 min fixes
agg["Durée (h)"] = agg["Total équipements"] * (15/60) + (10/60)

# ---------- Planning par mois (respect du mois de 'Mois VE') ----------
# On construit un calendrier couvrant du min(mois) au max(mois) inclus
if agg.empty:
    st.info("Aucune ligne exploitable après agrégation.")
    st.stop()

min_month = agg["Mois"].min()
max_month = agg["Mois"].max()

# Génère toutes les dates ouvrées pour chaque mois dans l'intervalle
def iter_months(start_month: dt.date, end_month: dt.date):
    y, m = start_month.year, start_month.month
    while (y < end_month.year) or (y == end_month.year and m <= end_month.month):
        yield dt.date(y, m, 1)
        if m == 12:
            y += 1; m = 1
        else:
            m += 1

def end_of_month(d: dt.date) -> dt.date:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return dt.date(d.year, d.month, last_day)

# File par mois : pour chaque mois, on planifie uniquement les sites de ce mois
allocations = []
for month_start in iter_months(min_month, max_month):
    month_end = end_of_month(month_start)

    # sous-ensemble des sites à honorer ce mois
    month_jobs = (
        agg[agg["Mois"] == month_start]
        .sort_values("Durée (h)", ascending=False)
        .assign(Heures_restantes=lambda x: x["Durée (h)"])
        .to_dict(orient="records")
    )

    # parcours des jours du mois, L→V
    d = month_start
    while d <= month_end and month_jobs:
        if d.weekday() <= 4:  # L→V
            cap = cap_for_day(d)
            if d in off_days:
                allocations.append({"Date": d.strftime("%d/%m/%Y"), "Jour": WEEKDAYS_FR[d.weekday()],
                                    "Mois": f"{month_start.month:02d}/{month_start.year}",
                                    "Site": "OFF (RTT/Formation/Férié)", "Heures": 0.0})
            else:
                safety = 0
                while cap > 1e-9 and month_jobs and safety < 2000:
                    safety += 1
                    # 1) petit client non entamé qui tient
                    pick_idx = None
                    for idx, it in enumerate(month_jobs):
                        if it["Total équipements"] < small_thresh and abs(it["Heures_restantes"] - it["Durée (h)"]) < 1e-9:
                            if it["Heures_restantes"] <= cap + 1e-9:
                                pick_idx = idx
                                break
                    # 2) sinon, prendre le premier
                    if pick_idx is None:
                        pick_idx = 0

                    cur = month_jobs[pick_idx]
                    if cur["Total équipements"] < small_thresh and abs(cur["Heures_restantes"] - cur["Durée (h)"]) < 1e-9:
                        alloc = cur["Heures_restantes"]
                    else:
                        alloc = min(cap, cur["Heures_restantes"])

                    allocations.append({
                        "Date": d.strftime("%d/%m/%Y"),
                        "Jour": WEEKDAYS_FR[d.weekday()],
                        "Mois": f"{month_start.month:02d}/{month_start.year}",
                        "Site": cur["Site"],
                        "Heures": round(float(alloc), 2)
                    })
                    cap -= alloc
                    cur["Heures_restantes"] -= alloc
                    if cur["Heures_restantes"] <= 1e-6:
                        month_jobs.pop(pick_idx)
        d += dt.timedelta(days=1)

    # S'il reste des heures non placées à la fin du mois → on le signale
    if month_jobs:
        reste = sum(x["Heures_restantes"] for x in month_jobs)
        allocations.append({
            "Date": end_of_month(month_start).strftime("%d/%m/%Y"),
            "Jour": WEEKDAYS_FR[end_of_month(month_start).weekday()],
            "Mois": f"{month_start.month:02d}/{month_start.year}",
            "Site": "⚠️ Heures non planifiées ce mois",
            "Heures": round(float(reste), 2)
        })

plan_df = pd.DataFrame(allocations)

# ---------- Affichage ----------
st.subheader("Résumé")
c1,c2,c3 = st.columns(3)
c1.metric("Mois couverts", f"{min_month.strftime('%m/%Y')} → {max_month.strftime('%m/%Y')}")
c2.metric("Total sites (mois distingués)", f"{len(agg)}")
c3.metric("Total heures estimées", f"{agg['Durée (h)'].sum():.1f} h")

st.subheader("Planning visuel par semaine (L→V)")
if plan_df.empty:
    st.info("Aucune allocation.")
else:
    plan_df["Date_dt"] = pd.to_datetime(plan_df["Date"], format="%d/%m/%Y")
    plan_df["Semaine"] = plan_df["Date_dt"].dt.isocalendar().week
    plan_df["Année"] = plan_df["Date_dt"].dt.isocalendar().year
    weeks = (plan_df.drop_duplicates(["Année","Semaine"])
                     [["Année","Semaine"]]
                     .sort_values(["Année","Semaine"])
                     .values.tolist())
    for (year, week) in weeks:
        sub = plan_df[(plan_df["Année"]==year) & (plan_df["Semaine"]==week)]
        if sub.empty:
            continue
        st.markdown(f"### Semaine {int(week)} — {int(year)}")
        grid = {d: [] for d in ["Lundi","Mardi","Mercredi","Jeudi","Vendredi"]}
        for _, r in sub.iterrows():
            if r["Jour"] in grid:
                label = f'{r["Date"]} — [{r["Mois"]}] {r["Site"]} ({r["Heures"]}h)'
                grid[r["Jour"]].append(label)
        cols = st.columns(5)
        for i, dayname in enumerate(["Lundi","Mardi","Mercredi","Jeudi","Vendredi"]):
            with cols[i]:
                st.markdown(f"**{dayname}**")
                if grid[dayname]:
                    for line in grid[dayname]:
                        st.write("• " + line)
                else:
                    st.caption("—")

# ---------- Exports ----------
st.subheader("Exports")
if not plan_df.empty:
    st.download_button(
        "📄 Télécharger planning (CSV)",
        data=plan_df[["Date","Jour","Mois","Site","Heures"]].to_csv(index=False).encode("utf-8"),
        file_name="planning.csv",
        mime="text/csv"
    )
st.download_button(
    "💾 Télécharger sites agrégés (CSV)",
    data=agg[["Site","Mois","Total équipements","Durée (h)"]].to_csv(index=False).encode("utf-8"),
    file_name="sites_agreges_par_mois.csv",
    mime="text/csv"
)
