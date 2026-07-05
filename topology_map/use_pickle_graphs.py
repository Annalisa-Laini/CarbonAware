import os
import pickle
import pandas as pd
import collections
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
import inspect
from networkx_graph import ASGraph

# Folders
pickle_folder = r"data\data\pickle_graphs"
output_folder = r"data\data\data 4 path plot"
os.makedirs(output_folder, exist_ok=True)

# Dates and hours
dates = ["2023-5-10"]
#hours = [f"{str(h).zfill(2)}" for h in range(24)]
hours = ["00"]
# Load AS pair data
path_to_csv = r"sampled_10k_pairs.csv"
df_paths = pd.read_csv(path_to_csv)

# Group by path length
length_to_pairs = collections.defaultdict(list)
for _, row in df_paths.iterrows():
    source = int(row["source_as"])
    target = int(row["target_as"])
    length = int(row["path_length"])
    length_to_pairs[length].append((source, target))

# Selected path lengths
selected_lengths = {3}

# Worker function
def compute_emissions(args):
    pair, graph_bytes, date, hour = args
    source_as, target_as = pair
    try:
        graph = pickle.loads(graph_bytes)
        emissions_path = graph.find_shortest_valid_path(source_as, target_as)  # this returns a list or None
        if emissions_path:
            emissions_length = len(emissions_path) - 1
            emissions_total = sum(graph.cost(node) for node in emissions_path)
            emissions_path_str = ' -> '.join(map(str, emissions_path))  # convert path to string
        else:
            emissions_length = 0
            emissions_total = 0
            emissions_path_str = ""

        return [date, hour, source_as, target_as, emissions_length, emissions_total, emissions_path_str]

    except Exception as e:
        print(f"[ERROR] {source_as}->{target_as}: {e}")
        return None


if __name__ == "__main__":
    for path_length in selected_lengths:
        csv_filename = os.path.join(output_folder, f"test4_LE_may_len{path_length}.csv")

        # Build a set of (date, hour) already processed
        completed = set()
        if os.path.exists(csv_filename):
            try:
                df_done = pd.read_csv(csv_filename, usecols=["date", "hour"])
                df_done["hour"] = df_done["hour"].astype(str).str.zfill(2)  # ensure zero-padded
                completed = set(zip(df_done["date"], df_done["hour"]))
            except Exception as e:
                print(f"[WARNING] Failed reading {csv_filename}: {e}")

        source_target_pairs = length_to_pairs[path_length]

        for date in dates:
            pickle_filename = os.path.join(pickle_folder, f"global_graph_{date}.pkl")
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
                graph_bytes = hourly_graphs[specific_datetime]  # still in pickle format

                task_args = [(pair, graph_bytes, date, hour) for pair in source_target_pairs]

                results = []
                with ProcessPoolExecutor(max_workers=16) as executor:
                    for result in tqdm(executor.map(compute_emissions, task_args), total=len(task_args),
                                       desc=f"{date} {hour} - len {path_length}"):
                        if result:
                            results.append(result)

                # Save to CSV
                write_header = not os.path.exists(csv_filename)
                pd.DataFrame(results, columns=["date", "hour", "source_as", "target_as", "emissions_length", "emissions_total", "emissions_path"]) \
                .to_csv(csv_filename, mode="a", header=write_header, index=False)

    print(" All data saved successfully.")
