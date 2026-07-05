import pandas as pd
import matplotlib.pyplot as plt
import os

df = pd.read_csv(r"data\data\as_criticality_from_pops.csv")

out_dir = r"topology_map\plots\as_criticality"
os.makedirs(out_dir, exist_ok=True)

TOP = 16
df_top = df.head(TOP)

def human_format(num):
    num = float(num)
    if abs(num) >= 1_000_000_000:
        return f"{num/1_000_000_000:.2f}B"
    elif abs(num) >= 1_000_000:
        return f"{num/1_000_000:.2f}M"
    elif abs(num) >= 1_000:
        return f"{num/1_000:.2f}K"
    else:
        return f"{num:.2f}"


def add_labels(ax, rotation=0, fontsize=9):
    """Add readable value labels on top of bars."""
    for p in ax.patches:
        height = p.get_height()
        label = human_format(height)
        ax.annotate(label,
                    (p.get_x() + p.get_width() / 2, height),
                    ha='center', va='bottom',
                    rotation=0,
                    fontsize=fontsize)
# raw

fig, axes = plt.subplots(3,1, figsize=(18, 12), sharey=False)
plt.suptitle("Annual Criticality (Raw Values)", fontsize=18)

# TOTAL
axes[0].bar(df_top["AS"].astype(str), df_top["criticality_annual"], color='gray')
axes[0].set_title("Total Criticality")
axes[0].set_xlabel("AS")
axes[0].set_ylabel("Annual Criticality (raw)")
axes[0].tick_params(axis='x', rotation=90)
add_labels(axes[0], rotation=90)

# SP
axes[1].bar(df_top["AS"].astype(str), df_top["criticality_annual_SP"], color='tab:blue')
axes[1].set_title("SP Criticality")
axes[1].set_xlabel("AS")
axes[1].tick_params(axis='x', rotation=90)
add_labels(axes[1], rotation=90)

# LE
axes[2].bar(df_top["AS"].astype(str), df_top["criticality_annual_LE"], color='green')
axes[2].set_title("LE Criticality")
axes[2].set_xlabel("AS")
axes[2].tick_params(axis='x', rotation=90)
add_labels(axes[2], rotation=90)

plt.tight_layout(rect=[0, 0, 1, 0.95])

raw_path = os.path.join(out_dir, "criticality_annual_raw.png")
plt.savefig(raw_path, dpi=300, bbox_inches='tight')
plt.close()

print("Saved:", raw_path)


# norm

fig, axes = plt.subplots(3,1, figsize=(19,12), sharey=True)
plt.suptitle("Criticality Normalized (0–100)", fontsize=18)

# TOTAL INDEX
axes[0].bar(df_top["AS"].astype(str), df_top["criticality_index"], color='gray')
axes[0].set_title("Total Index", fontsize=12)
axes[0].set_xlabel("AS number", fontsize=12)
axes[0].set_ylabel("Index (0–100)",fontsize=12)
axes[0].tick_params(axis='x', rotation=0, labelsize=12)
add_labels(axes[0],rotation=0, fontsize=12)

# SP INDEX
axes[1].bar(df_top["AS"].astype(str), df_top["criticality_index_SP"], color='tab:blue')
axes[1].set_title("SP Index", fontsize=12)
axes[1].set_xlabel("AS number", fontsize=12)
axes[1].tick_params(axis='x', rotation=0, labelsize=12)
add_labels(axes[1],rotation=0,  fontsize=12)

# LE INDEX
axes[2].bar(df_top["AS"].astype(str), df_top["criticality_index_LE"],color='green')
axes[2].set_title("LE Index",fontsize=12 )
axes[2].set_xlabel("AS number", fontsize=12)
axes[2].tick_params(axis='x', rotation=0, labelsize=12)
add_labels(axes[2], rotation=0,fontsize=12 )

plt.tight_layout(rect=[0, 0, 1, 0.95])

index_path = os.path.join(out_dir, "criticality_annual_index.png")
plt.savefig(index_path, dpi=300, bbox_inches='tight')
plt.close()

print("Saved:", index_path)

# share per AS

df["SP_share"] = df["criticality_annual_SP"] / df["criticality_annual"]
df["LE_share"] = df["criticality_annual_LE"] / df["criticality_annual"]

df_top = df.head(TOP).copy()
as_labels = df_top["AS"].astype(str)

fig, ax = plt.subplots(figsize=(12, 6))
plt.title("Share of Criticality per AS (SP vs LE)")

sp_bars = ax.bar(as_labels, df_top["SP_share"], label="SP share", color='tab:blue')
le_bars = ax.bar(as_labels, df_top["LE_share"], bottom=df_top["SP_share"], label="LE share", color = 'green')

ax.set_xlabel("AS")
ax.set_ylabel("Share of annual criticality")
ax.set_ylim(0, 1.05) 
ax.tick_params(axis='x', rotation=45)
ax.legend()

'''
df["SP_share"] = df["criticality_annual_SP"] / df["criticality_annual"]
df["LE_share"] = df["criticality_annual_LE"] / df["criticality_annual"]

'''
def add_share_labels(bars):
    for p in bars:
        height = p.get_height()
        if height <= 0:
            continue
        x = p.get_x() + p.get_width() / 2
        y = p.get_y() + height / 2
        ax.annotate(f"{height*100:.1f}%",
                    (x, y),
                    ha='center', va='center',
                    rotation=90,
                    fontsize=8)

add_share_labels(sp_bars)
add_share_labels(le_bars)

plt.tight_layout()

shares_path = os.path.join(out_dir, "criticality_SP_LE_shares_stacked.png")
plt.savefig(shares_path, dpi=300, bbox_inches='tight')
plt.close()

print("Saved:", shares_path)
