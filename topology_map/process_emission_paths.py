import os
import pickle
import pandas as pd
import collections
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
import math
from networkx_graph import ASGraph

# -----------------------------
# Folders
# -----------------------------
pickle_folder = r"data\data\pickle_graphs"
output_folder = r"data\server"
os.makedirs(output_folder, exist_ok=True)

# -----------------------------
# Dates and hours
# -----------------------------
dates = ["2023-01-10","2023-02-10","2023-03-10","2023-04-10","2023-05-10","2023-06-10"]
# dates = ["2023-07-10","2023-08-10","2023-09-10","2023-10-10","2023-11-10","2023-12-10"]
hours = [f"{str(h).zfill(2)}" for h in range(24)]

# -----------------------------
# Load AS pair data
# -----------------------------
path_to_csv = "pop_10k_sample.csv"
df_paths = pd.read_csv(path_to_csv)

# Group by path length
length_to_pairs = collections.defaultdict(list)
for _, row in df_paths.iterrows():
    source = str(row["source_as"])
    target = str(row["target_as"])
    length = int(row["path_length"])
    length_to_pairs[length].append((source, target))

# Selected path lengths
selected_lengths = {1}

# -----------------------------
# Worker init & function
# -----------------------------
_worker_graph = None
_worker_dt = None  # ### DEBUG INF: keep the hour for logging

def _init_worker(graph_obj_or_bytes, specific_datetime: str):
    """
    Unpickle the ASGraph once per worker.
    """
    global _worker_graph, _worker_dt
    graph = pickle.loads(graph_obj_or_bytes) if isinstance(graph_obj_or_bytes, (bytes, bytearray)) else graph_obj_or_bytes
    _worker_graph = graph
    _worker_dt = specific_datetime

def _edge_debug(graph: ASGraph, u, v):
    """### DEBUG INF: collect useful attributes to print when an edge is bad."""
    try:
        G = graph.graph  # the inner NetworkX graph
        ed = G[u][v]
        nd_u = G.nodes[u]
        nd_v = G.nodes[v]
    except Exception:
        return {}

    # Pick common suspects if present
    fields = {}
    for k in ("emissions","traffic","capacity","bytes","throughput","rate","weight"):
        if k in ed:
            fields[f"edge.{k}"] = ed.get(k)

    for side, nd in (("u", nd_u), ("v", nd_v)):
        for k in ("iso","country","region","intensity","emissions"):
            if k in nd:
                fields[f"{side}.{k}"] = nd.get(k)

    return fields

def _path_edge_emissions_total(graph: ASGraph, path_nodes, pair):
    """Sum emissions along edges using ASGraph.edge_cost(u, v) and report inf/nan per edge."""
    if not path_nodes or len(path_nodes) < 2:
        return 0.0
    total = 0.0
    for u, v in zip(path_nodes[:-1], path_nodes[1:]):
        try:
            cost = graph.edge_cost(u, v)  # should read edge['emissions']
        except Exception as e:
            print(f"[ERROR] {_worker_dt} {pair[0]}->{pair[1]} edge_cost({u},{v}) raised: {e}")
            continue

        # ### DEBUG INF: log any non-finite cost right away with context
        if not isinstance(cost, (int,float)) or math.isnan(cost) or math.isinf(cost):
            meta = _edge_debug(graph, u, v)
            print(f"[INF-COST] dt={_worker_dt} pair={pair[0]}->{pair[1]} edge={u}->{v} "
                  f"cost={cost} attrs={meta}")
        else:
            total += float(cost)
    return total

def compute_emissions(args):
    """
    Compute emissions path for a pair (source_as, target_as) on the worker's ASGraph.
    Uses ASGraph.find_valid_path(..., emissions=True) and sums edge emissions.
    """
    pair, date, hour = args
    source_as, target_as = pair
    try:
        graph: ASGraph = _worker_graph

        # Find path (emissions-aware)
        path_nodes = graph.find_valid_path(source_as, target_as, emissions=True)

        if not path_nodes:
            # ### DEBUG INF: explicit no-path log (often caused by inf costs blocking graph)
            print(f"[NO-PATH] dt={_worker_dt} pair={source_as}->{target_as}")
            return [date, hour, source_as, target_as, 0, 0.0, ""]

        emissions_total = _path_edge_emissions_total(graph, path_nodes, pair)

        # ### DEBUG INF: path-level check
        if not isinstance(emissions_total, (int,float)) or math.isnan(emissions_total) or math.isinf(emissions_total):
            print(f"[BAD-TOTAL] dt={_worker_dt} pair={source_as}->{target_as} "
                  f"path_len={len(path_nodes)-1} total={emissions_total} path={' -> '.join(path_nodes)}")

        emissions_path_str = " -> ".join(map(str, path_nodes))
        return [date, hour, source_as, target_as, len(path_nodes) - 1, emissions_total, emissions_path_str]

    except Exception as e:
        print(f"[ERROR] {source_as}->{target_as} dt={_worker_dt}: {e}")
        return None

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    for path_length in selected_lengths:
        csv_filename = os.path.join(output_folder, f"as0_LE_jan-jun_{path_length}.csv")

        # Build a set of (date, hour) already processed
        completed = set()
        if os.path.exists(csv_filename):
            try:
                df_done = pd.read_csv(csv_filename, usecols=["date", "hour"])
                df_done["hour"] = df_done["hour"].astype(str).str.zfill(2)
                completed = set(zip(df_done["date"], df_done["hour"]))
            except Exception as e:
                print(f"[WARNING] Failed reading {csv_filename}: {e}")

        source_target_pairs = length_to_pairs[path_length]

        for date in dates:
            pickle_filename = os.path.join(pickle_folder, f"as0_{date}.pkl")
            if not os.path.exists(pickle_filename):
                print(f"[SKIP] Missing graph file for {date}")
                continue

            with open(pickle_filename, "rb") as f:
                hourly_graphs = pickle.load(f)

            for hour in hours:
                if (date, hour) in completed:
                    print(f"[SKIP] Already processed {date} {hour} for path length {path_length}")
                    continue

                specific_datetime = f"{date} {hour}:00:00"
                if specific_datetime not in hourly_graphs:
                    print(f"[SKIP] Missing hourly graph for {specific_datetime}")
                    continue

                print(f"\n[INFO] Processing graph for {specific_datetime}, path length {path_length}")

                entry = hourly_graphs[specific_datetime]
                if isinstance(entry, (bytes, bytearray)):
                    graph_bytes = entry
                else:
                    graph_bytes = pickle.dumps(entry, protocol=pickle.HIGHEST_PROTOCOL)

                task_args = [(pair, date, hour) for pair in source_target_pairs]
                N = len(task_args)
                results = []

                if N <= 64:
                    _init_worker(graph_bytes, specific_datetime)  # prime once
                    for t in tqdm(task_args, total=N, desc=f"{date} {hour} - len {path_length}"):
                        r = compute_emissions(t)
                        if r:
                            results.append(r)
                else:
                    with ProcessPoolExecutor(
                        max_workers=8,
                        initializer=_init_worker,
                        initargs=(graph_bytes, specific_datetime),
                    ) as executor:
                        for r in tqdm(
                            executor.map(compute_emissions, task_args, chunksize=1),
                            total=N,
                            desc=f"{date} {hour} - len {path_length}"
                        ):
                            if r:
                                results.append(r)

                # Save to CSV
                write_header = not os.path.exists(csv_filename)
                pd.DataFrame(
                    results,
                    columns=["date", "hour", "source_as", "target_as", "emissions_length", "emissions_total", "emissions_path"]
                ).to_csv(csv_filename, mode="a", header=write_header, index=False)
