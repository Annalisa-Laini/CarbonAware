import os
import pickle
import pandas as pd
from networkx_graph import ASGraph
import json

# File paths
geo_json_path = r"C:\Users\annal\Documents\GitHub\Tesi\topology_map\data\geolocation_pop.json"
relationships_file = r"C:\Users\annal\Desktop\Tesi\topology_data\20240101.as-rel2.txt"
emissions_folder_path = r"C:\Users\annal\Documents\GitHub\Tesi\energy_graphs\data"
pickle_folder = r"C:\Users\annal\Desktop\Tesi\data\pickle_graphs"
iso_mapping_path = r"C:\Users\annal\Documents\GitHub\Tesi\topology_map\data\iso.json"
os.makedirs(pickle_folder, exist_ok=True)

# === Load geo data ===
with open(geo_json_path, "r") as f:
        data = json.load(f)
        as_to_country = {int(entry['as_number']): entry['country'] for entry in data}
        as_to_region = {int(entry['as_number']): entry['region'] for entry in data}

with open(r"topology_map\data\countries.txt", "r", encoding="utf-8") as file:
    content = file.read()
countries = [country.strip().strip('"') for country in content.split(',') if country.strip()]

# Define dates (10th of each month)
dates = [f"2023-{str(m).zfill(2)}-10" for m in range(1,4)] # 24 ore per il 10 del mese
hours = [f"{str(h).zfill(2)}" for h in range(24)]


# Process each month
for date in dates:

    # Initialize a dictionary to store hourly graphs
    hourly_graphs = {}

   
    # === Initialize graph ===
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

    # Set mappings
    graph.as_to_country = as_to_country
    graph.as_to_region = as_to_region
    graph.node_costs = {}

    # === Process graph ===
    graph.add_nodes()
    graph.add_edges()

    # Process each hour
    for hour in hours:
        specific_datetime = f"{date} {hour}:00:00"
        print(f"Processing graph for {specific_datetime}...") 
        graph.add_emission_data(specific_datetime)  # Add emissions for this hour

        # Save a copy of the graph for this hour
        hourly_graphs[specific_datetime] = pickle.dumps(graph)  # Serialize the graph object

    # Save the entire month's graphs as a pickle file
    pickle_filename = os.path.join(pickle_folder, f"pop_edge_{date}.pkl")
    with open(pickle_filename, "wb") as f:
        pickle.dump(hourly_graphs, f)

    print(f"Graph for {date} saved.")

print("All graphs saved successfully.")