import pandas as pd
import json
import os
import glob
from collections import Counter

'''
What it measures:
"How important a node/AS is for emissions impact", combining how often it appears in paths 
with the emissions of its respective country. At the PoP level:
- Count how many routes include that PoP (total_paths: SP paths + LE paths).
- Retrieve the average daily emissions intensity of the PoP's country/region on the chosen date (country_emissions_day).
- Multiply:
    criticality_day = (SP_paths + LE_paths) × country_emissions_day
    -> More traffic and/or a more carbon-intensive power grid => higher criticality.

Then at the AS level:
- Sum the criticality of all PoPs belonging to the same AS:
    AS_criticality_day = Sum (criticality_day of the PoPs).
- 0-100 normalization (for ranking):
    Divide each AS's value by the maximum across all AS and multiply by 100:
    criticality_index = (AS_criticality_day / max_AS_criticality_day) x 100.
'''

TARGET_DATE = "2023-10-10"
lengths = [1, 2, 3, 4, 5, 6]

emissions_dir    = r"energy_graphs\data"
iso_mapping_path = r"topology_map\data\iso.json"
geo_pop_path     = r"topology_map\data\geolocation_pop.json"
sp_le_base_dir   = r"data\server\csvs"

out_as_csv = r"data\data\as_criticality_from_pops.csv"

COUNT_UNIQUE_PER_PATH = True   # True: counts every PoP once per path. False: every PoP occurence

def parse_token(token: str):
    token = str(token).strip()
    parts = token.split("-")
    try:
        asn = int(parts[0])
    except:
        return None, None, None, None
    if len(parts) >= 3:
        cc = parts[1].strip()
        reg = parts[2].strip()
        pop_key = f"{asn}-{cc}-{reg}"
        return asn, pop_key, cc, reg
    return asn, str(asn), None, None

def extract_pop_nodes(path: str):
    if not isinstance(path, str) or not path:
        return []
    nodes = []
    for seg in path.split("->"):
        asn, pop_key, _, _ = parse_token(seg)
        if asn is not None and pop_key is not None:
            nodes.append((asn, pop_key))
    return list(set(nodes)) if COUNT_UNIQUE_PER_PATH else nodes

def build_iso_lookup(iso_mapping_path):
    with open(iso_mapping_path, "r", encoding="utf-8") as f:
        iso_data = json.load(f)
    return iso_data

def load_pop_geo(geo_pop_path):
    with open(geo_pop_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    pop_to_names = {}      # "AS-CC-REG" -> (country_name, region_name)
    as_to_country = {}     # ASN -> default country_name
    as_to_region  = {}     # ASN -> default region_name

    for entry in data:
        try:
            asn = int(entry.get("as_number"))
        except:
            continue
        country_name = entry.get("country_name") or entry.get("country", "Unknown")
        region_name  = entry.get("region_name")  or entry.get("region",  country_name)
        as_to_country[asn] = country_name
        as_to_region[asn]  = region_name

        pop_cc  = entry.get("pop_cc") or entry.get("cc")
        pop_reg = entry.get("pop_region") or entry.get("reg")
        if pop_cc and pop_reg:
            pop_key = f"{asn}-{str(pop_cc).strip()}-{str(pop_reg).strip()}"
            pop_to_names[pop_key] = (country_name, region_name)

    return pop_to_names, as_to_country, as_to_region


iso_mapping = build_iso_lookup(iso_mapping_path) 
pop_to_names, as_to_country_default, as_to_region_default = load_pop_geo(geo_pop_path)

available_iso = {
    os.path.basename(p).split("_")[0]
    for p in glob.glob(os.path.join(emissions_dir, "*_2023_hourly.csv"))
}

def resolve_iso(country_name: str, region_name: str):
    """
    Regole:
      1) Prova REGION: key = 'COUNTRY-REGION' (upper)
      2) Fallback COUNTRY (upper)
      3) In entrambi i casi, accetta solo se esiste il CSV di emissioni
    Ritorna (iso_code, reason_if_none)
    """
    country = (country_name or "").strip().upper()
    region  = (region_name or "").strip().upper()

    if region:
        region_key = f"{country}-{region}"
        if region_key in iso_mapping.get("regions", {}):
            iso_code = iso_mapping["regions"][region_key].get("iso_code")
            if iso_code in available_iso:
                return iso_code, None
            else:
                return None, f"file emissioni assente per ISO regionale '{iso_code}' (key '{region_key}')"
            
    if country in iso_mapping.get("countries", {}):
        iso_code = iso_mapping["countries"][country].get("iso_code")
        if iso_code in available_iso:
            return iso_code, None
        else:
            return None, f"file emissioni assente per ISO paese '{iso_code}' (country '{country}')"

    if region:
        return None, f"nessun mapping ISO per '{country}-{region}' né per country '{country}'"
    return None, f"nessun mapping ISO per country '{country}'"

pop_counter_SP = Counter()
pop_counter_LE = Counter()

for length in lengths:
    file_LE_1 = fr"data\server\csvs\edges_LE_glo_jan-jun_2_{length}.csv"
    file_LE_2 = fr"data\server\csvs\edges_glo_LE_jul-dec_len{length}.csv"
    file_SP_1 = fr"data\server\csvs\edges_SP_glo_jan-jun_2_{length}.csv"
    file_SP_2 = fr"data\server\csvs\edges_glo_SP_jul-dec_len{length}.csv"

    df_SP = pd.concat([pd.read_csv(file_SP_1), pd.read_csv(file_SP_2)], ignore_index=True)
    df_LE = pd.concat([pd.read_csv(file_LE_1), pd.read_csv(file_LE_2)], ignore_index=True)

    for path in df_SP["emissions_path"].dropna():
        pop_counter_SP.update(extract_pop_nodes(path))
    for path in df_LE["emissions_path"].dropna():
        pop_counter_LE.update(extract_pop_nodes(path))

def counter_to_df(cntr, col_name):
    rows = []
    for (asn, pop_key), cnt in cntr.items():
        rows.append({"AS": int(asn), "pop_key": str(pop_key), col_name: int(cnt)})
    return pd.DataFrame(rows)

df_pop_SP = counter_to_df(pop_counter_SP, "SP_paths")
df_pop_LE = counter_to_df(pop_counter_LE, "LE_paths")
df_pops = pd.merge(df_pop_SP, df_pop_LE, on=["AS", "pop_key"], how="outer").fillna(0)
df_pops["SP_paths"] = df_pops["SP_paths"].astype(int)
df_pops["LE_paths"] = df_pops["LE_paths"].astype(int)
df_pops["total_paths"] = df_pops["SP_paths"] + df_pops["LE_paths"]

countries, regions, isos = [], [], []
rows_to_keep = []
skipped = 0

for i, row in df_pops.iterrows():
    asn = row["AS"]; pop_key = row["pop_key"]

    if pop_key in pop_to_names:
        country_name, region_name = pop_to_names[pop_key]
    else:
        country_name = as_to_country_default.get(asn, "Unknown")
        region_name  = as_to_region_default.get(asn, country_name)

    iso_code, reason = resolve_iso(country_name, region_name)
    if not iso_code:
        skipped += 1
        print(f"[SKIP] PoP {pop_key} (AS {asn}) — {reason}")
        continue

    countries.append(country_name)
    regions.append(region_name)
    isos.append(iso_code)
    rows_to_keep.append(i)

df_pops = df_pops.loc[rows_to_keep].copy()
df_pops["country"] = countries
df_pops["region"] = regions
df_pops["iso_code"] = isos

print(f"PoP totali: {len(pop_counter_SP)+len(pop_counter_LE)} | PoP con dati emissioni: {len(df_pops)} | Skippati: {skipped}")

iso_to_emissions_day = {}
for file in glob.glob(os.path.join(emissions_dir, "*_2023_hourly.csv")):
    iso_code = os.path.basename(file).split("_")[0]
    try:
        df_em = pd.read_csv(file)
        if "Datetime (UTC)" not in df_em.columns:
            continue
        df_em["Datetime (UTC)"] = pd.to_datetime(df_em["Datetime (UTC)"], errors="coerce")
        df_day = df_em[df_em["Datetime (UTC)"].dt.date == pd.to_datetime(TARGET_DATE).date()]
        if df_day.empty:
            continue
        candidates = [c for c in df_em.columns if c.lower().strip() in {
            "carbon intensity gco₂eq/kwh (direct)",
            "carbon intensity gco2eq/kwh (direct)",
        }]
        if not candidates:
            continue
        emissions_col = candidates[0]
        iso_to_emissions_day[iso_code] = float(df_day[emissions_col].mean())
    except Exception:
        continue

df_pops["country_emissions_day"] = df_pops["iso_code"].map(iso_to_emissions_day).fillna(0.0)

df_pops["criticality_day"]    = df_pops["total_paths"] * df_pops["country_emissions_day"]    # totale
df_pops["criticality_day_SP"] = df_pops["SP_paths"]    * df_pops["country_emissions_day"]    # SOLO SP
df_pops["criticality_day_LE"] = df_pops["LE_paths"]    * df_pops["country_emissions_day"]    # SOLO LE

agg_dict = {
    "SP_paths": "sum",
    "LE_paths": "sum",
    "total_paths": "sum",
    "criticality_day": "sum",
    "criticality_day_SP": "sum",
    "criticality_day_LE": "sum",
}
df_as = df_pops.groupby("AS", as_index=False).agg(agg_dict)

max_tot = df_as["criticality_day"].max()
df_as["criticality_norm"]  = 0.0 if max_tot == 0 else (df_as["criticality_day"] / max_tot)
df_as["criticality_index"] = df_as["criticality_norm"] * 100.0

max_sp = df_as["criticality_day_SP"].max()
max_le = df_as["criticality_day_LE"].max()
df_as["criticality_index_SP"] = 0.0 if max_sp == 0 else (df_as["criticality_day_SP"] / max_sp) * 100.0
df_as["criticality_index_LE"] = 0.0 if max_le == 0 else (df_as["criticality_day_LE"] / max_le) * 100.0

def dominant_geo(sub):
    s = sub.sort_values("total_paths", ascending=False).iloc[0]
    return pd.Series({"country": s["country"], "region": s["region"], "iso_code": s["iso_code"]})

geo_dom = df_pops.groupby("AS").apply(dominant_geo).reset_index()
df_as = df_as.merge(geo_dom, on="AS", how="left")

df_as.sort_values("criticality_index", ascending=False).to_csv(out_as_csv, index=False)
print(f"Saved AS-level criticality (from PoPs) -> {out_as_csv}")