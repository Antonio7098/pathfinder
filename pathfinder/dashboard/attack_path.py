import networkx as nx
from pyvis.network import Network
from classes import node, edge


class AttackGraph:

    def __init__(self):
        self.G = nx.DiGraph()
        self.nodes = {}
        self.edges = []

        self.best_path = None
        self.best_score = float("inf")

        self.fixes = {
            "sql_injection": "Use parameterized queries and input validation.",
            "auth_bypass": "Implement strong authentication and session validation.",
            "weak_secrets": "Move secrets to environment variables or vault.",
            "default": "Review access controls and sanitize inputs."
        }

    # -------------------------
    # Node / Edge creation
    # -------------------------

    def add_node(self, node_id, entry=False, end=False):
        self.nodes[node_id] = node(node_id, entry_point=entry, end_point=end)

    def add_edge(self, source, target):
        self.edges.append(edge(source, target))

    def load_nodes(self, files):

        for f, entry, end in files:
            self.add_node(f, entry, end)

    def load_edges(self, links):

        for src, dst in links:
            self.add_edge(src, dst)

    # -------------------------
    # Build Graph
    # -------------------------

    def build_graph(self):

        for n in self.nodes.values():

            self.G.add_node(
                n.node_id,
                entry_point=n.entry_point,
                end_point=n.end_point,
                exploitability=n.exploitability,
                lateral_movement_value=n.lateral_movement_value,
                data_access_value=n.data_access_value,
                privelidge_gain=n.privelidge_gain,
                node_value=n.node_value()
            )

        for e in self.edges:

            self.G.add_edge(
                e.source_node,
                e.target_node,
                vulnerability=e.vulnerability,
                transition_likelihood=e.transition_likelihood,
                detection_risk=e.detection_risk,
                edge_attack_cost=e.edge_attack_cost,
                edge_cost=e.edge_cost()
            )

        print(
            f"{self.G.number_of_edges()} edges and {self.G.number_of_nodes()} nodes added!"
        )

    # -------------------------
    # Scoring functions
    # -------------------------

    def node_reward(self, node):

        if node["end_point"]:
            return node["data_access_value"] * 5 + node["privelidge_gain"] * 2

        if node["entry_point"]:
            return node["exploitability"] * 3

        return node["lateral_movement_value"]

    def edge_cost(self, edge):

        return (
            edge["edge_attack_cost"] * 2
            + edge["detection_risk"] * 3
            + (1 - edge["transition_likelihood"])
        )

    def compute_weights(self):

        for u, v, d in self.G.edges(data=True):

            target = self.G.nodes[v]

            cost = self.edge_cost(d)
            reward = self.node_reward(target)

            d["weight"] = cost - reward

    # -------------------------
    # Path Search
    # -------------------------

    def find_attack_path(self):

        entry_nodes = [n for n, d in self.G.nodes(data=True) if d["entry_point"]]
        end_nodes = [n for n, d in self.G.nodes(data=True) if d["end_point"]]

        for s in entry_nodes:
            for t in end_nodes:

                try:

                    path = nx.shortest_path(self.G, s, t, weight="weight")
                    score = nx.path_weight(self.G, path, weight="weight")

                    if score < self.best_score:
                        self.best_score = score
                        self.best_path = path

                except:
                    pass

        return self.best_path, self.best_score

    # -------------------------
    # Path Explanation
    # -------------------------

    def explain_path(self):

        attack = []

        for i in range(len(self.best_path) - 1):

            src = self.best_path[i]
            dst = self.best_path[i + 1]

            vuln = self.G[src][dst]["vulnerability"]

            attack.append(f"{src} --[{vuln}]--> {dst}")

        return attack

    def get_path_edges(self):

        return [
            (u, v, self.G[u][v])
            for u, v in zip(self.best_path[:-1], self.best_path[1:])
        ]

    # -------------------------
    # Mitigation Suggestions
    # -------------------------

    def mitigation_steps(self):

        mitigations = []

        for u, v, d in self.get_path_edges():

            vuln = d.get("vulnerability", "default")
            fix = self.fixes.get(vuln, self.fixes["default"])

            mitigations.append((u, v, fix))

        return mitigations

    # -------------------------
    # Visualization
    # -------------------------

    def build_network(self):

        net = Network(height="600px", width="100%", directed=True)
        net.from_nx(self.G)

        for n in net.nodes:

            if n["end_point"]:
                n["color"] = "#FFDE21"

            elif n["entry_point"]:
                n["color"] = "#00FFFF"

            else:
                n["color"] = "#cccccc"

            n["title"] = f"Attacker Interest: {round(n['node_value'],2)}"

        for e in net.edges:

            e["color"] = "#dddddd"
            e["width"] = 1

            vuln = self.G.edges[e["from"], e["to"]].get("vulnerability")

            if vuln:

                e["title"] = f"""
                Vulnerability
                Type: {vuln}
                Risk: {round(self.G.edges[e['from'], e['to']].get('edge_cost'),2)}
                """

        self.highlight_attack_path(net)

        return net

    def highlight_attack_path(self, net):

        attack_edges = [
            (u, v)
            for u, v in zip(self.best_path[:-1], self.best_path[1:])
        ]

        for n in net.nodes:

            if n["id"] in self.best_path:

                if n["entry_point"]:
                    n["color"] = "#FFC0CB"

                elif n["end_point"]:
                    n["color"] = "#8B0000"

                else:
                    n["color"] = "#ff4d4d"

                n["size"] = 10

        for e in net.edges:

            if (e["from"], e["to"]) in attack_edges:

                e["color"] = "#ff0000"
                e["width"] = 2

    # -------------------------
    # Export
    # -------------------------

    def export_html(self, filename="dashboard.html"):

        net = self.build_network()

        net.write_html("graph_temp.html")

        with open("graph_temp.html") as f:
            graph_html = f.read().split("<body>")[1].split("</body>")[0]

        steps_html = "".join(
            f"<li><b>Step {i+1}</b>: {s}</li>"
            for i, s in enumerate(self.explain_path())
        )

        mitigation_html = "".join(
            f"<li><b>{u} → {v}</b>: {fix}</li>"
            for u, v, fix in self.mitigation_steps()
        )

        dashboard = f"""
<html>

<head>

<title>Attack Graph Dashboard</title>

<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/dist/vis-network.min.js"></script>

<link rel="stylesheet"
href="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/dist/dist/vis-network.min.css"/>

<style>

body {{
font-family: Arial, sans-serif;
margin:0;
background:#ffffff;
color:#222;
}}

.top {{
height:65vh;
border-bottom:1px solid #ddd;
padding:10px;
}}

.bottom {{
display:flex;
height:35vh;
background:#f8f9fa;
}}

.panel {{
flex:1;
padding:20px;
overflow:auto;
border-right:1px solid #ddd;
}}

.panel:last-child {{
border-right:none;
}}

.panel h2 {{
border-bottom:2px solid #ddd;
padding-bottom:5px;
margin-bottom:15px;
color:#333;
}}

li {{
margin-bottom:10px;
line-height:1.5;
}}

#mynetwork {{
width:100%;
height:600px;
background:#ffffff;
border:1px solid #ddd;
border-radius:6px;
}}

.card {{
background:#ffffff;
border-radius:6px;
box-shadow:0 2px 6px rgba(0,0,0,0.1);
}}

</style>

</head>

<body>

<div class="top">
{graph_html}
</div>

<div class="bottom">

<div class="panel">
<h2>Attack Path</h2>
<ol>
{steps_html}
</ol>
</div>

<div class="panel">
<h2>Mitigation Guidance</h2>
<ul>
{mitigation_html}
</ul>
</div>

</div>

</body>
</html>
"""

        with open(filename, "w") as f:
            f.write(dashboard)