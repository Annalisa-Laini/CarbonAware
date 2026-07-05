import json

POPS_FILE = "AS_pops.json"
NODES_FILE = r"data\merged_nodes.jsonl"
OUTPUT_FILE = "as_pops_with_coords.json"
with open(POPS_FILE, "r") as f:
    as_pops = json.load(f)

needed = set()
for asn, regions in as_pops.items():
    for region_code in regions:
        needed.add((asn, region_code))

as_pops_with_coords = {
    asn: {
        region: {
            "count": count
        } for region, count in regions.items()
    } for asn, regions in as_pops.items()
}

with open(NODES_FILE, "r") as f:
    for line in f:
        if not needed:
            break 

        try:
            node = json.loads(line)
        except json.JSONDecodeError:
            continue

        node_asn = node.get("as_number", "").strip()
        country = node.get("country", "").strip().upper()
        region = node.get("region")
        lat = node.get("lat")
        lon = node.get("lon")

        if not node_asn or lat is None or lon is None:
            continue

        region = region.strip().upper() if region else ""
        node_region_code = f"{country}-" if region == "" else f"{country}-{region}"

        pair = (node_asn, node_region_code)
        if pair in needed:
            as_pops_with_coords[node_asn][node_region_code]["lat"] = round(lat, 5)
            as_pops_with_coords[node_asn][node_region_code]["lon"] = round(lon, 5)
            needed.remove(pair)

with open(OUTPUT_FILE, "w") as out:
    json.dump(as_pops_with_coords, out, indent=2)

print(f"[✓] Saved enriched AS PoPs with coordinates to: {OUTPUT_FILE}")
