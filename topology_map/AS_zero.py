import os
import json
import math
import pandas as pd
from datetime import datetime
from functools import lru_cache
from typing import Optional

#ASNS_TO_ZERO = {3356, 7922, 3257, 174, 209, 701, 4766, 20940, 3320, 4134, 7018, 4837, 4826} # primi 13 con criticality sopra il 10%
ASNS_TO_ZERO = {3356, 7922, 3257, 174, 209, 701, 4766, 20940, 3320, 4134, 7018, 4837, 4826,
                3216, 17676, 8075, 1239, 5617, 20115, 8151, 12389, 3491, 2914, 3786, 4780, 
                22773, 3549, 3462, 749, 1221} # primi 27 con criticality sopra il 5%
#ASNS_TO_ZERO = {1299, 3356, 174, 7922, 3257, 209, 2914, 701, 7018, 4766, 20940, 3320, 5511}   # count > 100k
#ASNS_TO_ZERO = {1299, 3356, 174, 7922, 3257, 209, 2914, 701, 7018, 4766,
#                20940, 3320, 5511, 4134, 4837, 1239, 17676, 3216, 4826, 8151}   # count > 50k
SUBTRACT_EACH_POP_OCCURRENCE = True          # False = subtract at most once per ASN per row

POPS_JSON = r"topology_map\data\geolocation_pop.json"
ISO_MAPPING_JSON = r"topology_map\data\iso.json"
EMISSIONS_FOLDER = r"energy_graphs\data"  

lengths = [1, 2, 3, 4, 5, 6]
file_templates = [
    r"data\server\csvs\edges_LE_glo_jan-jun_2_{length}.csv",
    r"data\server\csvs\edges_glo_LE_jul-dec_len{length}.csv",
    r"data\server\csvs\edges_SP_glo_jan-jun_2_{length}.csv",
    r"data\server\csvs\edges_glo_SP_jul-dec_len{length}.csv",
]

def parse_date_to_iso(d):
    s = str(d)
    if "-" in s and len(s) >= 10:
        return s[:10]
    dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
    if pd.isna(dt):
        dt = pd.to_datetime(s, dayfirst=False, errors="raise")
    return dt.strftime("%Y-%m-%d")

def hour2(h):
    try:
        return str(int(h)).zfill(2)
    except Exception:
        return str(h).zfill(2)

def pop_asn(pop: str):
    if not isinstance(pop, str) or "-" not in pop:
        return None
    head = pop.split("-", 1)[0]
    try:
        return int(head)
    except Exception:
        return None

def finite(x):
    return isinstance(x, (int, float)) and not math.isnan(x) and not math.isinf(x)

def load_json_any_utf(path):
    last_err = None
    for enc in ("utf-8", "utf-8-sig"):
        try:
            with open(path, "r", encoding=enc) as f:
                return json.load(f)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Could not decode {path}: {last_err}")

def iso_for_pop(entry, iso_map):
    country = (entry.get("country") or "").strip().upper()
    region  = (entry.get("region")  or "").strip().upper()
    region_key = f"{country}-{region}" if region else None
    if region_key and region_key in iso_map.get("regions", {}):
        return iso_map["regions"][region_key]["iso_code"]
    if country in iso_map.get("countries", {}):
        return iso_map["countries"][country]["iso_code"]
    return None

def build_pop_maps(pops_json, iso_map):
    pops = load_json_any_utf(pops_json)
    pop_to_asn, pop_to_iso = {}, {}
    for e in pops:
        pop = e.get("pop")
        asn = e.get("as_number")
        if not pop or asn is None:
            continue
        iso_code = iso_for_pop(e, iso_map)
        if iso_code is None:
            continue
        pop_to_asn[pop] = int(asn)
        pop_to_iso[pop] = iso_code
    return pop_to_asn, pop_to_iso

def derive_iso_from_token(pop_token: str, iso_map: dict) -> Optional[str]:
    if not isinstance(pop_token, str) or "-" not in pop_token:
        return None
    parts = [p.strip().upper() for p in pop_token.split("-")]
    if len(parts) < 2:
        return None
    country = parts[1]
    region = parts[2] if len(parts) >= 3 and parts[2] else None
    if region:
        rk = f"{country}-{region}"
        if rk in iso_map.get("regions", {}):
            return iso_map["regions"][rk]["iso_code"]
    if country in iso_map.get("countries", {}):
        return iso_map["countries"][country]["iso_code"]
    return None

@lru_cache(maxsize=None)
def load_iso_df(iso_code: str):
    filename = f"{iso_code}_2023_hourly.csv"
    path = os.path.join(EMISSIONS_FOLDER, filename)
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df.columns = df.columns.str.lower().str.strip()
    ts_col = "datetime (utc)"
    val_col = "carbon intensity gco₂eq/kwh (direct)"
    if ts_col not in df.columns or val_col not in df.columns:
        return None
    df[ts_col] = pd.to_datetime(df[ts_col], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
    df = df.dropna(subset=[ts_col]).set_index(ts_col)
    return df

def get_country_emissions(datetime_str: str, iso_code: str) -> float:
    df = load_iso_df(iso_code)
    if df is None:
        return float("inf")
    val_col = "carbon intensity gco₂eq/kwh (direct)"
    dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
    try:
        v = df.at[pd.Timestamp(dt), val_col]
        if pd.notna(v) and finite(float(v)):
            return float(v)
    except KeyError:
        pass
    same_day = df.loc[df.index.date == dt.date(), val_col]
    if not same_day.empty:
        m = pd.to_numeric(same_day, errors="coerce").mean()
        if pd.notna(m) and finite(float(m)):
            return float(m)
    return float("inf")

# -----------------------------
# Core processing
# -----------------------------
def process_file(in_path: str, pop_to_asn, pop_to_iso, asn_targets, iso_map, subtract_each=True):
    if not os.path.exists(in_path):
        print(f"[skip] {in_path} (not found)")
        return None
    print(f"[read] {in_path}")
    df = pd.read_csv(in_path)

    required = {"date","hour","emissions_total","emissions_path"}
    if not required.issubset(df.columns):
        missing = ", ".join(sorted(required - set(df.columns)))
        raise ValueError(f"{os.path.basename(in_path)} is missing columns: {missing}")

    df["date_iso"] = df["date"].apply(parse_date_to_iso)
    df["hour2"] = df["hour"].apply(hour2)
    df["timestamp_utc"] = df["date_iso"] + " " + df["hour2"] + ":00:00"

    subtract_vals, matched_asns_col, missing_col = [], [], []

    # debug counters
    fallback_hits = 0
    missing_iso_after_fallback = 0
    inf_intensity_hits = 0

    for _, row in df.iterrows():
        path_str = str(row.get("emissions_path") or "")
        ts = row["timestamp_utc"]

        to_subtract = 0.0
        matched_asns = set()
        missing_data = False

        if path_str.strip():
            tokens_full  = [t.strip().rstrip("-") for t in path_str.split("->") if t.strip()]
            edge_sources = tokens_full[:-1] 
            target_only_asns = set()
            if tokens_full:
                last_asn = pop_to_asn.get(tokens_full[-1], pop_asn(tokens_full[-1]))
                if last_asn in asn_targets:
                    target_only_asns.add(last_asn)

            pops, seen_asn = [], set()
            for token in edge_sources:
                asn = pop_to_asn.get(token, pop_asn(token))
                if asn is None:
                    continue
                if asn in asn_targets:
                    if subtract_each or asn not in seen_asn:
                        pops.append(token)
                        seen_asn.add(asn)
                        matched_asns.add(asn)

            for pop in pops:
                iso = derive_iso_from_token(pop, iso_map) or pop_to_iso.get(pop)
                if not iso:
                    missing_data = True
                    continue
                val = get_country_emissions(ts, iso)
                if finite(val):
                    to_subtract += float(val)
                else:
                    missing_data = True


        subtract_vals.append(to_subtract)
        matched_asns_col.append(",".join(map(str, sorted(matched_asns))) if matched_asns else "")
        missing_col.append(missing_data)

    df["matched_asns"] = matched_asns_col
    df["subtracted_emissions"] = subtract_vals
    df["emissions_total_adjusted"] = df["emissions_total"].astype(float) - df["subtracted_emissions"].astype(float)
    df["missing_pop_or_iso"] = missing_col


    out_path = os.path.splitext(in_path)[0] + "_crit5.csv"
    df.to_csv(out_path, index=False)
    print(f"[write] {out_path}  (rows: {len(df)})")
    print(f"  fallback ISO hits: {fallback_hits} | missing ISO after fallback: {missing_iso_after_fallback} | inf intensity: {inf_intensity_hits}")
    return out_path

def main():
    iso_map = load_json_any_utf(ISO_MAPPING_JSON)
    pop_to_asn, pop_to_iso = build_pop_maps(POPS_JSON, iso_map)
    asn_targets = {int(a) for a in ASNS_TO_ZERO}

    from collections import Counter
    import pandas as pd
    import os

    isos_seen = Counter()

    def preview_isos(file_path):
        df_tmp = pd.read_csv(file_path)
        if not {"date","hour","emissions_path"}.issubset(df_tmp.columns):
            return
        # build timestamps like your main code
        df_tmp["date_iso"] = pd.to_datetime(df_tmp["date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
        df_tmp["hour2"] = pd.to_numeric(df_tmp["hour"], errors="coerce").fillna(0).astype(int).astype(str).str.zfill(2)
        df_tmp["timestamp_utc"] = df_tmp["date_iso"] + " " + df_tmp["hour2"] + ":00:00"

        for path in df_tmp["emissions_path"].dropna().astype(str):
            tokens = [t.strip().rstrip("-") for t in path.split("->") if t.strip()]
            for token in tokens:
                asn = pop_to_asn.get(token) or pop_asn(token)
                if asn in asn_targets:
                    iso = pop_to_iso.get(token) or derive_iso_from_token(token, iso_map)
                    if iso:
                        isos_seen[iso] += 1

    for length in [2]:
        for tmpl in file_templates:
            p = tmpl.format(length=length)
            if os.path.exists(p):
                preview_isos(p)


    missing_files = []
    weird_cols   = []
    for iso, _ in isos_seen.items():
        fp = os.path.join(EMISSIONS_FOLDER, f"{iso}_2023_hourly.csv")
        if not os.path.exists(fp):
            missing_files.append((iso, fp))
        else:
            hdr = pd.read_csv(fp, nrows=1).columns
            ok_ts = any(c.lower().strip() == "datetime (utc)" for c in hdr)
            ok_co2 = any(("carbon intensity" in c.lower() and "gco" in c.lower()) for c in hdr)
            if not (ok_ts and ok_co2):
                weird_cols.append((iso, list(hdr)))

    outputs = []
    for length in lengths:
        for tmpl in file_templates:
            path = tmpl.format(length=length)
            outp = process_file(
                path, pop_to_asn, pop_to_iso, asn_targets, iso_map,
                subtract_each=SUBTRACT_EACH_POP_OCCURRENCE
            )
            if outp:
                outputs.append(outp)

    print("\nDone. Adjusted files:")
    for p in outputs:
        print(" -", p)

if __name__ == "__main__":
    main()
