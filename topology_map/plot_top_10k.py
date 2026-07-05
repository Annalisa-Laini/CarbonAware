import pandas as pd
import json
import os
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap
import networkx as nx

# === Config ===
TOP_K = 100
LENGTHS = [1, 2, 3, 4, 5, 6]
TARGET_DATETIME = pd.to_datetime("2023-07-10 12:00:00")

geo_json_path = r"data\data\geolocation_data_global.json"
output_path = r"topology_map\plots\geo_paths_per_length\combined_top_100_paths_all_lengths.png"

# === Load geolocation info ===
with open(geo_json_path, "r") as f:
    geo_data = json.load(f)

as_to_coords = {
    int(entry["as_number"]): (entry["lon"], entry["lat"])
    for entry in geo_data
    if "lat" in entry and "lon" in entry
}

# === Load emissions CSVs and compute savings ===
def load_emissions(length):
    base = r"data\data\data 4 path plot\CSV"
    sp = pd.read_csv(f"{base}/global_newSP_jul-dec_len{length}.csv", dayfirst=True)
    le = pd.read_csv(f"{base}/global_newLE_jul-dec_len{length}.csv", dayfirst=True)

    sp.columns = sp.columns.str.lower()
    le.columns = le.columns.str.lower()

    sp["datetime"] = pd.to_datetime(sp["date"] + " " + sp["hour"].astype(str) + ":00:00", errors="coerce")
    le["datetime"] = pd.to_datetime(le["date"] + " " + le["hour"].astype(str) + ":00:00", errors="coerce")

    sp = sp[sp["datetime"] == TARGET_DATETIME]
    le = le[le["datetime"] == TARGET_DATETIME]

    df = pd.merge(sp, le, on=["source_as", "target_as"], suffixes=("_sp", "_le"))
    df["saving"] = df["emissions_total_sp"] - df["emissions_total_le"]

    return df

# === Build unified graph ===
G = nx.DiGraph()

for length in LENGTHS:
    df = load_emissions(length)
    top = df.nlargest(TOP_K, "saving")

    for _, row in top.iterrows():
        for typ, color in [("sp", "red"), ("le", "green")]:
            path_col = f"emissions_path_{typ}"
            if pd.isna(row[path_col]):
                continue

            try:
                path = [int(x.strip()) for x in row[path_col].split("->")]

                for node in path:
                    if node in as_to_coords:
                        G.add_node(node)

                for i in range(len(path) - 1):
                    u, v = path[i], path[i + 1]
                    if u in as_to_coords and v in as_to_coords:
                        G.add_edge(u, v, color=color)
            except Exception as e:
                print(f"⚠️ Error parsing path: {row[path_col]} | {e}")

print(f"📊 Final unified graph: {len(G.nodes())} nodes, {len(G.edges())} edges")

# === Plot the combined map ===
fig = plt.figure(figsize=(20, 10))
m = Basemap(projection='robin', lon_0=0, resolution='c')

# Draw borders only
m.drawcoastlines(color='black')
m.drawcountries(color='black')
m.drawstates(color='black')

# Draw edges
for u, v, data in G.edges(data=True):
    if u in as_to_coords and v in as_to_coords:
        lon1, lat1 = as_to_coords[u]
        lon2, lat2 = as_to_coords[v]
        x1, y1 = m(lon1, lat1)
        x2, y2 = m(lon2, lat2)
        m.plot([x1, x2], [y1, y2], color=data['color'], linewidth=1.0, alpha=0.7, zorder=2)

# Draw nodes
for node in G.nodes():
    if node in as_to_coords:
        x, y = m(*as_to_coords[node])
        m.plot(x, y, 'o', markersize=3, color='black', alpha=0.9, zorder=3)

plt.title("Top 100 Emission Saving Paths Across All Lengths (SP=Red, LE=Green)", fontsize=15)
plt.tight_layout()
plt.savefig(output_path, dpi=300)
plt.close()

print(f"✅ Saved final combined plot to:\n{output_path}")
