import json

# === Load API zone definitions ===
with open("topology_map/data/API_zones.txt", "r", encoding="utf-8") as f:
    api_zones = json.load(f)

# === Build region-level ISO mapping ===
updated_mapping = {}

for code, details in api_zones.items():
    # Handle both country and subregion codes (like IN-DL, US-TEX-ERCO)
    if "-" in code:
        parts = code.split("-")
        country = parts[0]
        region = parts[1] if len(parts) == 2 else "-".join(parts[1:])
        region_key = f"{country}-{region}"
    else:
        region_key = code  # Just the country code

    # Create mapping entry
    updated_mapping[region_key] = {
        "iso_code": code,
        "zoneName": details.get("zoneName"),
        "countryName": details.get("countryName", "")
    }

# === Optional: Save to JSON file
with open("updated_iso_mapping_from_api.json", "w") as f:
    json.dump({"regions": updated_mapping}, f, indent=2)

print(f"Generated mapping with {len(updated_mapping)} region codes.")
