import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Define paths
#data_folder = r"data\data\shortest seasonal paths\diffs"
data_folder = r"data\data\sampled\lowest_emissions_distribution_diffs_sample.csv"
output_folder = r"topology_map\plots\distribution_plots"
os.makedirs(output_folder, exist_ok=True)  # Ensure the folder exists

# Define target dates and hours
dates = ["Jan_17", "Apr_18", "Jul_19", "Oct_19"]
hours = ["00", "06", "12", "18"]

def load_path_lengths_from_csv(filename):
    """Load CSV and extract path lengths (from the diffs files)."""
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return [], []

    try:
        df = pd.read_csv(filename)
        
        # Check if necessary columns exist (path lengths in the diffs file)
        if "hops_path_length" not in df.columns or "emissions_path_length" not in df.columns:
            print(f"Required columns not found in {filename}")
            return [], []
        
        # Extract the path lengths directly from the diffs CSV
        hops_path_lengths = df["hops_path_length"].astype(float)
        emissions_path_lengths = df["emissions_path_length"].astype(float)
        
        # Clean data by removing NaN and infinite values
        hops_path_lengths = hops_path_lengths[np.isfinite(hops_path_lengths)]
        emissions_path_lengths = emissions_path_lengths[np.isfinite(emissions_path_lengths)]
        
        return hops_path_lengths, emissions_path_lengths
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return [], []

# Create a single figure with subplots
fig, axes = plt.subplots(nrows=4, ncols=4, figsize=(16, 12), constrained_layout=True)

for i, date in enumerate(dates):
    for j, hour in enumerate(hours):
        ax = axes[i, j]  # Select the subplot

        # File names based on your data format (diffs_{date}_hour{hour}.csv)
        file_name = f"diff_{date}_hour{hour}.csv"
        path_file = os.path.join(data_folder, file_name)

        # Load path length distributions from the diffs file
        hops_path_lengths, emissions_path_lengths = load_path_lengths_from_csv(path_file)

        # Compute histogram bins
        all_lengths = np.concatenate((hops_path_lengths, emissions_path_lengths))
        bins = np.arange(min(all_lengths), max(all_lengths) + 2) - 0.5  # Align bins to integers

        # Compute histogram data
        shortest_counts, _ = np.histogram(hops_path_lengths, bins=bins)
        emissions_counts, _ = np.histogram(emissions_path_lengths, bins=bins)

        x = np.arange(len(shortest_counts))  # X-axis positions
        width = 0.4  # Bar width

        # Create side-by-side bar chart
        bars1 = ax.bar(x - width/2, shortest_counts, width=width, color="blue", alpha=0.7, label="Shortest Paths (Hops)")
        bars2 = ax.bar(x + width/2, emissions_counts, width=width, color="green", alpha=0.7, label="Lowest Emissions Paths")

        # Add labels on top of bars
        for bar in bars1:
            height = bar.get_height()  # Corrected: use `get_height()`
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2, height + 1, f"{height/1000:.1f}k", ha="right", fontsize=6, color="blue")

        for bar in bars2:
            height = bar.get_height()  # Corrected: use `get_height()`
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2, height + 1, f"{height/1000:.1f}k", ha="left", fontsize=6, color="green")

        # Formatting
        ax.set_xticks(x)
        ax.set_xticklabels(np.arange(min(all_lengths), max(all_lengths) + 1))
        ax.set_xlabel("Path Length (Hops)")
        ax.set_ylabel("Frequency")
        ax.set_title(f"{date.replace('_', ' ')} - {hour}:00")

# Add a single legend for the entire figure
handles, labels = ax.get_legend_handles_labels()
fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.05, 1), fontsize=12)
fig.suptitle("Differing paths length distribution during the year", fontsize=16, fontweight="bold")

# Save the full figure
plot_filename = os.path.join(output_folder, "diff_path_length_comparison_all_months.png")
plt.savefig(plot_filename, dpi=300, bbox_inches="tight")
plt.close()

print(f"Saved full comparison plot: {plot_filename}")
