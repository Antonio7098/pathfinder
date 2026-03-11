# Attack Graph Engine

## Purpose

The Attack Graph Engine provides the core structural modeling and path analysis layer for Pathfinder's security analysis workflow. It constructs a directed attack graph representing potential attacker movement through a system and identifies optimal attack paths between entry points and high-value target nodes.

## Core Responsibilities

- **Representation:** Modeling application components as graph nodes.
- **Transitions:** Modeling vulnerabilities and trust relationships as graph edges.
- **Weighting:** Computing attacker cost–reward metrics.
- **Optimization:** Identifying the most "attractive" attacker paths.
- **Export:** Formatting results for visualization and dashboard rendering.

## Separation of Concerns

To ensure the model remains deterministic, testable, and reproducible, the engine is intentionally isolated from:

- Repository extraction and static analysis.
- Vulnerability discovery.
- Reporting and LLM-driven mitigation generation.

---

## Graph Model

The attack graph is implemented as a directed graph (`networkx.DiGraph`).

- **Nodes:** Software components or execution units (files, services, scripts).
- **Edges:** Attacker transitions enabled by vulnerabilities or trust relationships.

> **Flow Example:** Entry Point → Service Layer → Privileged Component → Sensitive Target

The graph encodes both attacker costs and attacker rewards, which together determine path attractiveness.

### Node Model

Each node represents an executable unit. Nodes are instantiated using the repository's existing node class abstraction.

| Attribute               | Description                                               |
|-------------------------|-----------------------------------------------------------|
| `entry_point`           | Node represents an externally reachable component         |
| `end_point`             | Node represents a high-value target (data or privilege)   |
| `exploitability`        | Relative ease of exploitation                             |
| `lateral_movement_value`| Attacker value of moving deeper into the system           |
| `data_access_value`     | Value of data accessible from the node                    |
| `privelidge_gain`       | Potential privilege escalation value                      |
| `node_value`            | Aggregate value used in reward calculation                |

### Edge Model

Edges represent transitions between nodes, encoding properties associated with exploiting a specific vulnerability.

| Attribute               | Description                                                             |
|-------------------------|-------------------------------------------------------------------------|
| `vulnerability`         | The specific vulnerability enabling the transition                      |
| `transition_likelihood` | Likelihood an attacker can successfully perform the step               |
| `detection_risk`        | Risk of detection during the transition                                 |
| `edge_attack_cost`      | Base attacker cost                                                       |
| `edge_cost`             | Computed final transition cost                                           |

---

## Scoring Model

The engine utilizes a cost–reward scoring framework to evaluate path viability.

1. **Node Reward**

   The attacker reward associated with reaching a specific node:

   ```python
   if end_point:
       reward = (data_access_value * 5) + (privelidge_gain * 2)
   elif entry_point:
       reward = exploitability * 3
   else:
       reward = lateral_movement_value
   ```

2. **Edge Cost**

   The cost incurred by exploiting a vulnerability:

   \[math\] $cost = (edge\_attack\_cost \times 2) + (detection\_risk \times 3) + (1 - transition\_likelihood)$

3. **Edge Weight**

   The final weight used during path search:

   \[math\] $weight = edge\_cost - node\_reward(target)$

   This formulation encourages paths that minimize exploitation cost while maximizing attacker reward.

---

## Path Search

The engine searches for the most attractive path where `node.entry_point == True` and `node.end_point == True`.

Path discovery is executed via:

```python
networkx.shortest_path(..., weight="weight")
```

The "best" path is defined as the sequence with the lowest cumulative weight.

## Attack Path Explanation

Once identified, paths are converted into human-readable sequences for the dashboard:

```
web.js --[auth_bypass]--> auth.py --[sql_injection]--> db.py
```

## Mitigation Guidance

Each vulnerability type maps to a recommended mitigation. Mitigations are prioritized for edges along the selected attack path to effectively "break" the chain.

| Vulnerability      | Mitigation                                                 |
|--------------------|------------------------------------------------------------|
| sql_injection      | Use parameterized queries and input validation             |
| auth_bypass        | Implement strong authentication and session validation     |
| weak_secrets       | Move secrets to environment variables or vault            |
| default            | Review access controls and sanitize inputs                |

---

## Visualization & Dashboard

The engine supports interactive visualization using PyVis.

**Visual Conventions**

- **Node Type**
  - Entry Node: Cyan
  - Internal Node: Grey
  - Target Node: Yellow
- **Path Highlighting:**
  - Entry: Pink
  - Intermediate: Red
  - Target: Dark Red
- **Edges:** Increased width and red coloring.

**Dashboard Layout**

```
+---------------------------------------+
|            Graph View                 |
+-------------------+-------------------+
| Attack Path       | Mitigation Guide  |
+-------------------+-------------------+
```

---

## Integration with Pathfinder

The engine acts as the analytical bridge between structural extraction and reporting.

1. Repository Analysis
2. Attack Graph Construction
3. Path Search
4. Attack Path Artifact
5. Recommendation Reporting

---

## Design Principles

- **Deterministic behavior:** Graph construction and path search do not rely on stochastic processes.
- **Separation of concerns:** The engine does not perform its own vulnerability discovery or LLM reasoning.
- **Extensibility:** Designed to eventually support probabilistic graphs, multi-path enumeration, and CVSS-weighted risk scoring.
