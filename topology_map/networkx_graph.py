import json
import networkx as nx
import os
from datetime import datetime
from typing import Optional, Set, Any
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap
import heapq
import numpy as np

'''
EDGE + POP LOGIC
'''

class ASGraph:
    def __init__(self, data_file, relationships_file, countries, iso_mapping_file, load_data=True, 
                 emissions_folder_path=None, as_to_country=None, as_to_region=None, as_to_iso_code=None):
        self.data_file = data_file
        self.relationships_file = relationships_file
        self.countries = countries
        self.graph = nx.DiGraph()
        self.filtered_data = []  
        if iso_mapping_file and os.path.exists(iso_mapping_file):
            self.iso_mapping = self.load_iso_mapping(iso_mapping_file)
        else:
            # Allow tests or manual graph construction without the file.
            self.iso_mapping = {"countries": {}, "regions": {}}
        self.as_to_country = as_to_country or {}
        self.as_to_region = as_to_region or {}
        self.as_to_iso_code = as_to_iso_code or {}
        self.node_costs = {}
            
        if load_data:
            self.load_and_filter_data()    
        self.emissions_folder_path = emissions_folder_path  

    def load_iso_mapping(self, iso_mapping_file):
        last_err = None
        for enc in ("utf-8", "utf-8-sig"):
            try:
                with open(iso_mapping_file, "r", encoding=enc) as f:
                    data = json.load(f)
                # minimal sanity check (your iso.json has a "countries" object)
                if not isinstance(data, dict) or "countries" not in data:
                    raise ValueError("Invalid iso mapping: missing 'countries' key.")
                return data
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
                last_err = e
                continue

        raise RuntimeError(
            f"Could not decode {iso_mapping_file} as UTF-8/UTF-8-SIG or file is malformed: {last_err}"
        )

    def load_and_filter_data(self):
        # Try both UTF-8 and UTF-8-SIG encodings
        for enc in ("utf-8", "utf-8-sig"):
            try:
                with open(self.data_file, "r", encoding=enc) as f:
                    data = json.load(f)
                break  # success → exit loop
            except UnicodeDecodeError:
                continue
        else:
            raise RuntimeError(
                f"Could not decode {self.data_file} as UTF-8 or UTF-8-SIG. "
                "Please re-save the file in UTF-8."
            )

        self.filtered_data = [
            entry for entry in data if entry['country'] in self.countries
        ]

    def add_nodes(self):
        for entry in self.filtered_data:
            # print(f"Loaded {len(self.filtered_data)} PoPs to process...")
            try:
                pop = entry["pop"]
                as_number = entry["as_number"]
                region = entry.get("region", "").strip().upper()
                country = entry.get("country", "").strip().upper()
                lat, lon = float(entry["lat"]), float(entry["lon"])

                # === ISO code lookup with fallback ===
                iso_code = None
                region_key = f"{country}-{region}" if region else None

                # print(f"Checking: {pop} → region_key: '{region_key}' | country: '{country}'")

                # Try full region match first
                if region_key and region_key in self.iso_mapping.get('regions', {}):
                    iso_code = self.iso_mapping['regions'][region_key]['iso_code']
                # Fallback to country-level mapping
                elif country in self.iso_mapping.get('countries', {}):
                    iso_code = self.iso_mapping['countries'][country]['iso_code']

                if not iso_code:
                    print(f"No ISO code found for {region_key} or {country} → skipping PoP {pop}")
                    continue

                # === Emissions file check ===
                csv_filename = f"{iso_code}_2023_hourly.csv"
                csv_path = os.path.join(self.emissions_folder_path, csv_filename)
                
                if not os.path.exists(csv_path):
                    # Skip PoPs with no emissions data
                    print(f"File not found for zone '{iso_code}': {csv_path}")
                    continue

                # === Add node to graph ===
                self.graph.add_node(
                    pop,
                    as_number=as_number,
                    country=country,
                    region=region,
                    iso=iso_code,
                    title=f"""
                        <b>PoP:</b> {pop}<br>
                        <b>AS Number:</b> {as_number}<br>
                        <b>Country:</b> {country}<br>
                        <b>Region:</b> {region}<br>
                        <b>Latitude:</b> {lat}<br>
                        <b>Longitude:</b> {lon}
                    """,
                    x=lon * 100000,
                    y=lat * 100000
                )

                # Optional: track ISO per AS
                self.as_to_iso_code[as_number] = iso_code

            except KeyError as e:
                print(f"Missing key in data: {e}")
            except ValueError as e:
                print(f"Invalid value in data: {e}")

    def has_valid_data(self, iso_code):
        """
         if valid emissions data exists for the given ISO code."""
        filename = f"{iso_code}_2023_hourly.csv"
        file_path = os.path.join(self.emissions_folder_path, filename)
        return os.path.exists(file_path)

    def add_edges(self):
        # AS to PoP
        as_to_pops = {}
        for node, attrs in self.graph.nodes(data=True):
            asn = attrs.get("as_number")
            if asn:
                as_to_pops.setdefault(asn, []).append(node)

        # asrel from CAIDA
        with open(self.relationships_file, "r") as f:
            for line in f:
                try:
                    as1, as2, rel_type, *_ = line.strip().split("|")
                    as1 = as1.strip()
                    as2 = as2.strip()

                    pops1 = as_to_pops.get(as1, [])
                    pops2 = as_to_pops.get(as2, [])

                    if not pops1 or not pops2:
                        continue  # skip if one AS has no PoPs

                    if rel_type == '-1':
                        # <provider-as>|<customer-as>|-1
                        for provider_pop in pops1:
                            for customer_pop in pops2:
                                self.graph.add_edge(customer_pop, provider_pop, relationship="c2p", color="orange",weight=0.0001)
                                self.graph.add_edge(provider_pop, customer_pop, relationship="p2c", color="orange",weight=0.0001)
                    elif rel_type == '0':
                        # Peer-to-peer
                        for pop1 in pops1:
                            for pop2 in pops2:
                                self.graph.add_edge(pop1, pop2, relationship="p2p", color="green",weight=0.0001)
                                self.graph.add_edge(pop2, pop1, relationship="p2p", color="green",weight=0.0001)

                except ValueError as e:
                    print(f"Invalid line format: {line.strip()}, Error: {e}")

        # s2s
        for asn, pop_list in as_to_pops.items():
            for i in range(len(pop_list)):
                for j in range(i + 1, len(pop_list)):
                    self.graph.add_edge(pop_list[i], pop_list[j], relationship="s2s", color="blue",weight=0.00005)
                    self.graph.add_edge(pop_list[j], pop_list[i], relationship="s2s", color="blue",weight=0.00005)

        print(f"Graph has {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")               

    def get_country_emissions(self, datetime_str, iso_code):
        filename = f"{iso_code}_2023_hourly.csv"
        file_path = os.path.join(self.emissions_folder_path, filename)
        col = "carbon intensity gco₂eq/kwh (direct)"  # source column name in CSV

        if not os.path.exists(file_path):
            return float("inf")

        # Load once and normalize columns
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.lower().str.strip()
        if "datetime (utc)" not in df or col not in df:
            return float("inf")

        # Parse datetime column and coerce the whole column numeric up front
        df["datetime (utc)"] = pd.to_datetime(
            df["datetime (utc)"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

        # Exact timestamp lookup
        dt_input = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        match = df.loc[df["datetime (utc)"] == pd.Timestamp(dt_input)]

        if not match.empty:
            val = float(match.iloc[0][col]) if pd.notna(match.iloc[0][col]) else np.nan
            if np.isfinite(val):
                return val
            # else: fall through to daily-average fallback

        # Fallback: daily average (UTC) for that calendar day
        day_mask = df["datetime (utc)"].dt.date == dt_input.date()
        if day_mask.any():
            day_mean = pd.to_numeric(df.loc[day_mask, col], errors="coerce").mean()
            if pd.notna(day_mean) and np.isfinite(day_mean):
                return float(day_mean)

        # If the day has no usable data, keep prior behavior
        return float("inf")

    
    def add_emission_data(self, specific_datetime):
        """
        Compute per-node emissions and project them onto outgoing edges
        """
        node_em = {}
        for u, attrs in self.graph.nodes(data=True):
            iso = attrs.get("iso")
            if not iso or not self.has_valid_data(iso):
                node_em[u] = float("inf")
            else:
                node_em[u] = self.get_country_emissions(specific_datetime, iso)
        for u, v, ed in self.graph.edges(data=True):
            ed['emissions'] = node_em.get(u, float("inf"))

    def is_valid_path(self, path):
        state = None  
        not_only_s2s = False

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            edge_data = self.graph.get_edge_data(u, v)

            if not edge_data or "relationship" not in edge_data:
                return False
            
            relationship = edge_data["relationship"]

            if relationship != "s2s": 
                not_only_s2s = True
            if relationship == "s2s": # allow internal relationships
                continue

            # Transition Rules
            if state == "p2p" and relationship != "p2c":  # p2p can only go to p2c
                return False
            elif state == "p2c" and relationship != "p2c":  # p2c can only stay p2c
                return False
            
            state = relationship  # Update state to current relationship

        return not_only_s2s  

    def edge_cost(self, u, v):
        return self.graph[u][v].get('emissions', float("inf"))  

    def find_all_valid_paths(self, source, emissions: bool = True, targets: Optional[Set[Any]] = None):
        """
        emissions=True  -> objective = (emissions, weight, hops)
        emissions=False -> objective = (hops, weight, emissions)
        Returns: dict[target_node] -> path
        """
        UP, P2P_DONE, DOWN = 0, 1, 2
        def next_phase(phase, rel):
            if rel == "s2s": return phase
            if rel == "c2p": return phase if phase == UP else None
            if rel == "p2p": return P2P_DONE if phase == UP else None
            if rel == "p2c": return DOWN
            return None
        # tuples (key0, key1, key2, tiebreaker, node, phase, last_rel)
        def make_key(hops, wsum, emis):
            return (emis, wsum, hops) if emissions else (hops, wsum, emis)
       
        best_state = {}         # best_state[(node, phase, last_non_s2s_rel)] = (hops, wsum, emis)
        best_per_node = {}      # node -> key tuple
        pred = {}               # path reconstruction: pred[(node, phase, last_rel)] = (prev_state, prev_node)

        s_key = (source, UP, None)
        best_state[s_key] = (0, 0.0, 0.0)
        pred[s_key] = None

        heap = []
        tiebreak = 0
        heapq.heappush(heap, (*make_key(0, 0.0, 0.0), tiebreak, source, UP, None))

        remaining_targets = set(targets) if targets else None

        while heap:
            k0, k1, k2, _, u, phase, last_rel = heapq.heappop(heap)
            state_key = (u, phase, last_rel)
            hops, wsum, emis = best_state[state_key]
            # stale check via recompute key
            if (k0, k1, k2) != make_key(hops, wsum, emis):
                continue

            # finalize best for graph-node u (first time we pop a state whose key beats per-node key)
            key = (k0, k1, k2)
            if (u not in best_per_node) or (key < best_per_node[u]):
                best_per_node[u] = key

            # optional early stop for single-target queries
            if remaining_targets:
                if u in remaining_targets:
                    remaining_targets.remove(u)
                    if not remaining_targets:
                        break

            for v, ed in self.graph[u].items():
                rel = ed.get("relationship")
                nphase = next_phase(phase, rel)
                if nphase is None:
                    continue

                # valley-free detail: propagate "last non-s2s"
                last_rel_next = rel if rel != "s2s" else last_rel

                # new raw costs
                w = float(ed.get("weight", 0.0))
                hops2 = hops + 1
                wsum2 = wsum + w
                emis2 = emis + self.edge_cost(u, v)

                s2 = (v, nphase, last_rel_next)
                prev = best_state.get(s2)
                cand = (hops2, wsum2, emis2)
                if prev is None or (make_key(*cand) < make_key(*prev)):
                    best_state[s2] = cand
                    pred[s2] = state_key
                    tiebreak += 1
                    heapq.heappush(heap, (*make_key(*cand), tiebreak, v, nphase, last_rel_next))

        def rebuild_path(end_node):
            choices = [(make_key(*best_state[s]), s) for s in best_state.keys() if s[0] == end_node and s[2] is not None]
            if not choices:
                return None
            _, best_s = min(choices)
            path_nodes = []
            cur = best_s
            while cur is not None:
                node = cur[0]
                path_nodes.append(node)
                cur = pred.get(cur)
            return list(reversed(path_nodes))

        nodes_to_return = best_per_node.keys()
        if targets:
            nodes_to_return = [n for n in nodes_to_return if n in targets]

        valid_paths = {}
        for node in nodes_to_return:
            p = rebuild_path(node)
            if p:
                valid_paths[node] = p
        return valid_paths
    
    def find_all_paths(self, source, emissions: bool = True, targets: Optional[Set[Any]] = None):
        """
        emissions=True  -> objective = (emissions, weight, hops)
        emissions=False -> objective = (hops, weight, emissions)
        Returns: dict[target_node] -> path
        """
        
        def make_key(hops, wsum, emis):
            return (emis, wsum, hops) if emissions else (hops, wsum, emis)
       
        # best cost per node: node -> (hops, wsum, emis)
        best = {source: (0, 0.0, 0.0)}
        pred = {source: None}

        heap = []
        tiebreak = 0
        heapq.heappush(heap, (*make_key(0, 0.0, 0.0), tiebreak, source))

        remaining_targets = set(targets) if targets else None

        while heap:
            k0, k1, k2, _, u = heapq.heappop(heap)
            hops, wsum, emis = best[u]
            # stale check via recompute key
            if (k0, k1, k2) != make_key(hops, wsum, emis):
                continue

            if remaining_targets:
                if u in remaining_targets:
                    remaining_targets.remove(u)
                    if not remaining_targets:
                        break

            for v, ed in self.graph[u].items():            
                w = float(ed.get("weight", 0.0))
                hops2 = hops + 1
                wsum2 = wsum + w
                emis2 = emis + self.edge_cost(u, v)

                prev = best.get(v)
                cand = (hops2, wsum2, emis2)
                if prev is None or (make_key(*cand) < make_key(*prev)):
                    best[v] = cand
                    pred[v] = u
                    tiebreak += 1
                    heapq.heappush(heap, (*make_key(*cand), tiebreak, v))

        def rebuild_path(end_node):
            if end_node not in best:
                return None
            path = []
            cur = end_node
            while cur is not None:
                path.append(cur)
                cur = pred.get(cur)
            return list(reversed(path))

        nodes_to_return = best.keys()
        if targets:
            nodes_to_return = [n for n in nodes_to_return if n in targets]

        best_paths = {}
        for node in nodes_to_return:
            p = rebuild_path(node)
            if p:
                best_paths[node] = p
        return best_paths
            
    def path_cost(self, path):
        return sum(self.edge_cost(path[i], path[i+1]) for i in range(len(path) - 1))

    def find_valid_path(self, source, target, emissions: bool = True):
        paths = self.find_all_valid_paths(
            source,
            emissions=emissions,
            targets={target}  # <-- early stop
        )
        return paths.get(target)
    
    def find_path(self, source, target, emissions: bool = True):
        paths = self.find_all_paths(
            source,
            emissions=emissions,
            targets={target}  # <-- early stop
        )
        return paths.get(target)

    def plot_graph(self):
        fig, ax = plt.subplots(figsize=(12, 12))
        m = Basemap(projection='robin', lon_0=0, resolution='c', ax=ax)
        # m = Basemap(projection='lcc', resolution='h', lat_0=50, lon_0=10, width=8E6, height=6E6, ax=ax) # EU
        m.drawcoastlines()
        m.drawcountries()
        m.drawstates()

        for entry in self.filtered_data:
            try:
                lat, lon = float(entry['lat']), float(entry['lon'])
                x, y = m(lon, lat)
                m.scatter(x, y, c='blue', s=15, edgecolors='k', zorder=5)
                # plt.text(x, y, str(entry['as_number']), fontsize=8, ha='right', va='bottom', color='black', zorder=10) 
            except ValueError as e:
                print(f"Invalid latitude/longitude data for {entry['as_number']}")

        for edge in self.graph.edges:
            provider = edge[0]
            customer = edge[1]
            provider_data = next((entry for entry in self.filtered_data if str(entry['as_number']) == str(provider)), None)
            customer_data = next((entry for entry in self.filtered_data if str(entry['as_number']) == str(customer)), None)


            if provider_data and customer_data:
                provider_x, provider_y = m(float(provider_data['lon']), float(provider_data['lat']))
                customer_x, customer_y = m(float(customer_data['lon']), float(customer_data['lat']))
                edge_color = self.graph[provider][customer].get('color', 'red')
                # m.plot([provider_x, customer_x], [provider_y, customer_y], color=edge_color, linewidth=1, zorder=2)

        plt.title('Network of Autonomous Systems (ASes)')
        plt.savefig(r'topology_map\network_topology_glo.png', format='png', dpi=300)
        print("image saved")

