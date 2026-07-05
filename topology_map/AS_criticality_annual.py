import pandas as pd
import json
import os
import glob
from collections import Counter

'''
What it measures:
"How important a node/AS is for emissions impact" → how often it appears in paths × Carbon Intensity.
At the PoP level:

Count how many paths include that PoP (total_paths: SP paths + LE paths).
Retrieve the average annual emissions intensity of the PoP's country/region.
Multiply:
criticality = (SP_paths + LE_paths) × country_emissions
→ More traffic and/or a more carbon-intensive power grid ⇒ higher criticality.

Then at the AS level:

Sum the criticality of all PoPs belonging to the same AS:
AS_criticality = Σ (criticality of the PoPs).
0–100 normalization (for ranking, if enabled):
criticality_index = (AS_criticality / max_AS_criticality) × 100.
'''

lengths = [1, 2, 3, 4, 5, 6]

emissions_dir    = r"energy_graphs\data"
iso_mapping_path = r"topology_map\data\iso.json"
geo_pop_path     = r"topology_map\data\geolocation_pop.json"
sp_le_base_dir   = r"data\server\csvs"

out_as_csv = r"data\data\as_criticality_from_pops.csv"

COUNT_UNIQUE_PER_PATH = True    # True: count each PoP only once per path. False: count every occurrence.
USE_ANNUAL_MEAN       = True    # True: 2023 annual mean
NORMALIZE_CRITICALITY = True    # True: compute and populate the 0-100 indices


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

# Count PoP appearances in SP & LE
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

# PoP table
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

# Map PoP -> (country, region) -> ISO con fallback + check file
countries, regions, isos = [], [], []
rows_to_keep = []
skipped = 0

for i, row in df_pops.iterrows():
    asn = row["AS"]
    pop_key = row["pop_key"]

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

iso_to_emissions_value = {}

for file in glob.glob(os.path.join(emissions_dir, "*_2023_hourly.csv")):
    iso_code = os.path.basename(file).split("_")[0]
    try:
        df_em = pd.read_csv(file)
        if "Datetime (UTC)" not in df_em.columns:
            continue
        df_em["Datetime (UTC)"] = pd.to_datetime(df_em["Datetime (UTC)"], errors="coerce")

        candidates = [c for c in df_em.columns if c.lower().strip() in {
            "carbon intensity gco₂eq/kwh (direct)",
            "carbon intensity gco2eq/kwh (direct)",
            "carbon intensity gco2/kwh (direct)",
            "carbon_intensity_gco2eq_per_kwh"
        }]
        if not candidates:
            continue
        emissions_col = candidates[0]

        if USE_ANNUAL_MEAN:
            iso_to_emissions_value[iso_code] = float(df_em[emissions_col].dropna().mean())
    except Exception:
        continue


df_pops["country_emissions"] = df_pops["iso_code"].map(iso_to_emissions_value).fillna(0.0)


df_pops["criticality_raw"]    = df_pops["total_paths"] * df_pops["country_emissions"]  # totale
df_pops["criticality_raw_SP"] = df_pops["SP_paths"]    * df_pops["country_emissions"]  # SOLO SP
df_pops["criticality_raw_LE"] = df_pops["LE_paths"]    * df_pops["country_emissions"]  # SOLO LE


agg_dict = {
    "SP_paths": "sum",
    "LE_paths": "sum",
    "total_paths": "sum",
    "criticality_raw": "sum",
    "criticality_raw_SP": "sum",
    "criticality_raw_LE": "sum",
}
df_as = df_pops.groupby("AS", as_index=False).agg(agg_dict)

df_as.rename(columns={
    "criticality_raw":    "criticality_annual",
    "criticality_raw_SP": "criticality_annual_SP",
    "criticality_raw_LE": "criticality_annual_LE",
}, inplace=True)


if NORMALIZE_CRITICALITY:
    max_tot = df_as["criticality_annual"].max()
    if max_tot == 0:
        df_as["criticality_norm"]  = 0.0
        df_as["criticality_index"] = 0.0
    else:
        df_as["criticality_norm"]  = df_as["criticality_annual"] / max_tot
        df_as["criticality_index"] = df_as["criticality_norm"] * 100.0  

    
    max_sp = df_as["criticality_annual_SP"].max()
    max_le = df_as["criticality_annual_LE"].max()

    df_as["criticality_index_SP"] = 0.0 if max_sp == 0 else (df_as["criticality_annual_SP"] / max_sp) * 100.0
    df_as["criticality_index_LE"] = 0.0 if max_le == 0 else (df_as["criticality_annual_LE"] / max_le) * 100.0
else:
    df_as["criticality_norm"]       = 0.0
    df_as["criticality_index"]      = 0.0
    df_as["criticality_index_SP"]   = 0.0
    df_as["criticality_index_LE"]   = 0.0

def dominant_geo(sub):
    s = sub.sort_values("total_paths", ascending=False).iloc[0]
    return pd.Series({"country": s["country"], "region": s["region"], "iso_code": s["iso_code"]})


geo_dom = df_pops.groupby("AS").apply(dominant_geo).reset_index()
df_as = df_as.merge(geo_dom, on="AS", how="left")

sort_col = "criticality_index" if NORMALIZE_CRITICALITY else "criticality_annual"
df_as.sort_values(sort_col, ascending=False).to_csv(out_as_csv, index=False)
print(f"Saved AS-level criticality (from PoPs) -> {out_as_csv}")
