import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Define paths
shortest_path_data_folder = r"data\data"
emissions_path_data_folder = r"data\data"
output_folder = r"topology_map\plots\distribution_plots"
os.makedirs(output_folder, exist_ok=True)

# Define target dates and hours
dates = ["Jan_17", "Apr_18", "Jul_19", "Oct_19"]
hours = ["00", "06", "12", "18"]

CHUNK = 200_000  # tune as needed

def file_min_max(filename):
    """Stream a CSV and return (min, max) of path_length; None if file missing/empty."""
    if not os.path.exists(filename):
        return None
    min_v, max_v = None, None
    try:
        for chunk in pd.read_csv(filename, usecols=["path_length"], chunksize=CHUNK):
            if chunk.empty:
                continue
            cmin = chunk["path_length"].min()
            cmax = chunk["path_length"].max()
            min_v = cmin if min_v is None else min(min_v, cmin)
            max_v = cmax if max_v is None else max(max_v, cmax)
    except Exception as e:
        print(f"Error scanning {filename}: {e}")
        return None
    if min_v is None or max_v is None:
        return None
    return int(min_v), int(max_v)

def stream_hist_counts(filename, bins):
    """Stream a CSV and accumulate histogram counts for path_length using provided bins."""
    counts = np.zeros(len(bins) - 1, dtype=np.int64)
    for chunk in pd.read_csv(filename, usecols=["path_length"], chunksize=CHUNK):
        vals = chunk["path_length"].to_numpy()
        c, _ = np.histogram(vals, bins=bins)
        counts += c
    return counts

# Create a single figure with subplots
fig, axes = plt.subplots(nrows=4, ncols=4, figsize=(16, 12), constrained_layout=True)

for i, date in enumerate(dates):
    for j, hour in enumerate(hours):
        ax = axes[i, j]

        shortest_path_file = os.path.join(shortest_path_data_folder, f"SP_pop_EU_global_{date}_hour{hour}.csv")
        emissions_path_file = os.path.join(emissions_path_data_folder, f"pop_LE_EU_global_{date}_hour{hour}.csv")

        # First pass: get min/max for both files (streaming)
        mm1 = file_min_max(shortest_path_file)
        mm2 = file_min_max(emissions_path_file)

        if mm1 is None or mm2 is None:
            ax.set_title(f"{date.replace('_', ' ')} - {hour}:00\n(Missing Data)")
            ax.axis("off")
            continue

        min_all = min(mm1[0], mm2[0])
        max_all = max(mm1[1], mm2[1])

        # Build identical bins to your original code:
        # bins = np.arange(min(all_lengths), max(all_lengths) + 2) - 0.5
        bins = np.arange(min_all, max_all + 2) - 0.5

        # Second pass: accumulate histogram counts per file (streaming)
        try:
            shortest_counts = stream_hist_counts(shortest_path_file, bins)
            emissions_counts = stream_hist_counts(emissions_path_file, bins)
        except Exception as e:
            ax.set_title(f"{date.replace('_', ' ')} - {hour}:00\n(Error reading)")
            ax.axis("off")
            print(f"Error computing hist for {date} {hour}: {e}")
            continue

        x = np.arange(len(shortest_counts))
        width = 0.4

        bars1 = ax.bar(x - width/2, shortest_counts,color="blue", width=width, label="Shortest Paths", alpha=0.7)
        bars2 = ax.bar(x + width/2, emissions_counts,color="green", width=width, label="Lowest Emissions Paths", alpha=0.7)

        # Optional: add small labels (can comment out if many bins)
        for bar in bars1:
            h = bar.get_height()
            if h > 0:
                ax.text(bar.get_x() + bar.get_width()/2, h, f"{h/1000:.1f}k", ha="right", va="bottom", fontsize=6)
        for bar in bars2:
            h = bar.get_height()
            if h > 0:
                ax.text(bar.get_x() + bar.get_width()/2, h, f"{h/1000:.1f}k", ha="left", va="bottom", fontsize=6)

        ax.set_xticks(x)
        ax.set_xticklabels(np.arange(min_all, max_all + 1))
        ax.set_xlabel("Path Length (Hops)")
        ax.set_ylabel("Frequency")
        ax.set_title(f"{date.replace('_', ' ')} - {hour}:00")

# One legend for the whole figure
handles, labels = axes[0,0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.05, 1), fontsize=12)
fig.suptitle("Path length distribution during the year for Shortest Path and Lowest Emissions Algorithms",
             fontsize=16, fontweight="bold")

plot_filename = os.path.join(output_folder, "pop_path_length_comparison_all_months.png")
plt.savefig(plot_filename, dpi=300, bbox_inches="tight")
plt.close()
print(f"Saved full comparison plot: {plot_filename}")
