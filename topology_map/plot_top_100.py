import pandas as pd
import json
import os
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap
import networkx as nx

TOP_K = 100
LENGTHS = [1,2,3,4,5,6]
TARGET_DATETIME = pd.to_datetime("2023-07-10 12:00:00")

geo_json_path = r"topology_map\data\geolocation_pop.json"
output_dir = r"topology_map\plots\geo_pop_paths_per_length"
os.makedirs(output_dir, exist_ok=True)

def parse_token(token: str):
    """
    Atteso: "ASN-CC-REG" (es. "13335-DE-BERLIN")
    Fallback: "ASN"
    Ritorna: (asn:int|None, pop_key:str|None)
    """
    token = str(token).strip()
    parts = token.split("-")

    try:
        asn = int(parts[0])
    except:
        return None, None

    if len(parts) >= 3:
        cc = parts[1].strip()
        reg = parts[2].strip()
        pop_key = f"{asn}-{cc}-{reg}"
        return asn, pop_key

    return asn, str(asn)

def extract_pop_path(path: str):
    """
    Converte una stringa path "a->b->c" in lista di pop_key.
    """
    if not isinstance(path, str) or not path.strip():
        return []
    out = []
    for seg in path.split("->"):
        _, pop_key = parse_token(seg)
        if pop_key is not None:
            out.append(pop_key)
    return out

with open(geo_json_path, "r", encoding="utf-8") as f:
    geo_data = json.load(f)

# pop_key ("ASN-CC-REG") -> (lon, lat)
pop_to_coords = {}
asn_to_coords = {}

for entry in geo_data:
    lon = entry.get("lon")
    lat = entry.get("lat")
    if lon is None or lat is None:
        continue

    asn = str(entry.get("as_number")).strip()
    if asn and asn != "None":
        asn_to_coords[asn] = (lon, lat)

    pop_key = entry.get("pop")
    if pop_key is not None:
        pop_key = str(pop_key).strip()
        if pop_key:
            pop_to_coords[pop_key] = (lon, lat)
            #pop_to_coords[pop_key.rstrip("-")] = (lon, lat)

print(f"Loaded coords: {len(pop_to_coords)} PoPs, {len(asn_to_coords)} AS fallbacks")


def load_emissions(length):
    base = r"data\server\csvs"
    sp = pd.read_csv(f"{base}/edges_glo_SP_jul-dec_len{length}.csv", dayfirst=True)
    le = pd.read_csv(f"{base}/edges_glo_LE_jul-dec_len{length}.csv", dayfirst=True)

    sp.columns = sp.columns.str.lower()
    le.columns = le.columns.str.lower()

    sp["datetime"] = pd.to_datetime(sp["date"] + " " + sp["hour"].astype(str) + ":00:00", errors="coerce")
    le["datetime"] = pd.to_datetime(le["date"] + " " + le["hour"].astype(str) + ":00:00", errors="coerce")

    sp = sp[sp["datetime"] == TARGET_DATETIME]
    le = le[le["datetime"] == TARGET_DATETIME]

    df = pd.merge(sp, le, on=["source_as", "target_as"], suffixes=("_sp", "_le"))
    df["saving"] = df["emissions_total_sp"] - df["emissions_total_le"]

    return df

for length in LENGTHS:
    print(f"Processing length {length}...")
    df = load_emissions(length)
    if df.empty:
        print(f"No rows for length {length} at {TARGET_DATETIME}")
        continue

    top = df.nlargest(TOP_K, "saving")

    G = nx.DiGraph()

    for _, row in top.iterrows():
        for typ, color in [("sp", "red"), ("le", "green")]:
            path_col = f"emissions_path_{typ}"   
            if path_col not in row or pd.isna(row[path_col]):
                continue

            try:
                pop_path = extract_pop_path(row[path_col])
                if len(pop_path) < 2:
                    continue
                for node in pop_path:
                    if node in pop_to_coords or node in asn_to_coords:
                        G.add_node(node)

                for i in range(len(pop_path) - 1):
                    u, v = pop_path[i], pop_path[i + 1]

                    has_u = (u in pop_to_coords) or (u in asn_to_coords)
                    has_v = (v in pop_to_coords) or (v in asn_to_coords)
                    if has_u and has_v:
                        G.add_edge(u, v, color=color)

            except Exception as e:
                print(f"Error parsing PoP path: {row[path_col]} | {e}")
    print(f"✔ Length {length}: {len(G.nodes())} nodes, {len(G.edges())} edges")

    fig = plt.figure(figsize=(20, 10))
    m = Basemap(projection='robin', lon_0=0, resolution='c')

    m.drawcoastlines(color='black')
    m.drawcountries(color='black')
    m.drawstates(color='black')

    def get_coords(node):
        if node in pop_to_coords:
            return pop_to_coords[node]
        if node in asn_to_coords:
            return asn_to_coords[node]
        return None

    # Draw paths (edges)
    for u, v, data in G.edges(data=True):
        cu = get_coords(u)
        cv = get_coords(v)
        if not cu or not cv:
            continue

        lon1, lat1 = cu
        lon2, lat2 = cv
        x1, y1 = m(lon1, lat1)
        x2, y2 = m(lon2, lat2)
        m.plot([x1, x2], [y1, y2], color=data['color'], linewidth=1.0, alpha=0.8, zorder=2)

    # Draw nodes
    for node in G.nodes():
        c = get_coords(node)
        if not c:
            continue
        x, y = m(*c)
        m.plot(x, y, 'o', markersize=3, color='black', alpha=0.9, zorder=3)

    plt.title(f"Top {TOP_K} Emission-Saving PoP Paths for Length {length}\n(SP=Red, LE=Green)", fontsize=15)
    plt.tight_layout()
    output_path = os.path.join(output_dir, f"pop_top_{TOP_K}_paths_length_{length}.png")
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Saved plot: {output_path}")
