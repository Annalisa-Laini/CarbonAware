import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import make_interp_spline

# Load and clean data
df = pd.read_csv(r"data\server\sampled_path_lengths_SP_250k_pops_w_novalidity.csv", header=None, names=["Node1", "Node2", "PathLength"], low_memory=False)
df["PathLength"] = pd.to_numeric(df["PathLength"], errors="coerce")
df = df.dropna(subset=["PathLength"])
df["PathLength"] = df["PathLength"].astype(int)
print(f"Number of rows in df: {len(df)}")


# Calculate counts per integer PathLength
counts = df["PathLength"].value_counts().sort_index()
x = counts.index.values
y = counts.values

# Normalize to density (area under bars = 1)
density = y / y.sum()

plt.figure(figsize=(10, 6))

# Bars with width 1, no gaps
plt.bar(x, density, width=1.0, color="skyblue", edgecolor="black", align='center')
for xi, di in zip(x, density):
    plt.text(xi, di + 0.01, f"{di:.3f}", ha='center', va='bottom', fontsize=14, rotation=0)

plt.title("Path length density for 250k couples (IPv4 weight, SP distribution, no validity constraints)", fontsize=19)
# plt.title("Path length density for 500k couples (no weights, SP distribution)")
plt.xlabel("Path Length",fontsize=17)
plt.ylabel("Density",fontsize=17)
plt.ylim(0, 1.05)  # y max slightly above 1
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.savefig(r"topology_map\plots\distribution_plots\pop_dist_250k_w_SP_novalidity.png", dpi=300, bbox_inches='tight')

dist_table = pd.DataFrame({
    "PathLength": x,
    "Count": y,
    "Density": density,
    "Percent": density * 100
})

print("\n=== Path Length Distribution ===")
for _, row in dist_table.iterrows():
    print(f"Length {int(row['PathLength'])} = {row['Percent']:.4f}% (count={int(row['Count'])})")