# Service-Level Scaling vs File-Level Scaling

This note explains why **service-level security analysis** can scale better than **file-level security analysis** in Pathfinder's current implementation, while also making the current bottleneck explicit.

The short version is:

* downstream security analysis scales with `nodes + edges`
* file mode analyzes **every file** and **every structural edge**
* service mode analyzes **every service** and **every service edge**
* a service graph can be much smaller than a file graph
* but the current service-grouping step is a large one-shot LLM call and becomes the next scaling limit

This document is grounded in the current implementation and saved artifacts in this repository.

---

## Where the scaling comes from

Pathfinder's security stage makes:

* one LLM call per node
* one LLM call per edge

for whichever graph mode it is analyzing.

In code:

* file-mode graph inputs are built in `pathfinder/pipeline/service.py` by `_build_file_security_graph_input`
* service-mode graph inputs are built in `pathfinder/pipeline/service.py` by `_build_service_security_graph_input`
* node analysis happens in `_SecurityNodeStage`
* edge analysis happens in `_SecurityEdgeStage`

That means the dominant online security-analysis cost is approximately:

`security_calls ~= node_count + edge_count`

So the scaling comparison is not abstract. It is directly tied to the graph cardinality Pathfinder feeds into the security evaluator.

---

## Current repository numbers

The saved artifacts under `artifacts/full-run-service-2026-03-11/` show:

### File graph

From `structural_graph.json`:

* `file_count = 74`
* `structural_edge_count = 333`

So file-mode security analysis would make:

`74 + 333 = 407` LLM calls

### Service graph

From `service_grouping.json` and `service_graph.json`:

* `service_count = 8`
* `service_edge_count = 19`

So service-mode security analysis would make:

`8 + 19 = 27` LLM calls

Service mode also pays for one extra service-grouping call up front, so total LLM calls become:

`1 + 8 + 19 = 28`

### Empirical reduction on this repo

Using those counts:

* node reduction: `74 / 8 = 9.25x`
* edge reduction: `333 / 19 = 17.53x`
* downstream security-call reduction: `407 / 27 = 15.07x`
* total-call reduction including grouping: `407 / 28 = 14.54x`

That is the concrete scaling argument: once the graph has been compressed into services, the expensive node-and-edge security analysis stage becomes much smaller.

---

## Cost estimates from recorded token usage

The evaluation artifacts under `artifacts/evaluation/` provide real token usage for the current security-evaluation prompts.

Using `artifacts/evaluation/minimax_demo_vuln_repo_eval.json` and the built-in MiniMax pricing in `pathfinder/evaluation/pricing.py`:

* average file-risk call cost: about `$0.000701`
* average edge-analysis call cost: about `$0.001059`

Projecting those observed averages onto this repository's graph sizes:

### File-based security analysis

`74 * 0.000701 + 333 * 0.001059 ~= $0.4047`

### Service-based security analysis only

`8 * 0.000701 + 19 * 0.001059 ~= $0.0257`

### Service grouping cost

The saved `service_grouping.json` artifact recorded:

* `input_tokens = 41,574`
* `output_tokens = 773`
* `total_tokens = 42,347`

At the MiniMax prices configured in the repo:

* input price: `$0.30 / 1M`
* output price: `$1.20 / 1M`

That one grouping call is roughly:

`41,574 / 1,000,000 * 0.30 + 773 / 1,000,000 * 1.20 ~= $0.0134`

### Service-based total including grouping

`$0.0257 + $0.0134 ~= $0.0391`

### Cost comparison on this repo

Using these recorded averages and this repository's graph sizes:

* file-based total: about `$0.4047`
* service-based total including grouping: about `$0.0391`
* estimated improvement: about `10.3x`

This is the strongest concrete claim supported by the current artifacts: **service-level analysis can reduce the dominant downstream security-analysis cost by roughly an order of magnitude on this repository**.

---

## Simple scaling laws

Let:

* `F` = file count
* `E` = file structural edge count
* `S` = service count
* `E_s` = service edge count
* `a` = average node-analysis cost
* `b` = average edge-analysis cost
* `G(F, E)` = service-grouping cost

Then:

### File mode

`C_file ~= aF + bE`

### Service mode

`C_service ~= G(F, E) + aS + bE_s`

The service-mode advantage appears when:

* `S << F`
* `E_s << E`

For this repository, the observed compression ratios are:

* `S ~= F / 9.25`
* `E_s ~= E / 17.53`

If similar ratios held on larger repos, the downstream security-analysis stage would keep shrinking by roughly the same factor.

### Mathematical derivations

Snce we're assuming every file/service is used we can model the files as vertices and connections as edges in a connected graph. For $n$ files this means a minimum of $n-1$ edges where each file is used by exactly one other file (except the main/app file). In the worst case, we avoid cyclical calls by modeling the repository as a digraph instead, which has at most $\sum{i}_{i=1}^{n-1} = (n-1) + (n-1) + ... + 2 + 1 = \frac{n(n+1)}{2}$ edges. Combined with the LLM calls for the $n$ nodes, this leaves between $2n-1$ and $\frac{n(n+1)}{2}$ calls.

---

## Example larger-repo projections

These are simple extrapolations using the observed ratios above. They are useful for reasoning, not as guarantees.

### If a repo had 1,000 files

Using the current observed edge density and compression ratios:

* estimated file edges: about `4,500`
* estimated services: about `108`
* estimated service edges: about `257`

Then:

* file mode: about `5,500` security-analysis calls
* service mode: about `366` total calls including grouping
* reduction: about `15x`

Cost projection with current observed averages:

* file mode: about `$5.47`
* service mode: about `$0.53`

### If a repo had 5,000 files

Rough projection:

* estimated file edges: about `22,500`
* estimated services: about `541`
* estimated service edges: about `1,284`

Then:

* file mode: about `27,500` security-analysis calls
* service mode: about `1,826` total calls including grouping

Cost projection:

* file mode: about `$27.34`
* service mode: about `$2.65`

These examples show the same pattern: if the service graph stays much smaller than the file graph, the security-analysis stage scales much better.

---

## The important caveat

The current implementation does **not** make service-level analysis universally scalable yet.

The reason is the current service-grouping prompt.

The saved grouping artifact already used:

* `42,347` total tokens

to group just:

* `74` files
* `333` structural edges

That prompt includes rich structural summaries, directory summaries, and graphcode evidence. This is useful for quality, but it means the grouping step itself can become the next bottleneck.

If we scale the current grouping prompt naively, its token volume grows too quickly for large repositories.

Very rough linear extrapolation from the current artifact gives:

* `1,000` files -> about `562k` grouping input tokens
* `5,000` files -> about `2.81M` grouping input tokens
* `10,000` files -> about `5.62M` grouping input tokens

So the honest conclusion is:

* **downstream service-based security reasoning scales much better than file-based reasoning**
* **the current one-shot grouping prompt does not**

For large repositories, service grouping would need a more scalable strategy such as:

* hierarchical grouping
* directory-by-directory grouping
* staged clustering plus reconciliation
* bounded summaries instead of one giant prompt

---

## Bottom line

Pathfinder's current implementation supports a precise claim:

* file-mode security analysis scales with file nodes plus structural edges
* service-mode security analysis scales with service nodes plus service edges
* on this repository, that reduces downstream LLM calls from `407` to `27`, or `28` including grouping
* using current observed token-cost averages, that is about a `10x` total cost reduction

But the current implementation also requires an equally clear caveat:

* the existing service-grouping step is a large one-shot LLM prompt
* that prompt is the next scaling bottleneck
* therefore the service-level approach is more scalable for the **security-analysis stage**, but not yet fully scalable end-to-end for very large repositories

That distinction matters. It keeps the argument accurate, reviewable, and grounded in real Pathfinder artifacts.
