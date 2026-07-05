import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np

#    file_LE_1 = fr"data\server\csvs\edgesGLO\edges_LE_glo_jan-jun_2_{length}.csv" # BASELINE
#    file_LE_2 = fr"data\server\csvs\edgesGLO\edges_glo_LE_jul-dec_len{length}.csv" # BASELINE
#    file_SP_1 = fr"data\server\csvs\edgesGLO\edges_SP_glo_jan-jun_2_{length}.csv" # BASELINE
#    file_SP_2 = fr"data\server\csvs\edgesGLO\edges_glo_SP_jul-dec_len{length}.csv" # BASELINE
#    file_SP_1 = fr"data\server\csvs\1k\as0\csvs\SP_jan-jun_len{length}_as0_1k.csv" # 1k AS0
#    file_SP_2 = fr"data\server\csvs\1k\as0\csvs\SP_jul-dec_len{length}_as0_1k.csv" # 1k AS0
#    file_LE_1 = fr"data\server\csvs\1k\as0\csvs\LE_jan-jun_len{length}_as0_1k.csv" # 1k AS0
#    file_LE_2 = fr"data\server\csvs\1k\as0\csvs\LE_jul-dec_len{length}_as0_1k.csv" # 1k AS0
#    file_SP_1 = fr"data\server\csvs\1k\SP_jan-jun_len{length}_1k.csv"
#    file_SP_2 = fr"data\server\csvs\1k\SP_jul-dec_len{length}_1k.csv"
#    file_LE_1 = fr"data\server\csvs\edgesEU\edges_LE_jan-jun_2_{length}.csv" # EU
#    file_LE_2 = fr"data\server\csvs\edgesEU\edges_LE_jul-dec_len{length}.csv" # EU
#    file_SP_1 = fr"data\server\csvs\edgesEU\edges_SP_jan-jun_2_{length}.csv" # EU
#    file_SP_2 = fr"data\server\csvs\edgesEU\edges_SP_jul-dec_len{length}.csv" # EU
#    file_SP_1 = fr"data\server\noval\SP_jan-jun_len{length}_noval.csv" # NOVAL
#    file_SP_2 = fr"data\server\noval\SP_jul-dec_len{length}_noval.csv" # NOVAL
#    file_LE_1 = fr"data\server\noval\LE_jan-jun_len{length}_noval.csv"# NOVAL
#    file_LE_2 = fr"data\server\noval\LE_jul-dec_len{length}_noval.csv"# NOVAL

lengths = [4,5,6] 

for length in lengths:
    # Construct file paths dynamically
    file_LE_1 = fr"data\server\csvs\1k\LE_jan-jun_len{length}_1k.csv"
    file_LE_2 = fr"data\server\csvs\1k\LE_jul-dec_len{length}_1k.csv"
    file_SP_1 = fr"data\server\csvs\1k\SP_jan-jun_len{length}_1k.csv"
    file_SP_2 = fr"data\server\csvs\1k\SP_jul-dec_len{length}_1k.csv"


    couples_file = r"pop_3k_sample.csv" #1000 couples len 4,5,6
    #couples_file = r"pop_10k_sample.csv" #global sample
    #couples_file = r"pop_10k_sample_novalidity.csv"
    #couples_file = r"pop_1k_sample.csv" #1k EUROPE SAMPLE
    couples_df = pd.read_csv(couples_file)

    # Load datasets
    df_SP_1 = pd.read_csv(file_SP_1, parse_dates=["date"], dayfirst=False)
    df_SP_2 = pd.read_csv(file_SP_2, parse_dates=["date"], dayfirst=False)
    df_LE_1 = pd.read_csv(file_LE_1, parse_dates=["date"], dayfirst=False)
    df_LE_2 = pd.read_csv(file_LE_2, parse_dates=["date"], dayfirst=False)

    df_LE = pd.concat([df_LE_1, df_LE_2],  ignore_index=True)
    df_SP = pd.concat([df_SP_1, df_SP_2],  ignore_index=True)

    df = pd.merge(df_SP, df_LE, on=["date", "hour", "source_as", "target_as"], suffixes=("_SP", "_LE"))
    num_couples = couples_df[couples_df["path_length"] == length].shape[0]

    df["emission_difference"] = (
        (df["emissions_total_SP"] - df["emissions_total_LE"]) / df["emissions_total_SP"]
    ) * 100
    df["emission_difference"] = df["emission_difference"].round(6)

    neg_rows = df[df.emission_difference < 0]

    if not neg_rows.empty:
        row = neg_rows.iloc[0]

        print(f"\n Negative diff – len{length}   date {row['date'].date()}   hour {row['hour']}")

        raw_sp = row["emissions_path_SP"]
        sp_path = [p.strip() for p in raw_sp.split("->")]

        raw_le = row["emissions_path_LE"]
        le_path = [p.strip() for p in raw_le.split("->")]

        print("SP path :", " → ".join(sp_path))
        print("LE path :", " → ".join(le_path))
        print("SP total emissions :", row["emissions_total_SP"])
        print("LE total emissions :", row["emissions_total_LE"])

    else:
        print(f"✅ No negative emission_difference rows found for len {length}.")

    unique_dates = df["date"].dt.date.unique()
    
    # SMALLER PLOT 

    dates_to_plot = pd.to_datetime([
        "2023-01-10",
        #"2023-04-10",
        #"2023-07-10",
        #"2023-10-10",
    ]).date

    unique_dates = [d for d in unique_dates if d in dates_to_plot]
    rows, cols = 1, 1
    figsize =(14,10)
    '''
    rows, cols = 3, 4  # IF FULL YEAR
    figsize = (22, 18)  
    #'''
    #output_folder = r"topology_map\plots\paper"
    #output_folder = r"data\boxplots"
    #os.makedirs(output_folder, exist_ok=True)

    # --- Export data for gnuplot (single day only) ---
    for date in unique_dates:
        df_day = df[df["date"].dt.date == date]

        stats_file = f"boxplot_data_len{length}_{date}.dat"
        alldata_file = f"alldata_len{length}_{date}.dat"

        with open(stats_file, "w") as fstats, \
             open(alldata_file, "w") as fall:

            fstats.write("#hour whislo q1 median q3 whishi mean\n")
            fall.write("#hour value\n")

            for h in range(24):
                data = df_day[df_day["hour"] == h]["emission_difference"].dropna().values
                if len(data) == 0:
                    continue

                p5, q1, med, q3, p95 = np.percentile(data, [5, 25, 50, 75, 95])
                mean = np.mean(data)
                fstats.write(f"{h} {p5:.6f} {q1:.6f} {med:.6f} {q3:.6f} {p95:.6f} {mean:.6f}\n")

                for v in data:
                    fall.write(f"{h} {v:.6f}\n")

        print(f"Saved: {stats_file} and {alldata_file}")

    fig, axes = plt.subplots(rows, cols, figsize=figsize, sharex=True, sharey=True, squeeze=False)
    axes = axes.flatten()
    ymin, ymax = -1, 5

    for i, date in enumerate(unique_dates):
        df_day = df[df["date"].dt.date == date]
        bxp_stats = []

        for h in range(24):
            data = df_day[df_day["hour"] == h]["emission_difference"].dropna().values

            if len(data) == 0:
                continue

            percentiles = np.percentile(data, [5, 25, 50, 75, 95])
            stats = {
                'med': percentiles[2],
                'q1': percentiles[1],
                'q3': percentiles[3],
                'whislo': percentiles[0],
                'whishi': percentiles[4],
                'fliers': data[(data < percentiles[0]) | (data > percentiles[4])].tolist(),
                'mean': np.mean(data),
            }
            bxp_stats.append(stats)

        if bxp_stats:
            ticks = list(range(1, len(bxp_stats) + 1, 2))
            labels = list(range(0, 24, 2))[:len(bxp_stats)]
            axes[i].bxp(bxp_stats, showmeans=True,
                        meanprops=dict(marker="D", markerfacecolor="green", markersize=6),
                        boxprops=dict(color="black"),
                        medianprops=dict(color="orange"),
                        whiskerprops=dict(color="black"),
                        capprops=dict(color="black"))
            axes[i].set_title(f"{date}", fontsize=20)
            axes[i].set_xticks(ticks)
            axes[i].set_xticklabels(labels, fontsize= 18)
            axes[i].grid(True, linestyle="--", alpha=0.5)
            axes[i].set_ylim(ymin, ymax)

    for ax in axes[-cols:]:
        ax.set_xlabel("Hour of the Day", fontsize=20)

    for ax in axes[::cols]:
        ax.set_ylabel("Emission Difference (%)\n(SP-LE)", fontsize=20)

    handles = [
        plt.Line2D([], [], color="black", lw=2, label="5–95% Whiskers"),
        plt.Line2D([], [], color="orange", lw=2, label="Median"),
        plt.Line2D([], [], marker="D", color="green", markersize=6, linestyle="None", label="Mean"),
    ]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.02, -0.07), fontsize=18)

    fig.suptitle(f"Monthly Emission Difference (%) (SP-LE) for {num_couples:,} couples of length {length}\n(10k sample)",
                  fontsize=24, fontweight="bold", y=1.0)


    #plot_filename = os.path.join(output_folder, f"boxplot_edge_glo_test_len{length}_paper_JAN.svg")
    #fig.savefig(plot_filename, dpi=300, bbox_inches="tight")
    #plt.close(fig)
    
    print(f"\n=== Stats for length {length} ===")
    print(df["emission_difference"].describe())   
    percentiles_to_report = [0, 5, 25, 50, 75, 95, 100]
    percentile_values = np.percentile(df["emission_difference"].dropna(), percentiles_to_report)
    for p, val in zip(percentiles_to_report, percentile_values):
        print(f"{p}th percentile: {val:.2f}%")
    
    #print(f"Length {length} done. Saved to: {plot_filename}")
    
    '''
    # cumulativa
    data = df["emission_difference"].dropna().values
    sorted_data = np.sort(data)
    cdf = np.arange(1, len(sorted_data)+1) / len(sorted_data)
    percentiles_to_mark = [5, 25, 50, 75, 95, 100]
    bins = np.percentile(data, percentiles_to_mark)

    plt.figure(figsize=(10, 6))
    plt.step(sorted_data, cdf, where="post", label="Empirical CDF", color="blue")

    # Optional: draw percentiles, but be cautious with small n
    for perc, val in zip(percentiles_to_mark, bins):
        plt.axvline(val, linestyle='--', alpha=0.7, label=f"{perc}° perc = {val:.2f}%")

    plt.title(f"CDF of Emission Difference (%) - Length {length}")
    plt.xlabel("Emission Difference (%) (SP - LE)")
    plt.ylabel("Cumulative Probability")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="lower right", fontsize=9)

    cdf_path = os.path.join(output_folder, f"10k_cdf_emission_diff_len{length}.png")
    plt.savefig(cdf_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"CDF plot saved: {cdf_path}")
    print(len(data))  # or print(sorted_data)
    '''