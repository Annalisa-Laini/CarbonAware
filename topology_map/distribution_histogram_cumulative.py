import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def load_pathlengths(csv_path):
    df = pd.read_csv(csv_path, header=None, names=["Node1", "Node2", "PathLength"], low_memory=False)
    df["PathLength"] = pd.to_numeric(df["PathLength"], errors="coerce")
    df = df.dropna(subset=["PathLength"])
    df["PathLength"] = df["PathLength"].astype(int)
    return df["PathLength"].values

def empirical_cdf(lengths):
    # lengths: 1D array-like of ints
    x = np.sort(lengths)
    y = np.arange(1, len(x) + 1) / len(x)
    return x, y

# ----------------------------
# Paths to your 500k samples
# ----------------------------
SP_500K = r"data\test\sampled_path_lengths_SP_500k_pops_w.csv"
LE_500K = r"data\test\sampled_path_lengths_LE_500k_pops_w.csv"

sp = load_pathlengths(SP_500K)
le = load_pathlengths(LE_500K)

print(f"SP rows: {len(sp)} | min={sp.min()} max={sp.max()}")
print(f"LE rows: {len(le)} | min={le.min()} max={le.max()}")

x_sp, y_sp = empirical_cdf(sp)
x_le, y_le = empirical_cdf(le)

plt.figure(figsize=(10, 6))

# step plots are standard for empirical CDFs
plt.step(x_sp, y_sp, where="post", linewidth=2, label="SP (500k)", color="blue")
plt.step(x_le, y_le, where="post", linewidth=2, label="LE (500k)", color="green")

plt.title("CDF of path length (500k sample): SP vs LE")
plt.xlabel("Path Length")
plt.ylabel("Cumulative probability  P(PathLength ≤ L)")
plt.ylim(0, 1.01)
plt.grid(True, linestyle="--", alpha=0.6)
plt.legend()

OUT = r"topology_map\plots\distribution_plots\cdf_pathlength_500k_SP_vs_LE.png"
plt.savefig(OUT, dpi=300, bbox_inches="tight")
plt.show()

def summarize(name, arr):
    arr = np.asarray(arr)
    print(name,
          "n=", len(arr),
          "mean=", arr.mean(),
          "median=", np.median(arr),
          "p90=", np.quantile(arr, 0.90),
          "p99=", np.quantile(arr, 0.99),
          "max=", arr.max())

summarize("SP", sp)
summarize("LE", le)

