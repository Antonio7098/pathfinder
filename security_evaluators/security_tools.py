import os
import json
from openai import OpenAI

client = OpenAI(api_key="YOUR_OPENAI_API_KEY")


class PathfinderAI:
    def __init__(self, model="gpt-4o"):
        self.model = model
        # The allowed attack types for edges as requested
        self.valid_attack_types = [
            "exploitability",
            "privilege_gain",
            "data_access_value",
            "lateral_movement_value",
            "detection_risk",
            "confidence",
            "normalized_risk_score",
        ]

    def analyze_node(self, file_path):
        """Analyzes a file and ensures all security values are 0-1."""
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()

        prompt = """
        Analyze this code and return a JSON object for a security node.
        All security_scores must be floats between 0.0 and 1.0.
        
        Fields:
        - tags: list of strings
        - confidence: float (0-1)
        - rationale: string (reasons for these ratings)
        - security_scores: {{
            "exploitability": float (0-1), "privilege_gain": float (0-1), 
            "data_access_value": float (0-1), "lateral_movement_value": float (0-1), 
            "detection_risk": float (0-1), "confidence": float (0-1)
        }}
        """

        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": f"FILE: {file_path}\nCODE:\n{code}"}],
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        return self._finalize_node(data, file_path)

    def analyze_edge(self, structural_edge, source_node, target_node):
        """Generates attack edges where the 'attack_type' is restricted to the specified list."""
        prompt = f"""
        A structural link exists: {source_node['id']} --({structural_edge['relationship_type']})--> {target_node['id']}.
        
        Determine the primary security risk of this transition.
        The 'attack_type' MUST be exactly one of: {self.valid_attack_types}.
        
        Return JSON:
        - attack_type: string
        - transition_likelihood: float (0-1)
        - required_capability: string (low/med/high)
        - detection_risk: float (0-1)
        - edge_attack_cost: float (non-negative)
        - confidence: float (0-1)
        - rationale: string (why this specific attack_type was chosen)
        """

        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        edge_data = json.loads(response.choices[0].message.content)

        # Mapping to your Attack Edge schema
        edge_data.update(
            {
                "id": f"ae:{structural_edge['id']}",
                "edge_type": "attack_transition",
                "source": source_node["id"],
                "target": target_node["id"],
                "structural_basis_edge_ids": [structural_edge["id"]],
                "excluded_flag": False,
            }
        )
        return edge_data

    def _finalize_node(self, data, path):
        """Calculates normalized_risk_score (0-1) and formats node."""
        s = data["security_scores"]
        # Using the weighted formula from earlier, but keeping result 0-1
        impact = (
            s["privilege_gain"] * 0.4
            + s["data_access_value"] * 0.4
            + s["lateral_movement_value"] * 0.2
        )
        likelihood = s["exploitability"] * 0.7 + (1.0 - s["detection_risk"]) * 0.3
        score = round(((impact * 0.6) + (likelihood * 0.4)) * data["confidence"], 3)

        data.update(
            {
                "id": str(path),
                "path": str(path),
                "node_type": "file",
                "normalized_risk_score": score,
            }
        )
        data["security_scores"]["normalized_risk_score"] = score
        return data


class AttackGraphOrchestrator:
    def __init__(self, repo_root):
        self.ai = PathfinderAI()
        self.repo_root = repo_root

    def build_security_graph(self, file_paths, structural_edges):
        """
        Takes a list of relative file paths and structural edge dicts.
        Returns the complete Canonical JSON graph.
        """
        graph = {
            "graph_id": f"repo:{os.path.basename(self.repo_root)}",
            "version": "mvp-v1",
            "nodes": [],
            "structural_edges": structural_edges,
            "attack_edges": [],
        }

        # Step 1: Analyze Nodes
        node_cache = {}
        for rel_path in file_paths:
            full_path = os.path.join(self.repo_root, rel_path)
            node_data = self.ai.analyze_node(full_path)

            # Apply your graph constraints
            node_data["entrypoint_flag"] = any(
                x in rel_path for x in ["api", "web", "public"]
            )
            node_data["target_flag"] = any(
                x in rel_path for x in ["db", "admin", "vault", "config"]
            )

            graph["nodes"].append(node_data)
            node_cache[rel_path] = node_data

        # Step 2: Analyze Attack Edges
        for se in structural_edges:
            src_id = se["source"]
            tgt_id = se["target"]

            if src_id in node_cache and tgt_id in node_cache:
                attack_edge = self.ai.analyze_edge(
                    se, node_cache[src_id], node_cache[tgt_id]
                )

                # Check constraints: edge must reference existing nodes
                graph["attack_edges"].append(attack_edge)

        return graph


# # --- Demo Setup ---
# if __name__ == "__main__":
#     orchestrator = AttackGraphOrchestrator(repo_root="./vuln-bank")

#     # 1. Inputs: List of files and their AST-derived structural links
#     file_list = ["api/login.js", "services/db.js"]
#     struct_links = [
#         {
#             "id": "se:login->db",
#             "source": "api/login.js",
#             "target": "services/db.js",
#             "relationship_type": "calls",
#             "edge_type": "structural",
#         }
#     ]

#     # 2. Generate the full security context graph
#     complete_graph = orchestrator.build_security_graph(file_list, struct_links)

#     # 3. Save to file for your frontend visualizer
#     with open("attack_graph.json", "w") as f:
#         json.dump(complete_graph, indent=2, fp=f)
