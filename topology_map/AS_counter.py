import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np
import json
from collections import Counter
import matplotlib.ticker as ticker

json_path = r"topology_map\data\geolocation_pop.json"
with open(json_path, "r", encoding="utf-8") as f:
    as_data = json.load(f)

as_to_country = {}
for entry in as_data:
    try:
        asn = int(entry["as_number"])
        country = entry.get("country", "Unknown")
        as_to_country[asn] = country
    except:
        continue

def extract_as_from_token(token: str):
    """
    token is a hop like '14642-CA-BC' or just '14642'.
    Return the ASN as int, or None if not parseable.
    """
    try:
        first = str(token).split("-")[0].strip()
        return int(first)
    except:
        return None

def update_as_counter_from_path(series: pd.Series, counter: Counter):
    """
    Series contains paths like '14642-CA-BC->3356-US-NY->...'
    Count ASNs by extracting the first number from each hop.
    """
    for path in series.dropna():
        hops = [seg.strip() for seg in str(path).split("->") if seg.strip()]
        asns = []
        for h in hops:
            asn = extract_as_from_token(h)
            if asn is not None:
                asns.append(asn)
        counter.update(asns)

total_as_counter_SP = Counter()
total_as_counter_LE = Counter()

lengths = [2,3,4,5,6]

for length in lengths:
    file_LE_1 = fr"data\server\csvs\edges_LE_glo_jan-jun_2_{length}.csv"
    file_LE_2 =fr"data\server\csvs\edges_glo_LE_jul-dec_len{length}.csv"
    file_SP_1 = fr"data\server\csvs\edges_SP_glo_jan-jun_2_{length}.csv"
    file_SP_2 = fr"data\server\csvs\edges_glo_SP_jul-dec_len{length}.csv"

    df_SP_1 = pd.read_csv(file_SP_1, parse_dates=["date"], dayfirst=False)
    df_SP_2 = pd.read_csv(file_SP_2, parse_dates=["date"], dayfirst=False)
    df_LE_1 = pd.read_csv(file_LE_1, parse_dates=["date"], dayfirst=False)
    df_LE_2 = pd.read_csv(file_LE_2, parse_dates=["date"], dayfirst=False)

    df_SP = pd.concat([df_SP_1, df_SP_2], ignore_index=True)
    df_LE = pd.concat([df_LE_1, df_LE_2], ignore_index=True)

    candidate_pairs = [
        ("source_as", "target_as"),      # numeric AS endpoints
        ("source_pop", "target_pop"),    # PoP endpoints
        ("source", "target"),
        ("src_pop", "dst_pop"),
        ("src", "dst"),
    ]
    merge_keys = ["date", "hour"]
    pair = None
    for a, b in candidate_pairs:
        if {a, b}.issubset(df_SP.columns) and {a, b}.issubset(df_LE.columns):
            pair = (a, b)
            break
    if pair is None:
        raise KeyError(
            "Could not find source/target columns to merge on. "
            "Tried: " + ", ".join([f"{a}/{b}" for a, b in candidate_pairs])
        )
    merge_keys += list(pair)

    df = pd.merge(df_SP, df_LE, on=merge_keys, suffixes=("_SP", "_LE"))

    if "emissions_path_SP" not in df.columns or "emissions_path_LE" not in df.columns:
        raise KeyError("Expected 'emissions_path_SP' and 'emissions_path_LE' columns after merge.")

    update_as_counter_from_path(df["emissions_path_SP"], total_as_counter_SP)
    update_as_counter_from_path(df["emissions_path_LE"], total_as_counter_LE)

df_SP_counts = pd.DataFrame(total_as_counter_SP.items(), columns=["AS", "SP_count"])
df_LE_counts = pd.DataFrame(total_as_counter_LE.items(), columns=["AS", "LE_count"])
merged_df = pd.merge(df_SP_counts, df_LE_counts, on="AS", how="outer").fillna(0)


merged_df["SP_count"] = merged_df["SP_count"].astype(int)
merged_df["LE_count"] = merged_df["LE_count"].astype(int)
merged_df["total"] = merged_df["SP_count"] + merged_df["LE_count"]
merged_df["country"] = merged_df["AS"].map(as_to_country).fillna("Unknown")

merged_df = merged_df.sort_values(by="total", ascending=False)

# === Plotting ===
top_n = 30
#threshold = 40_000
#filtered = merged_df[merged_df[["SP_count","LE_count"]].gt(threshold).any(axis=1)]
# gt -> > threshold, any -> returns True if any column in that row is True
#top_merged = filtered
top_merged = merged_df.head(top_n)
x_labels = top_merged.apply(lambda row: f"{row['AS']}", axis=1)
x = np.arange(len(x_labels))
bar_width = 0.4

fig, ax = plt.subplots(figsize=(16, 7))
ax.bar(x - bar_width / 2, top_merged["SP_count"], width=bar_width, color='blue', label="SP")
ax.bar(x + bar_width / 2, top_merged["LE_count"], width=bar_width, color='green', label="LE")


ax.set_title(f"top 30 ASNs by total occurrences across all paths of lengths {lengths}", fontsize=14, fontweight="bold")
#ax.set_title(f"Most Used ASNs Across Paths of Length {lengths} (SP vs LE)", fontsize=14, fontweight="bold")
ax.set_xlabel("AS", fontsize=12)
ax.set_ylabel("Total Count Across Lengths", fontsize=12)
ax.set_xticks(x)
ax.set_yscale('log', base=10)
ax.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=12)
ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{int(x):,}'))
ax.legend()
ax.grid(True, axis='y', linestyle="--", alpha=0.6)

plt.tight_layout()

output_dir = r"topology_map\plots\as_counter"
os.makedirs(output_dir, exist_ok=True)
plot_path = os.path.join(output_dir, f"top30_as_count_len{lengths}.png")
plt.savefig(plot_path, dpi=300)
plt.close()
print(f"Combined plot saved: {plot_path}")
