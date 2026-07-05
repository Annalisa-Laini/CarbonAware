import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import uniform_filter1d  # Moving average

# Define paths
data_folder = r"data\data\shortest seasonal paths"
output_folder = r"topology_map\plots\emissions_scatter"
os.makedirs(output_folder, exist_ok=True)  # Ensure the folder exists

# Define target dates and hours
dates = ["Jan_17", "Apr_18", "Jul_19", "Oct_19"]
hours = ["00", "06", "12", "18"]

def load_emissions_from_csv(filename):
    """Load emissions data from CSV and sort paths by emissions."""
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return []

    try:
        df = pd.read_csv(filename, engine='python')
        if "emissions" not in df.columns:
            print(f"Column 'emissions' not found in {filename}")
            return []
        
        emissions = df["emissions"].astype(float).dropna()
        return np.sort(emissions)  # Sort emissions in ascending order
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return []

def sample_data(x, y, sample_fraction=0.15):
    """Randomly sample a percentage of points while keeping order."""
    N = len(y)
    sample_size = max(10, int(sample_fraction * N))  # Ensure at least 10 points
    indices = np.sort(np.random.choice(N, sample_size, replace=False))  # Randomly choose indices, keeping order
    return x[indices], y[indices]

# Create a single figure with subplots
fig, axes = plt.subplots(nrows=4, ncols=4, figsize=(16, 12), constrained_layout=True)

for i, date in enumerate(dates):
    for j, hour in enumerate(hours):
        ax = axes[i, j]  # Select subplot

        # File paths
        shortest_path_file = os.path.join(data_folder, f"shortest_paths_{date}_hour{hour}.csv")
        emissions_path_file = os.path.join(data_folder, f"lowest_emissions_{date}_hour{hour}.csv")

        # Load emissions data
        shortest_emissions = load_emissions_from_csv(shortest_path_file)
        lowest_emissions = load_emissions_from_csv(emissions_path_file)

        if len(shortest_emissions) == 0 or len(lowest_emissions) == 0:
            ax.set_title(f"{date.replace('_', ' ')} - {hour}:00\n(Missing Data)")
            ax.axis("off")  # Hide empty subplots
            continue

        # Generate x-axis as index (since paths are sorted by emissions)
        x_shortest = np.arange(len(shortest_emissions))
        x_lowest = np.arange(len(lowest_emissions))

        # Randomly sample 10-15% of points
        x_shortest_sampled, shortest_emissions_sampled = sample_data(x_shortest, shortest_emissions, 0.15)
        x_lowest_sampled, lowest_emissions_sampled = sample_data(x_lowest, lowest_emissions, 0.15)

        # Scatter plot (with sampled points)
        ax.scatter(x_shortest_sampled, shortest_emissions_sampled, color="orange", alpha=0.5, label="Shortest Paths", s=5)
        ax.scatter(x_lowest_sampled, lowest_emissions_sampled, color="green", alpha=0.5, label="Lowest Emissions Paths", s=5)

        # Moving average for trend line
        window_size = max(5, len(shortest_emissions) // 20)  # Adjustable smoothing
        trend_shortest = uniform_filter1d(shortest_emissions, size=window_size)
        trend_lowest = uniform_filter1d(lowest_emissions, size=window_size)

        # Sample the trend line at the same points
        _, trend_shortest_sampled = sample_data(x_shortest, trend_shortest, 0.15)
        _, trend_lowest_sampled = sample_data(x_lowest, trend_lowest, 0.15)

        # Plot trend lines
        ax.plot(x_shortest_sampled, trend_shortest_sampled, color="red", linewidth=0.5, label="Avg Shortest Paths")
        ax.plot(x_lowest_sampled, trend_lowest_sampled, color="blue", linewidth=0.5, label="Avg Lowest Emissions")

        # Formatting
        ax.set_xlabel("Paths (Sorted by Emissions)")
        ax.set_ylabel("Emissions")
        ax.set_title(f"{date.replace('_', ' ')} - {hour}:00")

# Add legend outside the plot
handles, labels = ax.get_legend_handles_labels()
fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.05, 1), fontsize=12)

# Save the figure
plot_filename = os.path.join(output_folder, "emissions_scatter_trend_sampled.png")
plt.savefig(plot_filename, dpi=300, bbox_inches="tight")
plt.close()

print(f"Saved scatter plot with trend lines (sampled): {plot_filename}")
