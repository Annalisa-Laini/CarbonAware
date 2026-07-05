# Is Carbon-Aware Inter-Domain Routing Worth the Effort?
A carbon-aware, valley-free routing simulator for Autonomous System networks. The code available in this repository builds a graph of network Points of Presence, applies real inter-AS business relationships, and finds routing paths optimized for grid carbon intensity instead of (or alongside) traditional hop count.

## Repository structure

| Path | Description |
|---|---|
| `energy_graphs/` | Plots/analysis relating network paths to carbon intensity |
| `topology_map/` | Scripts necessary to create a PoP-level network topology to evaluate algorithms differences |

## Energy Graphs
Running **main.py** lets you generate carbon-intensity trend plots by selecting a granularity ("seasonal" or "monthly") and whether the y-axis should be scaled (True) or not (False); the plot_function_map dispatches the chosen combination to the corresponding plotting function in plotter (plot_seasonal_scaled, plot_seasonal_not_scaled, plot_monthly_scaled, plot_monthly_not_scaled).

## Toplogy Map
### Installation

```bash
git clone https://github.com/Annalisa-Laini/CarbonAware.git
cd CarbonAware
pip install -r requirements.txt
```

### Data Used
1. Electricity Maps — 2023 hourly historical CSVs, one per zone: https://app.electricitymaps.com/datasets (The Electricity Maps CSVs should be mapped as {ISO_CODE}_2023_hourly.csv inside a single emissions_folder_path (data for 2023 is available under energy_graphs\data).)
2. CAIDA AS-relationships (Serial-2) — snapshot 20240101.as-rel2.txt: https://www.caida.org/catalog/datasets/as-relationships/
3. CAIDA ITDK — midar-iff.nodes.as (node → AS mapping) and midar-iff.nodes.geo (node geolocation), derived from merged_nodes.jsonl: https://www.caida.org/catalog/datasets/internet-topology-data-kit/
4. CAIDA RouteViews prefix-to-AS — snapshot routeviews-rv2-20240101-1200.pfx2as (only needed later, for IPv4-based sampling weights)
5. iso.json — hand-built mapping from country/region to Electricity Maps ISO zone, including manual overrides for small countries (MC→FR, LI→CH, AD→ES, SM→IT, VA→IT), regionless Russia (→RU-1), and any other regionless country (→ country average)
6. countries.txt — list of country codes to include in a given run (e.g. a European subset, or all countries for the global topology)
7. geolocation_pop.json - list on PoP that will populate the graphs and create the topology

### Calculate the paths' emissions
For each target timestamp run first **pickle_graph_creator.py**, and then **pickle_graph_hourly_creator.py** to create pkl files with all the necessary graphs, data and paths. 

The script **process_emission_paths.py** computes, for the chosen range of dates and hours, the Lowest-Emissions paths (emissions=True) (or Shortest Path paths (emissions=False)) for each sampled source-target AS pair of a chosen path length (from _pop_10k_sample.csv_*), using the hourly graph pickles built in the previous step. The scripts sum per-edge emissions along each path and incrementally appends results to a resumable CSV, which can be further explored and plotted by running **boxplots.py**

*use:
- _pop_10k_sample.csv_ for the original 10k sample
- _pop_10k_sample_novalidity.csv_ for the 10k sample without validity constraints (in this particular case, use_pickle_graphs.py should use function find_path)
- _pop_1k_sample.csv_ as the 1k EUROPE SAMPLE (also change countries.txt to countriesEU.txt)
- _pop_3k_sample.csv_ for the 1000 couples of len 4,5,6





