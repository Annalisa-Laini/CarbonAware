import json
INPUT_FILE = "AS_regions_counter.json"
OUTPUT_FILE = "AS_pops.json"
THRESHOLD_RATIO = 0.3  # 30% of max count

with open(INPUT_FILE, "r") as f:
    as_region_data = json.load(f)

as_pops = {}

for asn, region_counts in as_region_data.items():
    max_count = max(region_counts.values())
    threshold = THRESHOLD_RATIO * max_count
    pops = {
        region: count
        for region, count in region_counts.items()
        if count > threshold
    }
    as_pops[asn] = pops

with open(OUTPUT_FILE, "w") as f:
    json.dump(as_pops, f, indent=2)

print(f"Saved PoP data for {len(as_pops)} ASes to: {OUTPUT_FILE}")
