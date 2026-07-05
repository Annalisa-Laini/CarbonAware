import os
import pickle
import pandas as pd
from networkx_graph import ASGraph
import json

geo_json_path = r"topology_map\data\geolocation_pop.json"
relationships_file = r"data\topology_data\20240101.as-rel2.txt"
emissions_folder_path = r"energy_graphs\data"
pickle_folder = r"data\data\pickle_graphs"
iso_mapping_path = r"topology_map\data\iso.json"
os.makedirs(pickle_folder, exist_ok=True)

# === ASNs to zero ===
ASNS_TO_ZERO = { 3356, 7922, 3257, 174, 209, 701, 4766, 20940, 3320, 4134, 7018, 4837,3320, 4826 }  # AS with criticality over 10%

def zero_edges_for_asns(graph_obj, zero_asns) -> int:
    """
    Set edge['emissions'] = 0.0 for every edge whose *source* POP's ASN
    is in zero_asns. Returns the number of edges changed.
    """
    G = graph_obj.graph
    zset = {int(a) for a in zero_asns}
    changed = 0
    for u, v, ed in G.edges(data=True):
        asn = G.nodes[u].get("as_number")
        try:
            asn = int(asn)
        except Exception:
            continue
        if asn in zset:
            ed["emissions"] = 0.0
            changed += 1
    return changed

with open(geo_json_path, "r") as f:
    data = json.load(f)
    as_to_country = {int(entry['as_number']): entry['country'] for entry in data}
    as_to_region = {int(entry['as_number']): entry['region'] for entry in data}

with open(r"topology_map\data\countries.txt", "r", encoding="utf-8") as file:
    content = file.read()
countries = [country.strip().strip('"') for country in content.split(',') if country.strip()]

dates = [f"2023-{str(m).zfill(2)}-10" for m in range(9,10)]
hours = [f"{str(h).zfill(2)}" for h in range(24)]

for date in dates:
    hourly_graphs = {}

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

    graph.as_to_country = as_to_country
    graph.as_to_region = as_to_region
    graph.node_costs = {}

    graph.add_nodes()
    graph.add_edges()

    for hour in hours:
        specific_datetime = f"{date} {hour}:00:00"
        print(f"\nProcessing graph for {specific_datetime}...")

        graph.add_emission_data(specific_datetime)

        n_zeroed = zero_edges_for_asns(graph, ASNS_TO_ZERO)
        print(f"[ZERO] {specific_datetime}: set edge emissions to 0 on {n_zeroed:,} edges")
        hourly_graphs[specific_datetime] = pickle.dumps(graph, protocol=pickle.HIGHEST_PROTOCOL)

    pickle_filename = os.path.join(pickle_folder, f"as0_{date}.pkl")
    with open(pickle_filename, "wb") as f:
        pickle.dump(hourly_graphs, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"\nGraph for {date} saved to: {pickle_filename}")

print("\nAll graphs saved successfully.")
