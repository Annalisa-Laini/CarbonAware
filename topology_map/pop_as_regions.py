import json

input_file = r"data\merged_nodes.jsonl"
output_file = "AS_regions.json"
batch_size = 100_000

as_to_locations = {}

with open(input_file, "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        try:
            node = json.loads(line)
            asn = str(node["as_number"])
            country = node.get("country")
            region = node.get("region")

            if not country or not region:
                country = country or ""
                region = region or ""


            entry = f"{country}-{region}"
            if asn not in as_to_locations:
                as_to_locations[asn] = []
            as_to_locations[asn].append(entry)

        except Exception:
            continue

        if i % batch_size == 0:
            print(f"✅ Processed {i} lines... Saving batch to disk.")
            with open(output_file, "w", encoding="utf-8") as fout:
                json.dump(as_to_locations, fout, indent=2)

# Final save in case the last batch is smaller than batch_size
with open(output_file, "w", encoding="utf-8") as fout:
    json.dump(as_to_locations, fout, indent=2)

print(f"✅ Done! Final output saved to {output_file}")
