import os
import pandas as pd
from topology_map.networkx_graph import ASGraph
import json

# File paths
json_file_path = r"topology_map\data\filtered_data.json"
relationships_file = r"data\topology_data\20240101.as-rel2.txt"
emissions_folder_path = r"energy_graphs\data"
output_folder = r"topology_map\data"
os.makedirs(output_folder, exist_ok=True)

# Load AS-to-country mapping
with open(json_file_path, "r") as json_file:
    as_to_country = {entry['as_number']: entry['country'] for entry in json.load(json_file)}

# Initialize the ASGraph
graph = ASGraph(
    data_file=json_file_path,
    relationships_file=relationships_file,
    eu_countries=[
        "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czech Republic", "Denmark", "Estonia", "Finland", "France",
        "Germany", "Greece", "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands",
        "Poland", "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden"
    ],
    emissions_folder_path=emissions_folder_path,  
    as_to_country=as_to_country  
)

# Build graph
graph.add_nodes()
graph.add_edges()

# Define dates (10th of each month)
dates = [f"2023-{str(m).zfill(2)}-10" for m in range(1, 13)]  

# Define hours for 24-hour analysis
hours = [f"{str(h).zfill(2)}" for h in range(24)]

# List of source-target pairs
source_target_pairs = [("12479", "15991")]  # Add more pairs as needed Spain - Sweden

# Prepare CSV output file
csv_filename = os.path.join(output_folder, "shortest_path_path_data.csv")
columns = ["date", "hour", "source_as", "target_as", "emissions_length", "emissions_total"]

# If the file doesn't exist, write headers
if not os.path.exists(csv_filename):
    pd.DataFrame(columns=columns).to_csv(csv_filename, index=False)

# Process each source-target pair for each date
for date in dates:
    for source_as, target_as in source_target_pairs:
        for hour in hours:  
            specific_datetime = f"{date} {hour}:00:00"
            graph.add_emission_data(specific_datetime)  

            # Compute paths per hour
            emissions_paths = graph.find_all_valid_shortest_paths(source_as, graph.cost)
            emissions_path = emissions_paths.get(target_as, [])
            emissions_length = len(emissions_path) - 1 if emissions_path else 0

            # Calculate total emissions for the lowest emissions path (including last node)
            emissions_total = sum(graph.cost(node) for node in emissions_path) if emissions_path else 0

            # Append to CSV immediately
            new_data = pd.DataFrame([[date, hour, source_as, target_as, emissions_length, emissions_total]], columns=columns)
            new_data.to_csv(csv_filename, mode="a", header=False, index=False)

            print(f"Saved: {date} {hour}")

print(f"All data saved successfully to {csv_filename}")
