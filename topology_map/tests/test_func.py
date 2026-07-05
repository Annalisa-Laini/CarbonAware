import networkx as nx
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from networkx_graph import ASGraph
import json
import tempfile
import pytest

@pytest.fixture(scope="session")
def tmp_env():
    """
    Creates a temp iso_mapping file and an emissions folder.
    We don't rely on real datasets here.
    """
    tmpdir = tempfile.TemporaryDirectory()
    iso_path = os.path.join(tmpdir.name, "iso.json")
    with open(iso_path, "w", encoding="utf-8") as f:
        json.dump({
            "countries": {
                "IT": {"iso_code": "IT"},
                "DE": {"iso_code": "DE"},
                "FR": {"iso_code": "FR"},
                "ES": {"iso_code": "ES"},
            },
            "regions": {}
        }, f)
    em_dir = os.path.join(tmpdir.name, "emissions")
    os.makedirs(em_dir, exist_ok=True)
    yield {"iso_path": iso_path, "em_dir": em_dir, "tmpdir": tmpdir}
    tmpdir.cleanup()


@pytest.fixture
def make_solver(tmp_env):
    """
    Returns a function that creates an ASGraph with load_data=False
    so tests can add nodes/edges manually.
    """
    def _make():
        return ASGraph(
            data_file=tmp_env["iso_path"],
            relationships_file=tmp_env["iso_path"],
            countries={"IT", "DE", "FR", "ES"},
            iso_mapping_file=tmp_env["iso_path"],
            load_data=False,
            emissions_folder_path=tmp_env["em_dir"],
        )
    return _make


def set_all_edge_emissions(G, value_or_fn):
    """
    Helper: set edge['emissions'] for all edges.
    value_or_fn can be a float or a callable (u, v) -> float.
    """
    for u, v in G.graph.edges():
        if callable(value_or_fn):
            G.graph[u][v]["emissions"] = float(value_or_fn(u, v))
        else:
            G.graph[u][v]["emissions"] = float(value_or_fn)


# -------------
# The tests
# -------------

def test_le_vs_sp_different_paths(make_solver):
    G = make_solver()
    for n, iso in [("A","IT"),("B","DE"),("C","FR"),("D","ES")]:
        G.graph.add_node(n, iso=iso)

    # Two options A->D:
    # SP should prefer A->B->D (hops/weight),
    # LE should prefer A->C->D (lower emissions on A and C).
    G.graph.add_edge("A","B", relationship="c2p", weight=0.1)
    G.graph.add_edge("B","D", relationship="p2c", weight=0.1)
    G.graph.add_edge("A","C", relationship="c2p", weight=0.2)
    G.graph.add_edge("C","D", relationship="p2c", weight=0.4)

    def src_em(u, _):
        return {"A": 300.0, "B": 800.0, "C": 200.0}.get(u, 500.0)

    set_all_edge_emissions(G, src_em)

    paths_LE = G.find_all_valid_paths("A", emissions=True)
    paths_SP = G.find_all_valid_paths("A", emissions=False)

    assert paths_LE["D"] == ["A", "C", "D"]
    assert paths_SP["D"] == ["A", "B", "D"]
    assert G.find_valid_path("A", "D", emissions=True) == ["A", "C", "D"]

def test_le_vs_sp_different_paths_all_paths(make_solver):
    G = make_solver()
    for n, iso in [("A","IT"),("B","DE"),("C","FR"),("D","ES")]:
        G.graph.add_node(n, iso=iso)

    # Two options A->D:
    # SP should prefer A->B->D (hops/weight),
    # LE should prefer A->C->D (lower emissions on A and C).
    G.graph.add_edge("A","B", relationship="c2p", weight=0.1)
    G.graph.add_edge("B","D", relationship="p2c", weight=0.1)
    G.graph.add_edge("A","C", relationship="c2p", weight=0.2)
    G.graph.add_edge("C","D", relationship="p2c", weight=0.4)

    def src_em(u, _):
        return {"A": 300.0, "B": 800.0, "C": 200.0}.get(u, 500.0)

    set_all_edge_emissions(G, src_em)

    paths_LE = G.find_all_paths("A", emissions=True)
    paths_SP = G.find_all_paths("A", emissions=False)

    assert paths_LE["D"] == ["A", "C", "D"]
    assert paths_SP["D"] == ["A", "B", "D"]
    assert G.find_path("A", "D", emissions=True) == ["A", "C", "D"]


def test_targets_early_stop_returns_subset(make_solver):
    G = make_solver()
    for n in ["S","A","B","C"]:
        G.graph.add_node(n, iso="IT")
    # Make two branches
    G.graph.add_edge("S","A", relationship="c2p", weight=0.1)
    G.graph.add_edge("S","B", relationship="c2p", weight=0.1)
    G.graph.add_edge("A","C", relationship="p2c", weight=0.1)
    G.graph.add_edge("B","C", relationship="p2c", weight=0.1)
    set_all_edge_emissions(G, 1.0)

    subset = G.find_all_valid_paths("S", emissions=False, targets={"A","C"})
    assert set(subset.keys()) == {"A", "C"}

def test_targets_early_stop_returns_subset_all_paths(make_solver):
    G = make_solver()
    for n in ["S","A","B","C"]:
        G.graph.add_node(n, iso="IT")
    # Make two branches
    G.graph.add_edge("S","A", relationship="c2p", weight=0.1)
    G.graph.add_edge("S","B", relationship="c2p", weight=0.1)
    G.graph.add_edge("A","C", relationship="p2c", weight=0.1)
    G.graph.add_edge("B","C", relationship="p2c", weight=0.1)
    set_all_edge_emissions(G, 1.0)

    subset = G.find_all_paths("S", emissions=False, targets={"A","C"})
    assert set(subset.keys()) == {"A", "C"}


def test_valley_free_forbids_p2p_to_c2p(make_solver):
    G = make_solver()
    for n, iso in [("A","IT"),("B","DE"),("C","DE"),("D","DE"),("E","DE")]:
        G.graph.add_node(n, iso=iso)

    # legal: A->B (c2p, UP), B->C (p2p -> P2P_DONE), C->D (p2c, DOWN)
    G.graph.add_edge("A","B", relationship="c2p", weight=0.0)
    G.graph.add_edge("B","C", relationship="p2p", weight=0.0)
    G.graph.add_edge("C","D", relationship="p2c", weight=0.0)

    # illegal candidate: p2p -> c2p (C->E)
    G.graph.add_edge("C","E", relationship="c2p", weight=0.0)

    set_all_edge_emissions(G, 1.0)

    assert G.find_valid_path("A","D", emissions=False) == ["A","B","C","D"]
    assert G.find_valid_path("A","E", emissions=False) is None  # must be blocked


def test_s2s_keeps_phase(make_solver):
    G = make_solver()
    for n in ["A","A1","B"]:
        G.graph.add_node(n, iso="IT")
    G.graph.add_edge("A","A1", relationship="s2s", weight=0.0)   # phase unchanged
    G.graph.add_edge("A1","B", relationship="c2p", weight=0.0)   # still allowed (UP)
    set_all_edge_emissions(G, 1.0)
    assert G.find_valid_path("A","B", emissions=False) == ["A","A1","B"]


def test_tie_break_order(make_solver):
    G = make_solver()
    for n in ["S","X","Y","T"]:
        G.graph.add_node(n, iso="IT")
    # Two equal-hop paths S->X->T vs S->Y->T
    G.graph.add_edge("S","X", relationship="c2p", weight=0.1)
    G.graph.add_edge("X","T", relationship="p2c", weight=0.1)
    G.graph.add_edge("S","Y", relationship="c2p", weight=0.5)
    G.graph.add_edge("Y","T", relationship="p2c", weight=0.5)
    set_all_edge_emissions(G, 10.0)

    # LE picks lower weight when emissions tied
    assert G.find_all_valid_paths("S", emissions=True)["T"] == ["S", "X", "T"]

    # Now equalize weight, vary emissions → SP uses emissions as 3rd tie-break
    G.graph["S"]["X"]["weight"] = 0.3; G.graph["X"]["T"]["weight"] = 0.3
    G.graph["S"]["Y"]["weight"] = 0.3; G.graph["Y"]["T"]["weight"] = 0.3
    G.graph["S"]["X"]["emissions"] = 100.0; G.graph["X"]["T"]["emissions"] = 100.0
    G.graph["S"]["Y"]["emissions"] = 1.0;   G.graph["Y"]["T"]["emissions"] = 1.0

    assert G.find_all_valid_paths("S", emissions=False)["T"] == ["S", "Y", "T"]


def test_tie_break_order_all_paths(make_solver):
    G = make_solver()
    for n in ["S","X","Y","T"]:
        G.graph.add_node(n, iso="IT")
    # Two equal-hop paths S->X->T vs S->Y->T
    G.graph.add_edge("S","X", relationship="c2p", weight=0.1)
    G.graph.add_edge("X","T", relationship="p2c", weight=0.1)
    G.graph.add_edge("S","Y", relationship="c2p", weight=0.5)
    G.graph.add_edge("Y","T", relationship="p2c", weight=0.5)
    set_all_edge_emissions(G, 10.0)

    # LE picks lower weight when emissions tied
    assert G.find_all_paths("S", emissions=True)["T"] == ["S", "X", "T"]

    # Now equalize weight, vary emissions → SP uses emissions as 3rd tie-break
    G.graph["S"]["X"]["weight"] = 0.3; G.graph["X"]["T"]["weight"] = 0.3
    G.graph["S"]["Y"]["weight"] = 0.3; G.graph["Y"]["T"]["weight"] = 0.3
    G.graph["S"]["X"]["emissions"] = 100.0; G.graph["X"]["T"]["emissions"] = 100.0
    G.graph["S"]["Y"]["emissions"] = 1.0;   G.graph["Y"]["T"]["emissions"] = 1.0

    assert G.find_all_paths("S", emissions=False)["T"] == ["S", "Y", "T"]

def test_determinism_on_equal_keys(make_solver):
    G = make_solver()
    for n in ["S","A","B","T"]:
        G.graph.add_node(n, iso="IT")
    # Two symmetric, identical-cost paths
    G.graph.add_edge("S","A", relationship="c2p", weight=0.1)
    G.graph.add_edge("A","T", relationship="p2c", weight=0.1)
    G.graph.add_edge("S","B", relationship="c2p", weight=0.1)
    G.graph.add_edge("B","T", relationship="p2c", weight=0.1)
    set_all_edge_emissions(G, 5.0)

    p1 = G.find_all_valid_paths("S", emissions=True)["T"]
    p2 = G.find_all_valid_paths("S", emissions=True)["T"]
    assert p1 == p2

def test_determinism_on_equal_keys_all_paths(make_solver):
    G = make_solver()
    for n in ["S","A","B","T"]:
        G.graph.add_node(n, iso="IT")
    # Two symmetric, identical-cost paths
    G.graph.add_edge("S","A", relationship="c2p", weight=0.1)
    G.graph.add_edge("A","T", relationship="p2c", weight=0.1)
    G.graph.add_edge("S","B", relationship="c2p", weight=0.1)
    G.graph.add_edge("B","T", relationship="p2c", weight=0.1)
    set_all_edge_emissions(G, 5.0)

    p1 = G.find_all_paths("S", emissions=True)["T"]
    p2 = G.find_all_paths("S", emissions=True)["T"]
    assert p1 == p2


def test_infinite_emissions_are_dominated(make_solver):
    G = make_solver()
    for n in ["S","A","T"]:
        G.graph.add_node(n, iso="IT")
    G.graph.add_edge("S","A", relationship="c2p", weight=0.1)
    G.graph.add_edge("A","T", relationship="p2c", weight=0.1)
    G.graph.add_edge("S","T", relationship="c2p", weight=0.1)   # direct but inf emissions
    set_all_edge_emissions(G, 1.0)
    G.graph["S"]["T"]["emissions"] = float("inf")

    assert G.find_all_valid_paths("S", emissions=True)["T"] == ["S","A","T"]

def test_infinite_emissions_are_dominated_all_paths(make_solver):
    G = make_solver()
    for n in ["S","A","T"]:
        G.graph.add_node(n, iso="IT")
    G.graph.add_edge("S","A", relationship="c2p", weight=0.1)
    G.graph.add_edge("A","T", relationship="p2c", weight=0.1)
    G.graph.add_edge("S","T", relationship="c2p", weight=0.1)   # direct but inf emissions
    set_all_edge_emissions(G, 1.0)
    G.graph["S"]["T"]["emissions"] = float("inf")

    assert G.find_all_paths("S", emissions=True)["T"] == ["S","A","T"]


def test_cycles_terminate_and_choose_optimal(make_solver):
    G = make_solver()
    for n in ["S","A","B","T"]:
        G.graph.add_node(n, iso="IT")
    G.graph.add_edge("S","A", relationship="c2p", weight=0.1)
    G.graph.add_edge("A","B", relationship="s2s", weight=0.0)
    G.graph.add_edge("B","A", relationship="s2s", weight=0.0)  # s2s cycle
    G.graph.add_edge("A","T", relationship="p2c", weight=0.1)
    set_all_edge_emissions(G, 1.0)

    assert G.find_valid_path("S","T", emissions=True) == ["S","A","T"]

def test_cycles_terminate_and_choose_optimal_all_paths(make_solver):
    G = make_solver()
    for n in ["S","A","B","T"]:
        G.graph.add_node(n, iso="IT")
    G.graph.add_edge("S","A", relationship="c2p", weight=0.1)
    G.graph.add_edge("A","B", relationship="s2s", weight=0.0)
    G.graph.add_edge("B","A", relationship="s2s", weight=0.0)  # s2s cycle
    G.graph.add_edge("A","T", relationship="p2c", weight=0.1)
    set_all_edge_emissions(G, 1.0)

    assert G.find_path("S","T", emissions=True) == ["S","A","T"]

def test_add_emission_data_projects_source_iso(make_solver):
    G = make_solver()
    G.graph.add_node("U", iso="IT")
    G.graph.add_node("V", iso="DE")
    G.graph.add_edge("U","V", relationship="c2p", weight=0.0)

    # Stub out file access so we control the value
    G.get_country_emissions = lambda ts, iso: 123.0 if iso == "IT" else 999.0
    G.has_valid_data = lambda iso: True

    G.add_emission_data("2023-07-15 12:00:00")
    assert G.graph["U"]["V"]["emissions"] == 123.0  # must equal source node (U) emissions

def _total_emissions(G, path):
    if not path or len(path) < 2:
        return 0.0
    s = 0.0
    for i in range(len(path) - 1):
        s += G.graph[path[i]][path[i+1]]["emissions"]
    return s

@pytest.mark.parametrize("variant", [1, 2])
def test_le_emissions_never_worse_than_sp(make_solver, variant):
    """
    Property test: For the same (s,t), the total edge-emissions on the
    LE path must be <= the emissions on the SP path (worst case: equal).
    """
    G = make_solver()
    for n, iso in [("A","IT"),("B","DE"),("C","FR"),("D","ES"),("E","DE")]:
        G.graph.add_node(n, iso=iso)
    G.graph.add_edge("A","B", relationship="c2p", weight=0.10)
    G.graph.add_edge("B","D", relationship="p2c", weight=0.10)
    G.graph.add_edge("A","C", relationship="c2p", weight=0.20)
    G.graph.add_edge("C","D", relationship="p2c", weight=0.40)
    G.graph.add_edge("A","E", relationship="c2p", weight=0.05)
    G.graph.add_edge("E","D", relationship="p2c", weight=0.05)
    def src_em(u, v):
        return {"A": 200.0, "C": 150.0, "B": 900.0, "E": 800.0}.get(u, 500.0)
    set_all_edge_emissions(G, src_em)

    p_le = G.find_valid_path("A", "D", emissions=True)
    p_sp = G.find_valid_path("A", "D", emissions=False)
    assert p_le is not None and p_sp is not None
    em_le = _total_emissions(G, p_le)
    em_sp = _total_emissions(G, p_sp)
    assert em_le <= em_sp + 1e-12 
    assert p_le == ["A", "C", "D"]
    assert p_sp in (["A", "E", "D"], ["A", "B", "D"])

def _total_emissions(G, path):
    if not path or len(path) < 2:
        return 0.0
    return sum(G.graph[path[i]][path[i+1]]["emissions"] for i in range(len(path)-1))

def _total_weight(G, path):
    if not path or len(path) < 2:
        return 0.0
    return sum(G.graph[path[i]][path[i+1]].get("weight", 0.0) for i in range(len(path)-1))


@pytest.mark.parametrize("variant", [1, 2])
def test_le_emissions_never_worse_than_sp_all_paths(make_solver, variant):
    """
    Property test: For the same (s,t), the total edge-emissions on the
    LE path must be <= the emissions on the SP path (worst case: equal).
    """
    G = make_solver()
    for n, iso in [("A","IT"),("B","DE"),("C","FR"),("D","ES"),("E","DE")]:
        G.graph.add_node(n, iso=iso)
    G.graph.add_edge("A","B", relationship="c2p", weight=0.10)
    G.graph.add_edge("B","D", relationship="p2c", weight=0.10)
    G.graph.add_edge("A","C", relationship="c2p", weight=0.20)
    G.graph.add_edge("C","D", relationship="p2c", weight=0.40)
    G.graph.add_edge("A","E", relationship="c2p", weight=0.05)
    G.graph.add_edge("E","D", relationship="p2c", weight=0.05)
    def src_em(u, v):
        return {"A": 200.0, "C": 150.0, "B": 900.0, "E": 800.0}.get(u, 500.0)
    set_all_edge_emissions(G, src_em)

    p_le = G.find_path("A", "D", emissions=True)
    p_sp = G.find_path("A", "D", emissions=False)
    assert p_le is not None and p_sp is not None
    em_le = _total_emissions(G, p_le)
    em_sp = _total_emissions(G, p_sp)
    assert em_le <= em_sp + 1e-12 
    assert p_le == ["A", "C", "D"]
    assert p_sp in (["A", "E", "D"], ["A", "B", "D"])

def _total_emissions(G, path):
    if not path or len(path) < 2:
        return 0.0
    return sum(G.graph[path[i]][path[i+1]]["emissions"] for i in range(len(path)-1))

def _total_weight(G, path):
    if not path or len(path) < 2:
        return 0.0
    return sum(G.graph[path[i]][path[i+1]].get("weight", 0.0) for i in range(len(path)-1))

@pytest.mark.parametrize("mode", [True, False])  # True=LE, False=SP
def test_early_stop_equals_full_run(make_solver, mode):
    G = make_solver()
    # tiny graph with two alternative routes S->T
    for n, iso in [("S","IT"),("A","DE"),("B","FR"),("T","ES")]:
        G.graph.add_node(n, iso=iso)

    # Two legal paths: S->A->T and S->B->T
    G.graph.add_edge("S","A", relationship="c2p", weight=0.0001)
    G.graph.add_edge("A","T", relationship="p2c", weight=0.0001)
    G.graph.add_edge("S","B", relationship="c2p", weight=0.00005)
    G.graph.add_edge("B","T", relationship="p2c", weight=0.0001)

    # Edge emissions inherited from source node
    def src_em(u, v):
        return {"S": 300.0, "A": 900.0, "B": 150.0}.get(u, 500.0)
    set_all_edge_emissions(G, src_em)

    # full run (all destinations)
    full = G.find_all_valid_paths("S", emissions=mode)
    p_full = full.get("T")

    # early stop (only target T)
    early = G.find_all_valid_paths("S", emissions=mode, targets={"T"})
    p_early = early.get("T")

    # Same path
    assert p_full == p_early

    # Same totals (belt-and-suspenders)
    assert _total_emissions(G, p_full) == _total_emissions(G, p_early)
    assert _total_weight(G, p_full) == _total_weight(G, p_early)
    assert len(p_full) == len(p_early)


@pytest.mark.parametrize("mode", [True, False])  # True=LE, False=SP
def test_early_stop_equals_full_run_all_paths(make_solver, mode):
    G = make_solver()
    # tiny graph with two alternative routes S->T
    for n, iso in [("S","IT"),("A","DE"),("B","FR"),("T","ES")]:
        G.graph.add_node(n, iso=iso)

    # Two legal paths: S->A->T and S->B->T
    G.graph.add_edge("S","A", relationship="c2p", weight=0.0001)
    G.graph.add_edge("A","T", relationship="p2c", weight=0.0001)
    G.graph.add_edge("S","B", relationship="c2p", weight=0.00005)
    G.graph.add_edge("B","T", relationship="p2c", weight=0.0001)

    # Edge emissions inherited from source node
    def src_em(u, v):
        return {"S": 300.0, "A": 900.0, "B": 150.0}.get(u, 500.0)
    set_all_edge_emissions(G, src_em)

    # full run (all destinations)
    full = G.find_all_paths("S", emissions=mode)
    p_full = full.get("T")

    # early stop (only target T)
    early = G.find_all_paths("S", emissions=mode, targets={"T"})
    p_early = early.get("T")

    # Same path
    assert p_full == p_early

    # Same totals (belt-and-suspenders)
    assert _total_emissions(G, p_full) == _total_emissions(G, p_early)
    assert _total_weight(G, p_full) == _total_weight(G, p_early)
    assert len(p_full) == len(p_early)

def test_non_valley_free_allows_previously_illegal_sequence(make_solver):
    G = make_solver()
    for n in ["S", "C", "B", "T"]:
        G.graph.add_node(n, iso="IT")

    # Now it must be allowed and (with equal hops/weight) SP should pick lower emissions.
    G.graph.add_edge("S", "C", relationship="p2p", weight=0.1)
    G.graph.add_edge("C", "T", relationship="c2p", weight=0.1)

    # Alternative path with same hops/weight but higher emissions
    G.graph.add_edge("S", "B", relationship="c2p", weight=0.1)
    G.graph.add_edge("B", "T", relationship="p2c", weight=0.1)

    # Emissions: make S->C->T cheaper
    G.graph["S"]["C"]["emissions"] = 1.0
    G.graph["C"]["T"]["emissions"] = 1.0
    G.graph["S"]["B"]["emissions"] = 10.0
    G.graph["B"]["T"]["emissions"] = 10.0

    paths_sp = G.find_all_paths("S", emissions=False)
    assert paths_sp["T"] == ["S", "C", "T"]
