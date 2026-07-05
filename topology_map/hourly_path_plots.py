import pandas as pd
import matplotlib.pyplot as plt
import os
import math

# Load both datasets
file_shortest = r"data\data\data 4 path plot\SP_path_data_len6_x10.csv"  # Update with actual path
file_emissions = r"data\data\data 4 path plot\LE_path_data_len6_x10.csv"  # Update with actual path


df_shortest = pd.read_csv(file_shortest, parse_dates=["date"], dayfirst=True)
df_emissions = pd.read_csv(file_emissions, parse_dates=["date"], dayfirst=True)

# Merge data on common identifiers
df = pd.merge(df_shortest, df_emissions, on=["date", "hour", "source_as", "target_as"], suffixes=("_shortest", "_emissions"))

# Unique dates
unique_dates = df["date"].dt.date.unique()

# Create output folder
output_folder = r"topology_map\plots\emission_plots"
os.makedirs(output_folder, exist_ok=True)

# Define grid size
rows, cols = 3, 4  # 3x4 grid (12 subplots per figure)
plots_per_figure = rows * cols  # 12 plots per image
num_figures = math.ceil(len(unique_dates) / plots_per_figure)  # Total figures needed

for fig_idx in range(num_figures):
    # Get subset of dates for this figure
    date_subset = unique_dates[fig_idx * plots_per_figure : (fig_idx + 1) * plots_per_figure]

    # Create figures
    fig_emissions, axes_emissions = plt.subplots(rows, cols, figsize=(20, 16), sharex=True)

    axes_emissions = axes_emissions.flatten()

    for i, date in enumerate(date_subset):
        df_day = df[df["date"].dt.date == date]

        # Group by hour and calculate mean emissions and hops for each method
        grouped = df_day.groupby("hour").agg({
            "emissions_total_shortest": "mean",
            "emissions_total_emissions": "mean",
            "emissions_length_shortest": "mean",
            "emissions_length_emissions": "mean"
        }).reset_index()

        # Plot Emissions (averaged over 10 couples)
        axes_emissions[i].plot(grouped["hour"], grouped["emissions_total_shortest"], marker="o", linestyle="-", label="Shortest Paths", color="blue")
        axes_emissions[i].plot(grouped["hour"], grouped["emissions_total_emissions"], marker="o", linestyle="-", label="Lowest Emissions Paths", color="green")
        axes_emissions[i].set_title(f"{date}")
        axes_emissions[i].set_ylabel("Avg. Emissions")
        axes_emissions[i].grid(True)

        # Set x-axis labels (hours)
        axes_emissions[i].set_xticks(grouped["hour"])
        axes_emissions[i].set_xticklabels(grouped["hour"].astype(str), rotation=45, fontsize=6)
       
    # Hide empty subplots (if any)
    for j in range(len(date_subset), plots_per_figure):
        fig_emissions.delaxes(axes_emissions[j])

    # Formatting
    fig_emissions.suptitle(f"Average Emissions Comparison for 10 couples of length 6 ", fontsize=16, fontweight="bold")
    # Move legend outside of the grid
    handles, labels = axes_emissions[0].get_legend_handles_labels()  # Get legend handles from one of the plots
    fig_emissions.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.05, 1), fontsize=10)
    
    # Save figures
    plot_emissions_filename = os.path.join(output_folder, f"len6_x10_emissions_comparison.png")

    fig_emissions.savefig(plot_emissions_filename, dpi=300, bbox_inches="tight")

    plt.close(fig_emissions)

    print(f"Saved: {plot_emissions_filename}")    