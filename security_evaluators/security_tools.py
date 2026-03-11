import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from pprint import pprint

load_dotenv()

OPEN_AI_KEY = os.getenv("OPEN_AI_KEY")

client = OpenAI(api_key=OPEN_AI_KEY, base_url="https://openrouter.ai/api/v1")


class PathfinderAI:

    def __init__(
        self, model="gpt-4o"
    ):  # Default is not very good, better to use something like gpt-5.3-codex
        self.model = model
        # The allowed attack types for edges as requested
        self.valid_attack_types = [
            "sql_injection",
            "broken_authentication",
            "broken_authorization",
            "idor",
            "unsafe_deserialization",
            "command_injection",
            "session_abuse",
            "privilege_propagation",
            "unsafe_database_access",
        ]

    def analyze_node(self, file_path):
        """Analyzes a file and ensures all security values are 0-1."""
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()

        prompt = """
        Analyze this code and return a JSON object for a security summary.
        All security_scores must be floats between 0.0 and 1.0.
        
        Structure:
        {
            tags: list of strings; optional labels relevant to the file
            confidence: float (0-1); confidence in this assessment 
            rationale: string (reasons for these ratings)
            security_scores: {
                "exploitability": float (0-1),
                "privilege_gain": float (0-1), 
                "data_access_value": float (0-1),
                "lateral_movement_value": float (0-1), 
                "detection_risk": float (0-1),
                "confidence": float (0-1)
            }
        }
        """

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"FILE: {file_path}\nCODE:\n{code}"},
            ],
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)

        # pprint(data)
        # exit()

        return self._finalize_node(data, file_path)

    def analyze_edge(self, structural_edge, source_node, target_node):
        """Generates a list of potential attack edges for a structural link."""

        with open(source_node["id"], "r", encoding="utf-8") as f:
            source_code = f.read()

        with open(target_node["id"], "r", encoding="utf-8") as f:
            target_code = f.read()

        print("-" * 50)
        print("got data")
        print("-" * 50)

        prompt = f"""
        A structural link exists: {source_node['id']} --({structural_edge['relationship_type']})--> {target_node['id']}.
        
        Analyze this connection and identify ALL likely security risks/attack paths. 
        For each risk, create an entry in a list named 'attacks'.
        
        The 'attack_type' for each MUST be exactly one of: {self.valid_attack_types}.
        
        Return JSON format:
        {{
            "attacks": [
                {{
                    "attack_type": string,
                    "transition_likelihood": float (0-1),
                    "required_capability": string (low/med/high),
                    "detection_risk": float (0-1),
                    "edge_attack_cost": float (non-negative),
                    "confidence": float (0-1),
                    "rationale": string
                }}
            ]
        }}
        """
        print("-" * 50)
        print("got prompt")
        print("-" * 50)

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"SOURCE FILE: {source_node['id']}\nCODE:\n{source_code}\n\nTARGET FILE: {target_node['id']}\nCODE:\n{target_code}",
                },
            ],
            response_format={"type": "json_object"},
        )
        print("-" * 50)
        print("got response")
        print("-" * 50)

        raw_data = json.loads(response.choices[0].message.content)
        attack_list = raw_data.get("attacks", [])

        print("-" * 50)
        print("got preprocessed edges")
        print("-" * 50)
        processed_edges = []
        for index, attack in enumerate(attack_list):
            # Ensure unique ID by appending the index and attack type
            attack.update(
                {
                    "id": f"ae:{structural_edge['id']}_{attack['attack_type']}_{index}",
                    "edge_type": "attack_transition",
                    "source": source_node["id"],
                    "target": target_node["id"],
                    "structural_basis_edge_ids": [structural_edge["id"]],
                    "excluded_flag": False,
                }
            )
            processed_edges.append(attack)
        print("-" * 50)
        print("got postprocessed edges")
        print("-" * 50)

        return processed_edges

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

    def calculate_aggregate_risk(self, node_data, attack_edges):
        """
        Calculates a more nuanced risk score based on the variety
        and severity of all identified attack edges originating from this node.
        (not currently in use)
        """
        if not attack_edges:
            return node_data["normalized_risk_score"]

        # 1. Impact: Find the most damaging potential attack
        # We weight transition_likelihood and the inherent impact of the attack_type
        impact_scores = []
        for edge in attack_edges:
            # High likelihood transitions to high-value targets rank highest
            edge_impact = edge["transition_likelihood"] * (
                1.0 - edge["edge_attack_cost"] / 100
            )
            impact_scores.append(edge_impact)

        max_impact = max(impact_scores) if impact_scores else 0

        # 2. Complexity: If there are MANY types of attacks, the risk is higher
        multi_attack_penalty = min(len(attack_edges) * 0.05, 0.2)

        # 3. Final Calculation
        base_score = node_data["normalized_risk_score"]
        refined_score = round(
            min((base_score + max_impact + multi_attack_penalty) / 2, 1.0), 3
        )

        return refined_score


class AttackGraphOrchestrator:
    def __init__(self, repo_root):
        self.ai = PathfinderAI()
        self.repo_root = repo_root

    def build_security_graph(self, file_paths, structural_edges):
        graph = {
            "graph_id": f"repo:{os.path.basename(self.repo_root)}",
            "version": "mvp-v1",
            "nodes": [],
            "structural_edges": structural_edges,
            "attack_edges": [],
        }

        # Step 1: Analyze Nodes (Remains the same)
        node_cache = {}
        for rel_path in file_paths:
            full_path = os.path.join(self.repo_root, rel_path)
            node_data = self.ai.analyze_node(full_path)
            node_data["entrypoint_flag"] = any(
                x in rel_path for x in ["api", "web", "public"]
            )
            node_data["target_flag"] = any(
                x in rel_path for x in ["db", "admin", "vault", "config"]
            )
            graph["nodes"].append(node_data)
            node_cache[rel_path] = node_data

        # Step 2: Analyze Attack Edges (Modified to handle multiple edges)
        for se in structural_edges:
            src_id = se["source"]
            tgt_id = se["target"]

            if src_id in node_cache and tgt_id in node_cache:
                # This now returns a list of attack edges
                list_of_attacks = self.ai.analyze_edge(
                    se, node_cache[src_id], node_cache[tgt_id]
                )
                graph["attack_edges"].extend(list_of_attacks)

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
