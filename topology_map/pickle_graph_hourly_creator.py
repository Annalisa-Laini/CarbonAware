import os
import pickle
from networkx_graph import ASGraph

graph_pickle_folder = r"topology_map\pickle_graphs"
output_pickle_folder = r"data\data\all_paths_pickle"
os.makedirs(output_pickle_folder, exist_ok=True)

graph: ASGraph = ASGraph(...)
dates = [f"2023-{str(m).zfill(2)}-10" for m in range(1, 13)]
hours = [f"{str(h).zfill(2)}" for h in range(24)]

def load_graph(date, hour):
    """Load graph object for a specific hour."""
    filename = os.path.join(graph_pickle_folder, f"glo_graph_{date}.pkl")
    if not os.path.exists(filename):
        print(f"Missing graph file: {filename}")
        return None

    with open(filename, "rb") as f:
        hourly_graphs = pickle.load(f)

    datetime_key = f"{date} {hour}:00:00"
    if datetime_key not in hourly_graphs:
        print(f"Missing hour {datetime_key} in {filename}")
        return None

    return pickle.loads(hourly_graphs[datetime_key])

for date in dates:
    all_paths_by_hour = {}
    for hour in hours:
        graph = load_graph(date, hour)
        if graph:
            all_paths = {}
            for node in graph.graph.nodes:
                paths = graph.find_all_valid_shortest_paths(node, graph.cost)
                if paths:
                    all_paths[node] = paths
            all_paths_by_hour[f"{date} {hour}:00:00"] = all_paths

    out_path = os.path.join(output_pickle_folder, f"all_paths_{date}.pkl")
    with open(out_path, "wb") as f:
        pickle.dump(all_paths_by_hour, f)

print("All paths computed and saved.")