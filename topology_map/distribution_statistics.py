import os
from pathlib import Path
import pandas as pd
import numpy as np

BASE_DIR = Path(r"data\test")  # folder containing the CSVs
ALGOS    = ["LE", "SP"]
SIZES    = ["50k", "100k", "250k", "500k"]
FNAME    = "sampled_path_lengths_{ALG}_{SIZE}_pops_w.csv"  # rest of name stays the same
SUMMARY_OUT = BASE_DIR / "summary_stats_all.csv"

def process_one(csv_path: Path):
    df = pd.read_csv(csv_path, header=None,
                     names=["Node1", "Node2", "PathLength"],
                     dtype=str)
    df["PathLength"] = pd.to_numeric(df["PathLength"], errors="coerce")
    df = df.dropna(subset=["PathLength"])
    df["PathLength"] = df["PathLength"].astype(int)

    mean_path_length   = df["PathLength"].mean()
    median_path_length = df["PathLength"].median()
    max_path_length    = df["PathLength"].max()
    percentile_90      = float(np.percentile(df["PathLength"], 90))

    counts  = df["PathLength"].value_counts().sort_index()
    density = counts / counts.sum()

    return {
        "mean": mean_path_length,
        "median": median_path_length,
        "max": max_path_length,
        "p90": percentile_90,
        "density": density
    }

def main():
    summary_rows = []

    for alg in ALGOS:
        for size in SIZES:
            csv_path = BASE_DIR / FNAME.format(ALG=alg, SIZE=size)
            if not csv_path.exists():
                print(f"[skip] {csv_path} (not found)")
                continue

            print(f"\n=== Processing {csv_path.name} ===")
            res = process_one(csv_path)

            # Print stats
            print(f"Mean path length: {res['mean']:.2f}")
            print(f"Median path length: {res['median']}")
            print(f"Max path length: {res['max']}")
            print(f"90th percentile: {res['p90']:.2f}")

            # Print (and save) density
            print("\nPath Length Density Distribution:")
            for length, prob in res["density"].items():
                print(f"Path Length {length}: {prob:.6f}")

            # Save density next to input file
            density_out = csv_path.with_name(csv_path.stem + "_density.csv")
            res["density"].rename_axis("PathLength").reset_index(name="Density").to_csv(
                density_out, index=False
            )
            print(f"[saved] density -> {density_out}")

            # Collect for summary
            summary_rows.append({
                "algo": alg,
                "size": size,
                "file": csv_path.name,
                "rows": int(res["density"].sum() * res["density"].shape[0]) if not res["density"].empty else 0,
                "mean": res["mean"],
                "median": res["median"],
                "max": res["max"],
                "p90": res["p90"],
            })

    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        summary_df.to_csv(SUMMARY_OUT, index=False)
        print(f"\n[summary saved] {SUMMARY_OUT}")
    else:
        print("\nNo files processed.")

if __name__ == "__main__":
    main()
