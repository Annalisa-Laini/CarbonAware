import os, csv, re, random, math
import pandas as pd
from collections import Counter
from typing import Optional

def compute_as_ipv4_counts_from_pfx2as_plain(path: str) -> dict[int, int]:
    counts: dict[int, int] = {}
    with open(path, "rt", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line or line[0] in "#;":
                continue
            p = line.strip().split()
            if not p: continue
            if "/" in p[0]:
                parts = p[0].split("/", 1)
                if len(parts) != 2 or len(p) < 2: continue
                ip, mask_s = parts[0], parts[1]
                asn_field = p[1]
            else:
                if len(p) < 3: continue
                ip, mask_s, asn_field = p[0], p[1], p[2]
            if ":" in ip:  # IPv6
                continue
            try:
                mask = int(mask_s)
                if not (0 <= mask <= 32): continue
            except ValueError:
                continue
            num = []
            for ch in asn_field:
                if ch.isdigit(): num.append(ch)
                elif num: break
            if not num: continue
            asn = int("".join(num))
            if asn <= 0: continue
            counts[asn] = counts.get(asn, 0) + (1 << (32 - mask))
    return counts

def as_fractions_from_counts(as_ipv4_counts: dict[int,int]) -> dict[int,float]:
    total = sum(as_ipv4_counts.values())
    if total <= 0: raise ValueError("as_ipv4_counts total must be > 0")
    return {int(k): v / total for k, v in as_ipv4_counts.items() if v > 0}

ASN_RE1 = re.compile(r'\bAS\s*(\d{1,10})\b', re.I)
ASN_RE2 = re.compile(r'(?<!\d)(\d{1,10})(?!\d)')

def parse_asn_fast(s: str) -> Optional[int]:
    if not s: return None
    m = ASN_RE1.search(s) or ASN_RE2.search(s)
    return int(m.group(1)) if m else None

def sniff_sep_and_cols(path: str):
    with open(path, 'r', encoding='utf-8', errors='replace', newline='') as f:
        header_line = f.readline()
        data_start = f.tell()
    # delimiter
    try:
        dialect = csv.Sniffer().sniff(header_line, delimiters=[',',';','\t','|'])
        sep = dialect.delimiter
    except Exception:
        sep = ','
    # columns
    cols = next(csv.reader([header_line], delimiter=sep))
    low = {c.lower(): i for i, c in enumerate(cols)}
    def pick(cands):
        for c in cands:
            if c in low: return low[c]
        return None
    i_src = pick(['source_as','src_as','source','src','source_pop','src_pop'])
    i_tgt = pick(['target_as','dst_as','target','dst','target_pop','dst_pop'])
    i_len = pick(['path_length','length','pathlen','path_len','hops','len'])
    if None in (i_src, i_tgt, i_len):
        raise ValueError(f"Missing required columns in header: {cols}")
    return sep, (i_src, i_tgt, i_len), data_start, cols

# build subset via random seeks (approx uniform lines)
def make_random_subset_seek(csv_path: str, out_path: str, target_rows: int,
                            keep_all_columns: bool = False,
                            random_state: int = 65, max_attempts_factor: int = 6) -> None:
    """
    Approximate: picks random byte offsets, grabs next full line.
    Much faster than scanning entire file. Writes a new CSV with either full
    rows or only the 3 needed columns (source_as, target_as, path_length).
    """
    rng = random.Random(random_state)
    sep, (i_src, i_tgt, i_len), data_start, cols = sniff_sep_and_cols(csv_path)
    filesize = os.path.getsize(csv_path)
    seen_offsets = set()
    attempts, max_attempts = 0, max_attempts_factor * target_rows

    # Prepare writer
    if keep_all_columns:
        out_cols = cols
    else:
        out_cols = ['source_as','target_as','path_length']
    with open(out_path, 'w', encoding='utf-8', newline='') as out_f:
        writer = csv.writer(out_f)
        writer.writerow(out_cols)

        with open(csv_path, 'r', encoding='utf-8', errors='replace', newline='') as f:
            while attempts < max_attempts and target_rows > 0:
                attempts += 1
                pos = rng.randrange(data_start, max(data_start+1, filesize-1))
                f.seek(pos)
                f.readline()                
                offset = f.tell()
                line = f.readline()
                if not line:
                    f.seek(data_start)
                    offset = f.tell()
                    line = f.readline()
                    if not line:
                        break
                if offset in seen_offsets:
                    continue
                try:
                    row = next(csv.reader([line], delimiter=sep))
                except Exception:
                    continue
                if max(i_src, i_tgt, i_len) >= len(row):
                    continue

                try:
                    int(row[i_len])
                except Exception:
                    continue
                if parse_asn_fast(row[i_src]) is None or parse_asn_fast(row[i_tgt]) is None:
                    continue

                if keep_all_columns:
                    writer.writerow(row)
                else:
                    writer.writerow([row[i_src], row[i_tgt], row[i_len]])
                seen_offsets.add(offset)
                target_rows -= 1

    if target_rows > 0:
        raise RuntimeError("Could not collect the requested subset size within attempt budget. "
                           "Increase max_attempts_factor or loosen filters.")

# sample from subset with IPv4-only weights
def alloc_targets(dist: dict[int, float], total: int) -> dict[int,int]:
    total_w = sum(dist.values())
    raw = {L: (w/total_w)*total for L, w in dist.items()}
    floors = {L: int(math.floor(x)) for L, x in raw.items()}
    r = total - sum(floors.values())
    if r > 0:
        order = sorted(raw.items(), key=lambda kv: (kv[1] - floors[kv[0]]), reverse=True)
        for i in range(r):
            floors[order[i][0]] += 1
    return floors

def weighted_sample_from_subset(subset_csv: str,
                                as_weights: dict[int,float],
                                dist_dict: dict[int,float],
                                total_samples: int,
                                random_state: int = 42) -> pd.DataFrame:
    df = pd.read_csv(subset_csv)
    df["_src_asn"] = df["source_as"].astype(str).str.extract(r'(\d+)').astype(float).astype("Int64")
    df["_tgt_asn"] = df["target_as"].astype(str).str.extract(r'(\d+)').astype(float).astype("Int64")
    s_w = df["_src_asn"].map(as_weights).fillna(0.0)
    t_w = df["_tgt_asn"].map(as_weights).fillna(0.0)
    df["_w"] = s_w + t_w

    quotas = alloc_targets(dist_dict, total_samples)
    out_parts = []
    rng = random_state
    for L, n in quotas.items():
        g = df[df["path_length"] == L]
        if len(g) < n:
            raise ValueError(f"Subset too small for length {L}: need {n}, have {len(g)}.")
        if g["_w"].sum() == 0:
            raise ValueError(f"All weights zero for length {L} in subset.")
        sampled = g.sample(n=n, weights=g["_w"], random_state=rng)
        out_parts.append(sampled[["source_as","target_as","path_length"]])
        rng += 1
    return pd.concat(out_parts, ignore_index=True)

csv_path    = r"data\server\sampled_path_lengths_SP_250k_pops_w_novalidity.csv"
#subset_path = r"subset_10M.csv"
pfx2as_file = r"topology_map\data\routeviews-rv2-20240101-1200.pfx2as"

PATHLEN_DIST = {1:6.92, 2: 61.94, 3: 26.41, 4: 4.43, 5: 0.29, 6: 0.01}
TOTAL_SAMPLES = 10_000

# build AS weights from pfx2as ONLY
as_counts  = compute_as_ipv4_counts_from_pfx2as_plain(pfx2as_file)
as_weights = as_fractions_from_counts(as_counts)

# create a ~5M random subset quickly (no full scan)
#make_random_subset_seek(csv_path, subset_path, target_rows=10_000_000,
#                       keep_all_columns=False,  # write only 3 needed cols
#                       random_state=65, max_attempts_factor=6)

# sample from the subset with IPv4-only weighting and your length quotas
sampled = weighted_sample_from_subset(csv_path, as_weights,
                                      PATHLEN_DIST, TOTAL_SAMPLES, random_state=42)

sampled.to_csv("pop_10k_sample_novalidity.csv", index=False)
print("Done")
