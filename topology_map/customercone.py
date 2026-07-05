from collections import defaultdict, deque, Counter
from networkx_graph import ASGraph
import json
import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def build_p2c_from_pop_graph(G):
    """Collapse PoP-level edges into AS-level provider->customer adjacency (p2c only)."""
    prov2cust = defaultdict(set)

    for u, v, ed in G.edges(data=True):
        if ed.get("relationship") != "p2c":
            continue

        prov_as = str(G.nodes[u].get("as_number", "")).strip()
        cust_as = str(G.nodes[v].get("as_number", "")).strip()

        if prov_as and cust_as and prov_as != cust_as:
            prov2cust[prov_as].add(cust_as)

    return prov2cust


def cone_size(asn: str, prov2cust) -> int:
    """Cone size within the PoP-covered subgraph: self + all reachable customers via p2c."""
    asn = str(asn).strip()
    seen = set()
    q = deque([asn])

    while q:
        u = q.popleft()
        for v in prov2cust.get(u, ()):
            if v not in seen:
                seen.add(v)
                q.append(v)

    return len(seen) + 1  # include self


def compute_cone_sizes_from_pop_graph(G):
    prov2cust = build_p2c_from_pop_graph(G)

    asns_in_graph = {
        str(attrs.get("as_number")).strip()
        for _, attrs in G.nodes(data=True)
        if attrs.get("as_number") is not None
    }

    cone_sizes = {asn: cone_size(asn, prov2cust) for asn in asns_in_graph}
    return cone_sizes, prov2cust

def iso_year_mean_ci(emissions_dir: str) -> dict:
    """
    Compute annual mean carbon intensity per ISO zone from *_2023_hourly.csv.
    Returns: iso2mean[ISO] = mean(gCO2/kWh)
    """
    iso2mean = {}

    candidates = {
        "carbon intensity gco₂eq/kwh (direct)",
        "carbon intensity gco2eq/kwh (direct)",
        "carbon intensity gco2/kwh (direct)",
        "carbon_intensity_gco2eq_per_kwh",
    }

    for fp in glob.glob(os.path.join(emissions_dir, "*_2023_hourly.csv")):
        iso = os.path.basename(fp).split("_")[0]
        df = pd.read_csv(fp)
        df.columns = df.columns.str.lower().str.strip()

        ci_col = None
        for c in df.columns:
            if c in candidates:
                ci_col = c
                break
        if ci_col is None:
            continue

        vals = pd.to_numeric(df[ci_col], errors="coerce").dropna()
        if len(vals) == 0:
            continue

        iso2mean[iso] = float(vals.mean())

    return iso2mean


def as_level_ci(G, iso2mean):
    """
    Estimate per-AS carbon intensity by:
    ISO annual mean -> assign to PoPs -> average across PoPs per AS.
    Returns: as_ci[asn] = mean(gCO2/kWh)
    """
    as2vals = defaultdict(list)

    for _, attrs in G.nodes(data=True):
        asn = str(attrs.get("as_number", "")).strip()
        iso = str(attrs.get("iso", "")).strip()
        if not asn or not iso:
            continue

        ci = iso2mean.get(iso)
        if ci is None or not np.isfinite(ci):
            continue

        as2vals[asn].append(ci)

    as_ci = {asn: float(np.mean(vals)) for asn, vals in as2vals.items() if vals}
    return as_ci

def cone_mean_ci(root_asn: str, prov2cust, as_ci: dict):
    """Mean CO2 intensity across ASes in the cone (root included)."""
    root_asn = str(root_asn).strip()
    seen = {root_asn}
    q = deque([root_asn])

    total = 0.0
    cnt = 0

    while q:
        u = q.popleft()

        val = as_ci.get(u)
        if val is not None and np.isfinite(val):
            total += float(val)
            cnt += 1

        for v in prov2cust.get(u, ()):
            v = str(v).strip()
            if v not in seen:
                seen.add(v)
                q.append(v)

    cone_sz = len(seen)
    return (total / cnt) if cnt else np.nan, cone_sz, cnt


def cone_total_score(root_asn: str, prov2cust, as_ci: dict, w: dict):
    """
    Usage-weighted 'total cone CO2 score':
      score = sum_{AS in cone} CI_AS * w(AS)
    Also returns wsum to allow weighted mean:
      cone_ci_weighted = score / wsum
    """
    root_asn = str(root_asn).strip()
    seen = {root_asn}
    q = deque([root_asn])

    score = 0.0
    wsum = 0.0

    while q:
        u = q.popleft()

        ci = as_ci.get(u)
        wu = w.get(u, 0)

        if ci is not None and np.isfinite(ci) and wu > 0:
            score += float(ci) * float(wu)
            wsum += float(wu)

        for v in prov2cust.get(u, ()):
            v = str(v).strip()
            if v not in seen:
                seen.add(v)
                q.append(v)

    return score, len(seen), wsum

def path_to_as_seq(path_str: str):
    """
    Convert: '34262-HU- -> 5588-HU-BU -> ... -> 16055-AT-'
    to AS-seq: ['34262','5588',...,'16055'], compressing consecutive duplicates.
    """
    toks = [t.strip() for t in str(path_str).split("->") if t.strip()]
    asns = []
    for t in toks:
        asn = t.split("-")[0].strip()
        if asn:
            asns.append(asn)

    out = []
    for a in asns:
        if not out or out[-1] != a:
            out.append(a)
    return out


def update_counts_from_file(counter: Counter, filepath: str,
                            path_col="emissions_path",
                            mode="transit",
                            chunksize=200000):
    """
    mode='transit' -> count only internal ASes (exclude first and last)
    mode='all'     -> count all ASes in the path
    """
    if not os.path.exists(filepath):
        print(f"⚠️ missing file: {filepath}")
        return

    for chunk in pd.read_csv(filepath, chunksize=chunksize):
        chunk.columns = chunk.columns.str.lower().str.strip()
        col = path_col.lower()
        if col not in chunk.columns:
            raise ValueError(f"Column '{path_col}' not found in {filepath}")

        for s in chunk[col].dropna():
            seq = path_to_as_seq(s)
            if len(seq) < 2:
                continue

            if mode == "transit":
                for a in seq[1:-1]:
                    counter[a] += 1
            elif mode == "all":
                for a in seq:
                    counter[a] += 1
            else:
                raise ValueError("mode must be 'transit' or 'all'")


def compute_usage_weights(lengths, base_csv_dir, mode="transit"):
    """
    Computes w_sp and w_le from your four files per length.
    Returns: (w_sp:dict, w_le:dict, w_all:dict)
    """
    w_sp = Counter()
    w_le = Counter()

    for length in lengths:
        file_LE_1 = os.path.join(base_csv_dir, f"edges_LE_glo_jan-jun_2_{length}.csv")
        file_LE_2 = os.path.join(base_csv_dir, f"edges_glo_LE_jul-dec_len{length}.csv")
        file_SP_1 = os.path.join(base_csv_dir, f"edges_SP_glo_jan-jun_2_{length}.csv")
        file_SP_2 = os.path.join(base_csv_dir, f"edges_glo_SP_jul-dec_len{length}.csv")

        update_counts_from_file(w_le, file_LE_1, mode=mode)
        update_counts_from_file(w_le, file_LE_2, mode=mode)
        update_counts_from_file(w_sp, file_SP_1, mode=mode)
        update_counts_from_file(w_sp, file_SP_2, mode=mode)

        print(f"✔ done length {length}")

    #w_all = Counter(w_sp) + Counter(w_le)
    w_all = Counter (w_sp) # SOLO LE OCCURENCES DEL SP
    return dict(w_sp), dict(w_le), dict(w_all)

def plot_cone_scatter(df, x_col, y_col, out_path, title=None, y_label=None,
                      dot_color="black", line_color="blue", ylim=None):
    d = df[[x_col, y_col]].dropna()
    d = d[(d[x_col] > 0) & (d[y_col] > 0)]

    x = d[x_col].to_numpy(dtype=float)
    y = d[y_col].to_numpy(dtype=float)

    lx = np.log10(x)
    ly = np.log10(y)
    m, b = np.polyfit(lx, ly, 1)

    x_line = np.logspace(lx.min(), lx.max(), 200)
    y_line = 10 ** (m * np.log10(x_line) + b)

    plt.figure(figsize=(12, 7))
    plt.scatter(x, y, s=8, alpha=0.35, color=dot_color)
    plt.plot(x_line, y_line, color=line_color, linewidth=2)

    if ylim is not None:
        plt.ylim(ylim[0], ylim[1])

    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("Customer Cone Size")
    plt.ylabel(y_label if y_label else y_col)
    if title:
        plt.title(title)

    plt.grid(True, which="both", linestyle="--", linewidth=0.7, alpha=0.4)
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()

    print(f"Saved: {out_path}")
    print(f"log-log fit: log10(y) = {m:.3f} * log10(x) + {b:.3f}")

if __name__ == "__main__":
    
    lengths = [1, 2, 3, 4, 5, 6]

    base_csv_dir = r"data\server\csvs"
    geo_json_path = r"topology_map\data\geolocation_pop.json"
    iso_mapping_path = r"topology_map\data\iso.json"
    emissions_folder_path = r"energy_graphs\data"
    relationships_file = r"data\topology_data\20240101.as-rel2.txt"

    out_dir = r"topology_map\plots\customercone"
    os.makedirs(out_dir, exist_ok=True)

    with open(r"topology_map\data\countries.txt", "r", encoding="utf-8") as file:
        content = file.read()
    countries = [c.strip().strip('"') for c in content.split(",") if c.strip()]

    with open(geo_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        as_to_country = {entry["pop"]: entry.get("country", "") for entry in data}
        as_to_region  = {entry["pop"]: entry.get("region", "") for entry in data}

    graph = ASGraph(
        data_file=geo_json_path,
        relationships_file=relationships_file,
        emissions_folder_path=emissions_folder_path,
        countries=countries,
        iso_mapping_file=iso_mapping_path,
        as_to_country=as_to_country,
        as_to_region=as_to_region,
        as_to_iso_code={}
    )
    graph.add_nodes()
    graph.add_edges()

    print(f"Graph has {graph.graph.number_of_nodes()} nodes and {graph.graph.number_of_edges()} edges")

    cone_sizes, prov2cust = compute_cone_sizes_from_pop_graph(graph.graph)
    print("ASNs in graph:", len(cone_sizes))
    print("Example cone sizes:", list(cone_sizes.items())[:5])

    top_cones = sorted(cone_sizes.items(), key=lambda kv: kv[1], reverse=True)[:10]
    print("Top ASes by cone size:")
    for asn, size in top_cones:
        print(asn, size)

    iso2mean = iso_year_mean_ci(emissions_folder_path)
    as_ci = as_level_ci(graph.graph, iso2mean)

    w_sp, w_le, w_all = compute_usage_weights(lengths, base_csv_dir, mode="transit")
    print(f"Usage weights: |SP|={len(w_sp)} |LE|={len(w_le)} |ALL|={len(w_all)}")

    asns = set(as_ci.keys()) | set(prov2cust.keys())

    rows_ci = []
    for asn in asns:
        cone_ci, cone_sz, n_valid = cone_mean_ci(asn, prov2cust, as_ci)
        rows_ci.append({"asn": asn, "cone_size": cone_sz, "cone_ci": cone_ci, "n_valid_ci": n_valid})
    df_ci = pd.DataFrame(rows_ci)

    rows_score = []
    for asn in asns:
        score, cone_sz, wsum = cone_total_score(asn, prov2cust, as_ci, w_all)
        rows_score.append({
            "asn": asn,
            "cone_size": cone_sz,
            "cone_score": score,  # gCO2/kWh * occurrences
            "cone_ci_weighted": (score / wsum) if wsum > 0 else np.nan,
            "wsum": wsum
        })
    df_score = pd.DataFrame(rows_score)
   

    plot_cone_scatter(
        df_ci,
        x_col="cone_size",
        y_col="cone_ci",
        out_path=os.path.join(out_dir, "cone_ci_vs_cone_size.png"),
        title="CO₂ intensity aggregated over each AS customer cone vs cone size",
        y_label="Mean CO₂ intensity in cone (gCO₂/kWh)",
        dot_color="black",
        line_color="blue",
        ylim=(1e-1, 1e4)
    )
''' 
    plot_cone_scatter(
        df_score,
        x_col="cone_size",
        y_col="cone_score",
        out_path=os.path.join(out_dir, "cone_score_vs_cone_size.png"),
        title="Usage-weighted cone CO₂ score vs cone size",
        y_label="Cone CO₂ score (gCO₂/kWh × path-occurrences)",
        dot_color="black",
        line_color="blue"
    )
    
    plot_cone_scatter(
        df_score,
        x_col="cone_size",
        y_col="cone_ci_weighted",
        out_path=os.path.join(out_dir, "cone_ci_weighted_vs_cone_size.png"),
        title="Usage-weighted mean CO₂ intensity in cone vs cone size",
        y_label="Usage-weighted mean CO₂ intensity in cone (gCO₂/kWh)",
        dot_color="black",
        line_color="blue",
        ylim=(1e-1, 1e4)
    )
    '''

    
