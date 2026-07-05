import json

INPUT_FILE = "as_pops_with_coords.json"
OUTPUT_FILE = "virtual_as_pops.json"

with open(INPUT_FILE, "r") as f:
    as_pops = json.load(f)

virtual_pops = []

for asn, regions in as_pops.items():
    for region_code, data in regions.items():
        country, region = region_code.split("-", 1)  # Split "DE-NW" → "DE", "NW"
        virtual_pops.append({
            "pop": f"{asn}-{region_code}",
            "as_number":asn,
            "country": country,
            "region": region,
            "lat": data["lat"],
            "lon": data["lon"]
        })

with open(OUTPUT_FILE, "w") as out:
    json.dump(virtual_pops, out, indent=2)

print(f"[✓] Saved {len(virtual_pops)} virtual PoPs to {OUTPUT_FILE}")
