import os
import csv
import pickle
import re
import bz2
import gzip
import ipaddress
import numpy as np
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor

POPS_PKL      = r"data\data\pickle_graphs\pops_2023-05-10.pkl"
GRAPH_TS_KEY  = "2023-05-10 12:00:00"
PFX2AS_FILE   = r"topology_map\data\routeviews-rv2-20240101-1200.pfx2as"

USE_WEIGHTED  = True   # True = IPv4-AS weighted (no PoP split, same as your code); False = uniform
BATCH_SIZE    = 30_000
TARGET_SAMPLE_COUNT = 650_000   # counts ATTEMPTS (same semantics as your old script)
MAX_WORKERS   = 12  # use most cores
MAP_CHUNKSZ   = 2048   # bigger task chunks -> fewer IPC calls
CAND_MULTIPLIER = 4    # oversample factor for dedup/self-filter

OUTPUT_FILE       = ("sampled_path_lengths_SP_500k_pops_w.csv" if USE_WEIGHTED
                     else "sampled_path_lengths_SP_500k_pops_nw.csv")
SEEN_SAMPLES_FILE = ("seen_samples_pops_SP_w_ids.pkl" if USE_WEIGHTED else "seen_samples_pops_nw_ids.pkl")

_ASN_RE = re.compile(r"\d+")

def open_maybe_compressed(path: str):
    if path.endswith(".bz2"):
        return bz2.open(path, "rt", encoding="latin-1", errors="ignore")
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="latin-1", errors="ignore")
    return open(path, "r", encoding="latin-1", errors="ignore")

def parse_pfx2as_ipv4_counts(pfx2as_path: str) -> dict[int, int]:
    """Return {ASN -> total IPv4 addresses} from pfx2as (3-col or CIDR formats)."""
    as_ipv4: dict[int, int] = {}
    with open_maybe_compressed(pfx2as_path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            net = None
            as_field = None
            if len(parts) >= 3 and "." in parts[0] and parts[1].isdigit():
                ip = parts[0]
                try:
                    mlen = int(parts[1])
                except ValueError:
                    mlen = None
                if mlen is not None and 0 <= mlen <= 32:
                    try:
                        net = ipaddress.ip_network(f"{ip}/{mlen}", strict=False)
                        as_field = parts[2]
                    except ValueError:
                        net = None
    
            if net is None and len(parts) >= 2 and "/" in parts[0]:
                try:
                    net = ipaddress.ip_network(parts[0], strict=False)
                    as_field = parts[1]
                except ValueError:
                    net = None
            if net is None or net.version != 4:
                continue
            nums = _ASN_RE.findall(as_field if as_field is not None else " ".join(parts[1:]))
            if not nums:
                continue
            asn = int(nums[-1])
            as_ipv4[asn] = as_ipv4.get(asn, 0) + net.num_addresses
    return as_ipv4

def node_asn(n):
    """Extract leading integer ASN from PoP labels like '1299-SE-IDF' or int."""
    s = str(n)
    num = []
    for ch in s:
        if ch.isdigit(): num.append(ch)
        else: break
    return int("".join(num)) if num else None

def count_csv_rows(path):
    if not os.path.exists(path):
        return 0
    with open(path, newline="") as f:
        return max(0, sum(1 for _ in f) - 1)  
    
def pack_pair(uid: int, vid: int) -> int:
    return (uid << 32) | (vid & 0xFFFFFFFF)

with open(POPS_PKL, "rb") as f:
    hourly_graphs = pickle.load(f)
graph = pickle.loads(hourly_graphs[GRAPH_TS_KEY])
graph_bytes = pickle.dumps(graph, protocol=pickle.HIGHEST_PROTOCOL)  

as_ipv4_counts = parse_pfx2as_ipv4_counts(PFX2AS_FILE)
if not as_ipv4_counts or sum(as_ipv4_counts.values()) == 0:
    raise SystemExit("Parsed zero IPv4 addresses. Check path/format/compression.")
total_ipv4 = sum(as_ipv4_counts.values())
as_ipv4_fraction = {asn: v / total_ipv4 for asn, v in as_ipv4_counts.items() if v > 0}

all_nodes = list(graph.graph.nodes)
node2id = {}
id2node = []
weights = []

if USE_WEIGHTED:
    for n in all_nodes:
        w = as_ipv4_fraction.get(node_asn(n), 0.0)
        if w > 0.0:
            node2id[n] = len(id2node)
            id2node.append(n)
            weights.append(w)
else:
    for n in all_nodes:
        node2id[n] = len(id2node)
        id2node.append(n)

if not id2node:
    raise RuntimeError("No valid PoP nodes to sample from; check graph labels and IPv4 data.")

N = len(id2node)
if USE_WEIGHTED:
    weights_np = np.array(weights, dtype=np.float64)
    weights_np /= weights_np.sum()  
else:
    weights_np = None

_GRAPH = None
def _init_worker(graph_bytes_param: bytes):
    global _GRAPH
    _GRAPH = pickle.loads(graph_bytes_param)

def compute_path_length(pair):
    """Use your graph.find_shortest_valid_path for a single pair."""
    src, dst = pair
    try:
        path = _GRAPH.find_shortest_valid_path(src, dst)
        if path:
            return (src, dst, len(path) - 1)
    except Exception as e:
        # optional: print(f"Error on {src}->{dst}: {e}")
        pass
    return None

if __name__ == '__main__':
    rng = np.random.default_rng(42)

    output_file = OUTPUT_FILE
    seen_samples_file = SEEN_SAMPLES_FILE

    seen: set[int] = set()
    loaded_from_pkl = False
    if os.path.exists(seen_samples_file):
        try:
            with open(seen_samples_file, "rb") as sf:
                obj = pickle.load(sf)
            if isinstance(obj, set) and (len(obj) == 0 or isinstance(next(iter(obj)), int)):
                seen = obj 
            elif isinstance(obj, set) and (len(obj) == 0 or isinstance(next(iter(obj)), tuple)):
                for u, v in obj:
                    if u in node2id and v in node2id:
                        seen.add(pack_pair(node2id[u], node2id[v]))
            loaded_from_pkl = True
            print(f"Loaded {len(seen)} seen pairs.")
        except Exception as e:
            print(f"Warning: failed to load {seen_samples_file} ({e}); starting fresh.")

    csv_count = count_csv_rows(output_file)
    if not os.path.exists(output_file) or csv_count == 0:
        with open(output_file, "w", newline="") as f:
            csv.writer(f).writerow(["source_as", "target_as", "path_length"])
        csv_count = 0

    total_samples = max(csv_count, len(seen))  
    print(f"Resuming from {total_samples} attempts…  Nodes={N}  Workers={MAX_WORKERS}")

    with ProcessPoolExecutor(
        max_workers=MAX_WORKERS,
        initializer=_init_worker,
        initargs=(graph_bytes,)
    ) as ex:

        try:
            while total_samples < TARGET_SAMPLE_COUNT:
                batch_ids = []
                while len(batch_ids) < BATCH_SIZE:
                    M = max(BATCH_SIZE - len(batch_ids), 1) * CAND_MULTIPLIER
                    if USE_WEIGHTED:
                        idx = np.arange(N)
                        u_ids = rng.choice(idx, size=M, replace=True, p=weights_np)
                        v_ids = rng.choice(idx, size=M, replace=True, p=weights_np)
                    else:
                        u_ids = rng.integers(0, N, size=M, endpoint=False)
                        v_ids = rng.integers(0, N, size=M, endpoint=False)
                    for ui, vi in zip(u_ids, v_ids):
                        ui = int(ui); vi = int(vi)
                        if ui == vi:
                            continue
                        packed = pack_pair(ui, vi)  
                        if packed in seen:
                            continue
                        seen.add(packed)
                        batch_ids.append((ui, vi))
                        if len(batch_ids) >= BATCH_SIZE:
                            break

                batch = [(id2node[ui], id2node[vi]) for ui, vi in batch_ids]

                results = []
                for r in tqdm(ex.map(compute_path_length, batch, chunksize=MAP_CHUNKSZ),
                              total=len(batch),
                              desc=f"Batch {1 + total_samples // max(1, BATCH_SIZE)}"):
                    if r is not None:
                        results.append(r)

                if results:
                    with open(output_file, "a", newline="") as f:
                        csv.writer(f).writerows(results)
                
                with open(seen_samples_file, "wb") as sf:
                    pickle.dump(seen, sf, protocol=pickle.HIGHEST_PROTOCOL)

                total_samples += len(batch)
                print(f"Completed {total_samples}/{TARGET_SAMPLE_COUNT} attempts.")

        finally:
            with open(seen_samples_file, "wb") as sf:
                pickle.dump(seen, sf, protocol=pickle.HIGHEST_PROTOCOL)
            print(f"Final attempts on disk: {total_samples}")
