import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np

lengths = [1, 2, 3, 4, 5, 6]  
for length in lengths:
    # Construct file paths dynamically
    file_LE_1 = fr"data\data\data 4 path plot\CSV\global_newLE_jan-may_len{length}.csv"
    file_LE_2 = fr"data\data\data 4 path plot\CSV\global_newLE_jul-dec_len{length}.csv"
    file_SP_1 = fr"data\data\data 4 path plot\CSV\global_newSP_jan-may_len{length}.csv"
    file_SP_2 = fr"data\data\data 4 path plot\CSV\global_newSP_jul-dec_len{length}.csv"

    couples_file = r"sampled_10k_pairs.csv"
    couples_df = pd.read_csv(couples_file)

    # Load datasets
    df_SP_1 = pd.read_csv(file_SP_1, parse_dates=["date"], dayfirst=False)
    df_SP_2 = pd.read_csv(file_SP_2, parse_dates=["date"], dayfirst=False)
    df_LE_1 = pd.read_csv(file_LE_1, parse_dates=["date"], dayfirst=False)
    df_LE_2 = pd.read_csv(file_LE_2, parse_dates=["date"], dayfirst=False)

    df_LE = pd.concat([df_LE_1, df_LE_2], ignore_index=True)
    df_SP = pd.concat([df_SP_1, df_SP_2], ignore_index=True)

    df = pd.merge(df_SP, df_LE, on=["date", "hour", "source_as", "target_as"], suffixes=("_SP", "_LE"))

    num_couples = couples_df[couples_df["path_length"] == length].shape[0]

    df["emission_difference"] = (
        (df["emissions_total_SP"] - df["emissions_total_LE"]) / df["emissions_total_SP"]
    ) * 100
    df["emission_difference"] = df["emission_difference"].round(6)

    unique_dates = np.sort(df["date"].dt.date.unique())[:12] 

    rows, cols = 3, 4
    figsize = (22, 18)
    ymin, ymax = -2, 110

    output_folder = r"topology_map\plots\emission_boxplots"
    os.makedirs(output_folder, exist_ok=True)

    fig, axes = plt.subplots(rows, cols, figsize=figsize, sharex=True, sharey=True)
    axes = axes.flatten()

    for i, date in enumerate(unique_dates):
        df_day = df[df["date"].dt.date == date]

        path_means = df_day.groupby(["source_as", "target_as"])["emission_difference"].mean()

        if path_means.empty:
            print(f"No data for date {date}")
            continue

        lowest_path = path_means.idxmin()
        highest_path = path_means.idxmax()

        hours = range(24)
        mean_low = []
        mean_high = []

        for h in hours:
            vals_low = df_day[
                (df_day["hour"] == h) &
                (df_day["source_as"] == lowest_path[0]) &
                (df_day["target_as"] == lowest_path[1])
            ]["emission_difference"]
            mean_low.append(vals_low.mean() if not vals_low.empty else np.nan)

            vals_high = df_day[
                (df_day["hour"] == h) &
                (df_day["source_as"] == highest_path[0]) &
                (df_day["target_as"] == highest_path[1])
            ]["emission_difference"]
            mean_high.append(vals_high.mean() if not vals_high.empty else np.nan)

        ax = axes[i]
        ax.plot(hours, mean_low, color="green", marker="o", label="Lowest emission diff path")
        ax.plot(hours, mean_high, color="blue", marker="o", label="Highest emission diff path")

        ax.set_title(f"{date}", fontsize=12)
        ax.set_xlim(0, 23)
        ax.set_xticks(range(0, 24, 2))
        ax.set_xlabel("Hour of Day")
        ax.set_ylabel("Emission Difference (%)")
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.set_ylim(ymin, ymax)

    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])

    # Legend for whole figure
    handles = [
        plt.Line2D([], [], color="green", marker="o", label="Lowest emission diff path"),
        plt.Line2D([], [], color="blue", marker="o", label="Highest emission diff path"),
    ]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=12)

    fig.suptitle(
        f"Hourly Emission Difference (%) for Lowest and Highest Emission Paths (Length {length})\n",
        fontsize=18,
        fontweight="bold"
    )

    plot_filename = os.path.join(output_folder, f"hourly_lineplot_lowest_highest_len{length}.png")
    fig.savefig(plot_filename, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"Length {length} done. Saved to: {plot_filename}")
