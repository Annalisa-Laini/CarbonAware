from networkx_graph import ASGraph
from datetime import datetime
import json
import os

if __name__ == "__main__":
    with open(r"topology_map\data\countries.txt", "r", encoding="utf-8") as file:
        content = file.read()
    countries = [country.strip().strip('"') for country in content.split(',') if country.strip()]

    # === File paths ===
    geo_json_path = r"topology_map\data\geolocation_pop.json"
    iso_mapping_path = r"topology_map\data\iso.json"
    emissions_folder_path = r"energy_graphs\data"
    relationships_file = r"data\topology_data\20240101.as-rel2.txt"

    # === Load geo data ===
    with open(geo_json_path, "r") as f:
        data = json.load(f)
        as_to_country = {entry['pop']: entry['country'] for entry in data}
        as_to_region = {entry['pop']: entry['region'] for entry in data}

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
    # print(f"Filtered entries: {len(graph.filtered_data)}")

    if input("Do you want to plot the graph? (yes/no): ").strip().lower() == 'yes':
        graph.plot_graph()

    source_as = int(input("Enter the source AS number: ").strip())
    target_as = int(input("Enter the target AS number: ").strip())

    specific_datetime = input("Enter the datetime (YYYY-MM-DD HH:MM:SS): ").strip()
    
    graph.add_emission_data(specific_datetime)
    valid_paths = graph.find_all_valid_shortest_paths(source_as)

    if target_as in valid_paths:
        path = valid_paths[target_as]
        total_emissions = 0
        print(f"Path from {source_as} to {target_as}: {path}")

        for node in path:
            node_emissions = graph.cost(node)
            print(f"Emissions for node {node}: {node_emissions}")
            total_emissions += node_emissions

        print(f"Total emissions for the path: {total_emissions}")
    else:
        print("No valid path found for the target AS.")


