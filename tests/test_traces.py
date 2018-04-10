import pandas as pd
import glob
import networkx as nx

def test_connected_component():
    for trace_file in glob.glob("traces/*.ctr"):
        # read first transaction from trace
        trace = pd.read_csv(trace_file, parse_dates=["datetime"], index_col="datetime")
        first_transaction = trace[(trace.transaction_id == trace.transaction_id.min()) &
                                  (trace.channel == "11-26") &
                                  (trace.pdr > 0)]

        # build graph
        nodes = list(set().union(first_transaction.src.unique(),
                                 first_transaction.dst.unique()))
        edges = list(set().union(first_transaction.groupby(["src", "dst"]).groups.keys(),
                                 first_transaction.groupby(["dst", "src"]).groups.keys()))
        G = nx.Graph()
        G.add_nodes_from(nodes)
        G.add_edges_from(edges)

        # assert that there is only one connected component
        assert len(list(nx.connected_components(G))) == 1

