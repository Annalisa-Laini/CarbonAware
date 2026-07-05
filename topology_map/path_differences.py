import os
import re
import csv
import shelve
import tempfile
import pandas as pd
from contextlib import closing

def extract_key(filename: str):
    m = re.match(r'^(?:SP_)?pop_EU_global_(.+)\.csv$', filename)
    return m.group(1) if m else None

def parse_path_to_list(path_str: str):
    """Normalize path string to a list of nodes; accepts 'a->b->c' or 'a,b,c'."""
    if '->' in path_str:
        parts = [p.strip() for p in path_str.split('->')]
    elif ',' in path_str:
        parts = [p.strip() for p in path_str.split(',')]
    else:
        # single-hop or already normalized
        parts = [p.strip() for p in path_str.split()]
        if len(parts) == 1 and ',' in path_str:
            parts = [p.strip() for p in path_str.split(',')]
    return parts

def build_emissions_shelve(emissions_csv: str, shelf_path: str):
    """Stream the emissions-based CSV and persist (source,target)->(path_list, emissions) on disk."""
    with closing(shelve.open(shelf_path, flag='n')) as db:
        usecols = ["source_as", "target_as", "path", "emissions"]
        for chunk in pd.read_csv(emissions_csv, usecols=usecols, chunksize=200_000):
            for _, row in chunk.iterrows():
                s = str(row["source_as"])
                t = str(row["target_as"])
                p = parse_path_to_list(str(row["path"]))
                e = None
                try:
                    e = float(row["emissions"])
                except Exception:
                    e = None
                db[f"{s}|{t}"] = (p, e)

def stream_compare_to_csv(hops_csv: str, shelf_path: str, out_csv: str):
    """Stream the hops-based CSV, compare against shelved emissions data, append diffs to out_csv."""
    write_header = not os.path.exists(out_csv)
    out_fh = open(out_csv, 'a', newline='', encoding='utf-8')
    writer = csv.DictWriter(out_fh, fieldnames=[
        "source_as", "target_as",
        "emissions_path", "hops_path",
        "emissions_path_length", "hops_path_length",
        "shortest_path_emissions", "lowest_path_emissions"
    ])
    if write_header:
        writer.writeheader()

    with closing(shelve.open(shelf_path, flag='r')) as db:
        usecols = ["source_as", "target_as", "path", "emissions"]
        for chunk in pd.read_csv(hops_csv, usecols=usecols, chunksize=200_000):
            # Iterate rows and compare
            for _, row in chunk.iterrows():
                s = str(row["source_as"])
                t = str(row["target_as"])
                key = f"{s}|{t}"
                if key not in db:
                    continue  # no pair in emissions file
                em_path, em_emiss = db[key]

                hops_path = parse_path_to_list(str(row["path"]))
                # Only store if paths differ
                if em_path != hops_path:
                    try:
                        hops_emiss = float(row["emissions"])
                    except Exception:
                        hops_emiss = None

                    writer.writerow({
                        "source_as": s,
                        "target_as": t,
                        "emissions_path": "->".join(em_path),
                        "hops_path": "->".join(hops_path),
                        "emissions_path_length": max(len(em_path) - 1, 0),
                        "hops_path_length": max(len(hops_path) - 1, 0),
                        "shortest_path_emissions": hops_emiss,   # emissions for shortest (hops) file
                        "lowest_path_emissions": em_emiss        # emissions for lowest-emissions file
                    })
    out_fh.close()

def compare_two_csvs_streaming(file_emissions: str, file_hops: str, out_csv: str):
    """Orchestrates on-disk index + streaming comparison to write differences to CSV."""
    with tempfile.TemporaryDirectory() as tmpdir:
        shelf_path = os.path.join(tmpdir, "emissions_index")
        
        build_emissions_shelve(file_emissions, shelf_path)
        
        stream_compare_to_csv(file_hops, shelf_path, out_csv)

def batch_compare_streaming(folder_emissions: str, folder_hops: str, output_folder: str):
    os.makedirs(output_folder, exist_ok=True)

    emissions_files = {
        extract_key(f): f for f in os.listdir(folder_emissions)
        if f.startswith("pop_EU_global_") and f.endswith(".csv")
    }
    hops_files = {
        extract_key(f): f for f in os.listdir(folder_hops)
        if f.startswith("SP_pop_EU_global_") and f.endswith(".csv")
    }

    common = sorted(set(emissions_files.keys()) & set(hops_files.keys()))
    if not common:
        print("No matching files found between the two folders.")
        return

    for key in common:
        f_em = os.path.join(folder_emissions, emissions_files[key])
        f_hp = os.path.join(folder_hops,      hops_files[key])
        out  = os.path.join(output_folder,    f"diff_{key}.csv")

        if os.path.exists(out):
            os.remove(out)

        compare_two_csvs_streaming(f_em, f_hp, out)
        print(f"Saved: {out}")

if __name__ == "__main__":
    folder_emissions = r"data\data"
    folder_hops      = r"data\data"
    output_folder    = r"data\data\pop diffs"

    batch_compare_streaming(folder_emissions, folder_hops, output_folder)
