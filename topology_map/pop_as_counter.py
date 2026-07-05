import json
from collections import defaultdict

input_file = "AS_regions.json"
output_file = "AS_regions_counter.json"

with open(input_file, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

asn_region_counts = {}

for asn, region_list in raw_data.items():
    region_count = defaultdict(int)
    for region in region_list:
        region_count[region] += 1
    asn_region_counts[asn] = dict(region_count)

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(asn_region_counts, f, indent=2)

