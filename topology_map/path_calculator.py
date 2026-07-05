import os
import sys
import csv
import json
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any, Tuple

from networkx_graph import ASGraph  
MAX_WORKERS = 10 
COUNTRIES_FILE         = r"topology_map\data\countries.txt"
GEO_JSON_PATH          = r"topology_map\data\geolocation_pop.json"
ISO_MAPPING_PATH       = r"topology_map\data\iso.json"
EMISSIONS_FOLDER_PATH  = r"energy_graphs\data"
RELATIONSHIPS_FILE     = r"topology_map\data\20240101.as-rel2.txt"
OUTPUT_FOLDER          = r"."

CSV_HEADER = ["source_as", "target_as", "path_length", "emissions", "path"]

def ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)

def append_paths_for_source_to_csv(graph: ASGraph, source_as: Any, target_paths: Dict[Any, List[Any]], filename: str) -> None:
    """
    Appends all rows for a single source to CSV (opens, writes, closes).
    This keeps memory low and ensures progress is flushed per source.
    """
    if not target_paths:
        return
    ensure_parent(filename)
    file_exists = os.path.exists(filename)
    with open(filename, mode="a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(CSV_HEADER)
        for target_as, path in target_paths.items():
            # emissions sum is based on node costs along the path
            emissions_sum = sum(graph.cost(node) for node in path)
            w.writerow([
                source_as,
                target_as,
                (len(path) - 1),
                emissions_sum,
                " -> ".join(str(node) for node in path),
            ])
        f.flush()
        os.fsync(f.fileno())

def read_done_sources_from_csv(filename: str) -> set:
    """
    Reads unique source_as values from an existing (possibly partial) CSV without loading everything into memory.
    Tolerates truncated/partial lines.
    """
    done = set()
    if not os.path.exists(filename):
        return done
    try:
        with open(filename, mode="r", encoding="utf-8", newline="") as f:
            r = csv.reader(f)
            header = next(r, None)
            if header is None:
                return done
            try:
                idx = header.index("source_as")
            except ValueError:
                idx = 0
            for row in r:
                if not row or len(row) <= idx:
                    continue
                done.add(row[idx])
    except Exception:
        
        pass
    return done

def worker_process_sources(args):
    (geo_json_path, iso_mapping_path, emissions_folder_path, relationships_file,
     countries, specific_datetime, as_to_country, as_to_region, out_tmp_path, source_list, worker_log_path) = args

    done_sources = read_done_sources_from_csv(out_tmp_path)

    try:
        graph = ASGraph(
            data_file=geo_json_path,
            relationships_file=relationships_file,
            emissions_folder_path=emissions_folder_path,
            countries=countries,
            iso_mapping_file=iso_mapping_path,
            as_to_country=as_to_country,
            as_to_region=as_to_region,
            as_to_iso_code={}
        )
        graph.as_to_country = as_to_country
        graph.as_to_region  = as_to_region
        graph.node_costs    = {}

        graph.add_nodes()
        graph.add_edges()
        graph.add_emission_data(specific_datetime)
    except Exception as e:
        _append_log(worker_log_path, f"[FATAL] Graph build failed: {e}")
        raise

    processed = 0
    for src in source_list:
        if str(src) in done_sources:
            continue
        try:
            valid_paths = graph.find_all_valid_shortest_paths(src)
            if valid_paths:
                append_paths_for_source_to_csv(graph, src, valid_paths, out_tmp_path)
            processed += 1
        except Exception as e:
            _append_log(worker_log_path, f"[WARN] Source {src} failed: {e}")

    return processed  # for progress tally

def _append_log(log_path: str, msg: str) -> None:
    ensure_parent(log_path)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as lf:
        lf.write(f"{ts} {msg}\n")

def concat_csvs(temp_paths: List[str], final_path: str) -> None:
    ensure_parent(final_path)
    with open(final_path, "w", encoding="utf-8", newline="") as fout:
        wrote_header = False
        for tp in temp_paths:
            if not os.path.exists(tp):
                continue
            with open(tp, "r", encoding="utf-8", newline="") as fin:
                reader = csv.reader(fin)
                try:
                    header = next(reader)
                except StopIteration:
                    continue
                if not wrote_header:
                    writer = csv.writer(fout)
                    writer.writerow(header)
                    wrote_header = True
                # write remaining rows
                writer = csv.writer(fout)
                for row in reader:
                    if row:
                        writer.writerow(row)

def make_run_id(date: str, time_str: str) -> str:
    return f"sp_run_{date.replace('-', '')}_{time_str.replace(':', '')}"

def checkpoint_path(run_dir: str) -> str:
    return os.path.join(run_dir, "config.json")

def load_or_create_checkpoint(run_dir: str,
                              final_csv: str,
                              source_nodes: List[Any],
                              time_str: str,
                              date: str) -> Dict[str, Any]:
    """
    If a checkpoint exists, reuse its chunking and temp paths.
    Otherwise create a new checkpoint with deterministic chunking.
    """
    cfg_path = checkpoint_path(run_dir)
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg

    n = len(source_nodes)
    cpu = os.cpu_count() or 1
    W = min(MAX_WORKERS, max(1, cpu))

    chunks = [source_nodes[i::W] for i in range(W)]
    temp_paths = [os.path.join(run_dir, f"tmp_worker_{i}_{time_str[:2]}.csv") for i in range(W)]
    log_paths  = [os.path.join(run_dir, f"worker_{i}.log") for i in range(W)]

    cfg = {
        "W": W,
        "n": n,
        "date": date,
        "time_str": time_str,
        "final_csv": final_csv,
        "temp_paths": temp_paths,
        "log_paths": log_paths,
        "chunks": [[str(x) for x in chunk] for chunk in chunks],
    }
    Path(run_dir).mkdir(parents=True, exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    return cfg

def chunk_complete(temp_csv: str, expected_sources: List[str]) -> bool:
    done = read_done_sources_from_csv(temp_csv)
    return all(str(s) in done for s in expected_sources)

def compute_progress(temp_paths: List[str], chunks: List[List[str]]) -> Tuple[int, int]:
    total = sum(len(ch) for ch in chunks)
    done_sources = 0
    for tp, ch in zip(temp_paths, chunks):
        done_sources += len(read_done_sources_from_csv(tp) & set(map(str, ch)))
    return done_sources, total

def main():
    with open(COUNTRIES_FILE, "r", encoding="utf-8") as file:
        content = file.read()
    countries = [c.strip().strip('"') for c in content.split(",") if c.strip()]

    with open(GEO_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    as_to_country = {entry["pop"]: entry["country"] for entry in data}
    as_to_region  = {entry["pop"]: entry["region"]  for entry in data}

    target_dates   = ["2023-07-19"]
    time_intervals = ["12:00:00"]

    Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

    for date in target_dates:
        for time_str in time_intervals:
            specific_datetime = f"{date} {time_str}"
            month_abbr = datetime.strptime(date, "%Y-%m-%d").strftime("%b")
            final_csv  = os.path.join(OUTPUT_FOLDER, f"pop_SP_world_{month_abbr}_19_hour{time_str[:2]}.csv")
            run_id     = make_run_id(date, time_str)
            run_dir    = os.path.join(OUTPUT_FOLDER, run_id)
            print(f"\n[Run] {specific_datetime}  (run_dir: {run_dir})")

            g0 = ASGraph(
                data_file=GEO_JSON_PATH,
                relationships_file=RELATIONSHIPS_FILE,
                emissions_folder_path=EMISSIONS_FOLDER_PATH,
                countries=countries,
                iso_mapping_file=ISO_MAPPING_PATH,
                as_to_country=as_to_country,
                as_to_region=as_to_region,
                as_to_iso_code={}
            )
            g0.as_to_country = as_to_country
            g0.as_to_region  = as_to_region
            g0.node_costs    = {}
            g0.add_nodes()
            g0.add_edges()
            source_nodes = list(g0.graph.nodes)

            # Prepare / load checkpoint (keeps chunking stable across restarts)
            cfg        = load_or_create_checkpoint(run_dir, final_csv, source_nodes, time_str, date)
            W          = cfg["W"]
            temp_paths = cfg["temp_paths"]
            log_paths  = cfg["log_paths"]
            chunks     = cfg["chunks"]  # list of list of str
            n          = cfg["n"]

            # If final already exists and all chunks are complete, we’re done
            all_done = all(chunk_complete(tp, ch) for tp, ch in zip(temp_paths, chunks))
            if all_done and os.path.exists(final_csv):
                print(f"[OK] All chunks complete and final CSV already present: {final_csv}")
                continue

            # Launch workers (each resumes its own temp CSV)
            futures = []
            with ProcessPoolExecutor(max_workers=W) as ex:
                for i, (chunk, tmp, logp) in enumerate(zip(chunks, temp_paths, log_paths)):
                    # Skip entirely if this chunk is already complete
                    if chunk_complete(tmp, chunk):
                        continue
                    # Convert chunk AS list back to original type if needed
                    # Here we keep them as str consistently, because we compare as str elsewhere.
                    args = (GEO_JSON_PATH, ISO_MAPPING_PATH, EMISSIONS_FOLDER_PATH, RELATIONSHIPS_FILE,
                            countries, specific_datetime, as_to_country, as_to_region, tmp, chunk, logp)
                    futures.append(ex.submit(worker_process_sources, args))

                # Progress logging
                for fut in as_completed(futures):
                    try:
                        fut.result()
                    except Exception as e:
                        print("[Worker failed]", e)

            # Post-run: compute progress and finalize if ready
            done_sources, total_sources = compute_progress(temp_paths, chunks)
            print(f"[Progress] {done_sources}/{total_sources} sources processed")

            # Only concatenate when every chunk is complete
            all_done = all(chunk_complete(tp, ch) for tp, ch in zip(temp_paths, chunks))
            if all_done:
                print("[Stitch] All chunks complete; concatenating temp CSVs into final output...")
                concat_csvs(temp_paths, final_csv)
                print(f"[Saved] {final_csv}")
            else:
                print("[Resume Ready] Some chunks incomplete. Keep run_dir; re-run to resume.")

    print("Processing complete.")

if __name__ == "__main__":
    try:
        from multiprocessing import freeze_support
        freeze_support()
    except Exception:
        pass
    main()
