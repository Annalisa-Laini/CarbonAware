import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np

csv_path  = r"data\data\as_criticality_from_pops.csv"
output_dir = r"topology_map\plots\as_criticality"

top_n = 16                
metric_source = "total"        # "total" | "SP" | "LE"  

df = pd.read_csv(csv_path)

if "criticality_day" not in df.columns:
    raise KeyError("Manca 'criticality_day' nel CSV.")

max_tot = df["criticality_day"].max()
if max_tot == 0 or pd.isna(max_tot):
    df["unified_index_total"] = 0.0
    df["unified_index_SP"]    = 0.0
    df["unified_index_LE"]    = 0.0
else:
    if "criticality_day_SP" not in df.columns or "criticality_day_LE" not in df.columns:
        raise KeyError("Mancano 'criticality_day_SP' o 'criticality_day_LE' nel CSV.")
    df["unified_index_total"] = (df["criticality_day"]    / max_tot) * 100.0
    df["unified_index_SP"]    = (df["criticality_day_SP"] / max_tot) * 100.0
    df["unified_index_LE"]    = (df["criticality_day_LE"] / max_tot) * 100.0

if metric_source == "total":
    metric_col = "unified_index_total"
    ylabel = "Criticality totale (indice unificato 0–100)"
elif metric_source == "SP":
    metric_col = "unified_index_SP"
    ylabel = "Criticality SP (indice unificato 0–100)"
elif metric_source == "LE":
    metric_col = "unified_index_LE"
    ylabel = "Criticality LE (indice unificato 0–100)"
else:
    raise ValueError("metric_source deve essere 'total', 'SP' o 'LE'.")

df_plot = df.sort_values(metric_col, ascending=False).head(top_n).copy()

if "country" in df_plot.columns:
    df_plot["label"] = df_plot.apply(lambda r: f"{int(r['AS'])} ({str(r['country'])})", axis=1)
else:
    df_plot["label"] = df_plot["AS"].astype(int).astype(str)

fig, ax = plt.subplots(figsize=(14, 6))
bars = ax.bar(df_plot["label"], df_plot[metric_col])

ax.margins(y=0.1)

for rect, v in zip(bars, df_plot[metric_col].values):
    ax.text(
        rect.get_x() + rect.get_width()/2,
        rect.get_height(),
        f"{v:.0f}",
        ha="center", va="bottom",
        fontsize=10, rotation=0,
        clip_on=False
    )

title_metric = {"total": "Total (SP+LE)", "SP": "Shortest Path only", "LE": "Lowest Emissions only"}[metric_source]
ax.set_title(f"Top {top_n} AS — {title_metric}")
ax.set_xlabel("AS")
ax.set_ylabel(ylabel)
ax.set_xticks(range(len(df_plot)))
ax.set_xticklabels(df_plot["label"], rotation=45, ha="right")
ax.grid(axis="y", linestyle="--", alpha=0.5)
plt.tight_layout()

os.makedirs(output_dir, exist_ok=True)
out_path = os.path.join(output_dir, f"top16AS.png")
#out_path = os.path.join(output_dir, f"as_criticality_top{top_n}_unified_{metric_source.lower()}.png")
plt.savefig(out_path, dpi=300)
plt.close()
print(f"Plot salvato: {out_path}")
