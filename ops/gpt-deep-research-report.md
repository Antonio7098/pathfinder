# Defensive Autonomy for Agentic Cyber-Threats

## How cyber-threats became “agentic” and time-compressed

The plausibility of “Agentic Cyber-Warfare” in 2026 is less about a single new exploit and more about **compound acceleration**: faster intrusion velocity, cheaper “as-a-service” commercialization, and a widening attack surface created by AI-connected workflows. Threat intelligence reporting in the past two years has consistently emphasized **speed** as the strategic driver for both attackers and defenders. For example, entity["company","CrowdStrike","cybersecurity firm"]’s 2026 threat reporting highlights that average eCrime “breakout time” (time from initial compromise to lateral movement) fell to **~29 minutes**, with extremely fast cases measured in **seconds**, shrinking defenders’ decision windows from “hours” to “minutes.” citeturn5search3turn5search9

That “minutes-scale” reality coexists with a different metric that is still often “days-scale”: **dwell time** (how long an attacker remains undetected). entity["company","Mandiant","incident response firm"] reports a **global median dwell time of 11 days** in 2024 investigations, but also shows that **adversary notification** (common in extortion/ransomware) can compress detection to a median of **5 days**—still long enough for modern, fast intrusions to do serious damage. citeturn9view0

What makes this “agentic” (rather than just “automated” like older botnets) is the increasingly normal availability of **AI-enabled reconnaissance and decision support**. entity["organization","Europol","eu law enforcement agency"] documents that major cybercrime forums (e.g., Cracked and Nulled, prior to takedowns) offered **AI-based tools and scripts** that could automatically scan for vulnerabilities and optimize attacks—lowering skill barriers and increasing operational tempo. citeturn9view3

Meanwhile, defenses predicated on static perimeters are strained by the fact that attackers don’t need to “break in loudly” if they can operate through legitimate channels or abused credentials. entity["company","Verizon","telecom company"]’s 2025 DBIR findings reinforce that ransomware/system intrusion patterns increasingly leverage **vulnerability exploitation** as a key access vector, and also that “actor disclosure” (ransomware groups posting on leak sites) has become a dominant discovery method—an uncomfortable sign that many organizations still learn about incidents late. citeturn11view0

European-level assessments echo the same pattern: entity["organization","ENISA","eu cybersecurity agency"] points to rapid weaponization of disclosed vulnerabilities and highlights **AI-supported phishing** as a defining feature of the threat landscape, framing an environment of continuous, convergent campaigns that erode resilience over time. citeturn9view2

The net effect is a strategic inversion: defenders can’t only optimize “prevent,” because **the time-to-impact is now too short**; they must optimize “detect → decide → mitigate” as a tightly engineered loop. That is the core logic behind the theme’s emphasis on **Mean Time To Respond (MTTR)** and “defensive autonomy” (automation/agents that can safely execute response under strong governance). citeturn5search3turn21view0

## Shadow Agent risk as a first-class security problem

The theme’s most forward-looking point is also its most realistic: once organizations deploy internal AI agents (ticket triage bots, code-change agents, finance assistants, IT copilots), the main danger isn’t only “external malware,” but **internal automation executing untrusted intent**.

Two families of failure are especially relevant for a hackathon project that wants to feel truly “2026.”

**Prompt injection (direct and indirect)**  
The entity["organization","OWASP","app security foundation"] GenAI Security Project frames “Prompt Injection” as a top risk for LLM applications, including **indirect prompt injection** where malicious instructions are embedded in data sources the model consumes (web pages, documents, emails). citeturn0search1turn19search5 This is not theoretical—recent research and security reporting continues to show that tool-using agents can be steered by hostile content if systems fail to separate “instructions” from “data.” citeturn0search2turn0search10turn4search1

The entity["organization","National Cyber Security Centre","uk cybersecurity agency"] (UK) makes an especially important design argument: prompt injection should be treated less like “SQL injection with better sanitization” and more like a **confused deputy** problem—systems that are inherently “confusable” can be coerced into taking privileged actions on behalf of untrusted inputs. That framing directly supports your theme’s “verify intent of every autonomous action” requirement. citeturn4search0turn4search3

**Memory poisoning / long-term persistence attacks on agents**  
As organizations add long-term memory (RAG stores, vector DBs, “agent memory,” ticket histories, CRM notes), attackers gain a new foothold: poison the memory so future actions drift. This is now extensively discussed in the research literature. For example, NeurIPS work like **AGENTPOISON** demonstrates backdoor-style attacks targeting LLM agents by poisoning long-term memory or RAG knowledge bases. citeturn12search14 USENIX work like **PoisonedRAG** analyzes knowledge corruption attacks against retrieval-augmented generation. citeturn12search16 Newer work explicitly naming “memory poisoning” for persistent-memory agents further confirms the risk is being formalized and benchmarked. citeturn12search1turn12search7

**“Excessive agency” as the vulnerability that turns AI errors into real-world impact**  
Even if an LLM makes a “normal” mistake (hallucination, wrong classification), harm usually requires one extra ingredient: the system grants the model overly broad authority (ability to run commands, patch code, move money, change firewall rules). OWASP formalizes this as **Excessive Agency**, where damaging actions can be performed in response to unexpected or manipulated model outputs. citeturn20search20turn19search5

The most important design implication for your project: you can’t make a perfect classifier, but you *can* build a system where **any single model failure is contained by governance**, and where every action is logged with evidence for audit and approval. citeturn4search0turn20search20

image_group{"layout":"carousel","aspect_ratio":"16:9","query":["security operations center war room dashboard incident response","cyber deception honeypot architecture diagram","zero trust architecture concept diagram","LLM prompt injection diagram"],"num_per_query":1}

## Defensive autonomy that a CISO can sign off on

A hackathon project in this theme will stand out if it treats “autonomy” as an engineering discipline with explicit controls—rather than “let the agent do things.”

A defensible architecture can be justified using mainstream security governance sources:

**Anchor incident response in established lifecycles and taxonomies**  
entity["organization","NIST","us standards agency"]’s Cybersecurity Framework 2.0 emphasizes the six functions (Govern, Identify, Protect, Detect, Respond, Recover). citeturn2search0turn2search4 NIST’s updated incident response guidance (SP 800-61r3, 2025) explicitly reframes incident response as continuous, integrated risk management—incidents are frequent, recovery can take weeks or months, and improvement must happen continuously. citeturn21view0

**Adopt “zero trust” assumptions for agents and tools**  
NIST’s Zero Trust Architecture guidance centers on continuously evaluating trust rather than relying on network location (the “perimeter”). This aligns well with “verify the intent of every autonomous action.” citeturn3search12

**Make auditability a product feature, not an afterthought**  
Security response systems live or die on evidence. NIST’s log management guidance emphasizes the need for sound, enterprise-wide log management so that security records are captured and usable for detection and analysis. citeturn3search2turn3search5 NIST’s newer log management planning work (SP 800-92r1 IPD) is literally structured as a playbook for improving logging practices, reflecting how central logs are to operational security. citeturn18search3turn18search0

**Govern AI like a risk-bearing system**  
NIST’s AI RMF frames trustworthy AI via characteristics like “accountable and transparent” and “explainable and interpretable,” which gives you language for why your dashboard must show “why the agent acted.” citeturn2search5turn2search1 In parallel, entity["organization","ISO","standards organization"]/IEC 42001 defines requirements for an AI management system, reinforcing that governance and continual improvement are expected organizational behaviors for AI deployments. citeturn7search11turn15search9

**Treat timing pressure as compliance pressure, not only technical pressure**  
Because you’re in Europe/London, it’s worth noting that EU cybersecurity regulation increasingly demands fast notifications. The NIS2 Directive includes reporting obligations such as an early warning within 24 hours and a follow-up notification within 72 hours. citeturn8search0turn8search2 The EU’s DORA framework for financial entities is also active (applies from 17 Jan 2025) and defines structured incident reporting; European supervisory authorities have published technical standards and timelines for incident notifications. citeturn8search9turn8search7turn16search2

For your project, the governance takeaway is straightforward: defensive autonomy must be able to show, quickly and clearly:
- **What happened** (facts/events)
- **Why it was considered risky** (evidence + mapped technique/outcome)
- **What action was taken** (or proposed)
- **Which policy allowed it** (or which approval was required)
- **What changed** (diffs, tickets, patches, rule updates)

That is “explainable response,” and it is much closer to what CISOs and auditors accept than an opaque agent. citeturn2search5turn3search2turn8search0

## Creative project ideas built for MTTR and intent verification

Below are six project concepts that fit your theme. Each idea is designed to be demoable in a hackathon, measurable on MTTR, and structured so the system can expose **audit trails** without requiring you to reveal raw model chain-of-thought.

**Intent Firewall for Tool-Using Agents**  
Core idea: build a “tool-call gateway” that all internal agents must use. It inspects every proposed action (e.g., “patch container,” “rotate credential,” “block egress,” “open ticket”), assigns risk, and enforces a policy: auto-approve low-risk actions; require human approval for high-risk actions; deny actions triggered by untrusted content patterns. This directly addresses the NCSC “confused deputy” framing and OWASP’s “excessive agency” risk. citeturn4search0turn20search20  
Demo: show a benign agent reading an external document containing an indirect prompt injection; the agent tries to exfiltrate data via a tool, and the Intent Firewall blocks it and logs exactly which policy gate triggered.

**Sleeper-Agent Discovery via Memory Integrity Diffing**  
Core idea: build an “Auditor Agent” that continuously checks agent memory stores (RAG corpora + persistent instruction memory) for anomalies: new “instructions” injected into memory, semantically suspicious retrieval hits, and drift in agent behavior compared to a baseline. The logic is grounded in the growing literature on memory poisoning and agent backdoors. citeturn12search14turn12search16turn12search1  
Demo: seed a small RAG store with a poisoned entry; show that the Auditor flags “instruction-like text embedded in a knowledge document,” quarantines it, and produces a before/after memory diff plus impacted agent capabilities.

**Autonomous Honeypot Swarm that Matches Your Real Stack**  
Core idea: generate decoy cloud assets *dynamically* when scanning behavior is detected: fake S3-equivalent buckets, “high-value” BigQuery-like tables, or honey-APIs with realistic schemas. This aligns with deception research; container-based honeynet architectures like “HoneyFactory” show how deception environments can be generated and monitored systematically. citeturn16search0turn14image3  
Demo: when an attacker scanner touches an exposed service, your system deploys a decoy environment, captures TTPs, and automatically generates detection rules and a containment recommendation. Score success by reducing time-to-triage (humans typically need time to validate if a scan is real).

**KEV-to-Patch Autopilot with SBOM-Aware Blast Radius**  
Core idea: take the example workflow you were given (scrape CVEs, match to stack) and make it operationally sharp by prioritizing vulnerabilities that are *actually exploited* and then auto-generating remediation steps. entity["organization","CISA","us cyber agency"]’s Known Exploited Vulnerabilities (KEV) catalog is explicitly designed to focus remediation on vulnerabilities exploited in the wild. citeturn16search4turn6search3  
Pair that with SBOM-style component mapping so your agent can answer: “Which deployed containers include the vulnerable library?” (and therefore which services must be patched first). citeturn3search1turn3search10  
Demo: inject a “new KEV added” event; the system identifies impacted services, opens a PR with version bumps, runs tests, and (if tests pass) deploys a patched container automatically, logging every step.

**Non-Human Identity Radar for Secrets, Tokens, and Shadow AI**  
Core idea: build a detection + remediation agent focused on the “credential layer” rather than malware. DBIR reporting includes examples of long remediation times for leaked secrets (e.g., secrets exposed in code repositories) and also highlights how employees access GenAI services outside corporate identity controls. citeturn11view0  
Add “agent identity”: each internal agent gets a scoped identity, and any unusual token usage triggers containment (rotate token, revoke session, require re-auth).  
Demo: simulate a leaked token; show automated revocation + replacement + audit event + “who/what used it” narrative in the dashboard.

**Predictive Threat Feed Synthesis with Evidence-Linked Controls**  
Core idea: your system ingests OSINT signals (CVE/NVD updates, CISA KEV, vendor advisories, and carefully selected public threat reporting) and produces “action packages”: suggested detections, candidate firewall/WAF rules, and patch recommendations. This is consistent with how NVD enrichment and KEV style catalogs are intended to help downstream remediation decisions. citeturn6search2turn16search4  
Demo: show that a newly disclosed vulnerability is detected as relevant to your tech stack (via SBOM/census), and your system immediately creates a mitigation plan: temporary compensating control + patch plan + rollback plan.

## A reference architecture that matches your example stack and is demo-friendly

A strong hackathon implementation is one that feels “end-to-end” even if each component is simplified. The main trick is to build it as an **event-driven pipeline** with a “Threat Brain” datastore and a “War Room” UI, but with governance gates so the system is safe to demo.

**Ingestion and normalization layer**  
- Pull vulnerability and threat-intel signals from: CVE/NVD enrichment feeds, CISA KEV catalog, and a small set of curated OSINT sources. NVD explicitly enriches CVEs after publication to the CVE list, and KEV is designed to highlight known exploitation. citeturn6search2turn16search4  
- Normalize into a single “Threat Event” schema: {signal_source, timestamp, affected_products, exploit_status, confidence, links, recommended_actions}.

**Risk triage layer**  
- Use a coding-capable model (like “Devstral”) to map the threat to your internal stack: parse dependency manifests or SBOMs and determine if the vulnerable component exists in deployed images. citeturn2search3turn3search1  
- Attach explainability artifacts: which package matched, which version range, which service owner, and which policy requires approval.

**Threat Brain datastore and query**  
- If you stay aligned to the suggested Google stack: store events in BigQuery (serverless data warehouse) so your UI can query and filter quickly. citeturn17search0turn17search4

**Orchestration and response layer**  
- Event triggers can run serverless remediation jobs (for example, Cloud Run services) to execute playbooks. Cloud Run is positioned as a fully managed serverless platform for running containers. citeturn17search2turn17search13  
- Notifications to a SOC channel can be sent using Slack incoming webhooks (simple JSON payloads to post messages). citeturn17search3

**War Room dashboard**  
- The UI should show “Decision Cards,” not raw chain-of-thought:
  - Evidence (logs, CVE IDs, diff links, IoCs)
  - Risk score and why (e.g., “KEV-listed + internet-facing + asset criticality”)
  - Mapped tactic/technique vocabulary for communication (if you use ATT&CK-style language)  
  - Action taken/proposed, plus approval state
  - Full immutable audit log of tool calls and configuration changes

This “decision card” approach aligns with the transparency/explainability direction called out by AI governance frameworks without forcing you to expose sensitive internal reasoning text. citeturn2search5turn4search0turn3search2

## Proving a 50% MTTR improvement with an evaluation that looks real

To win on this theme, treat your project like a measurable cyber capability. Build a small evaluation harness that can run in the hackathon environment.

**Define MTTR as a measurable pipeline latency**  
Use at least two clocks:
- **MTTI (Mean Time To Identify)**: first signal → incident created with evidence attached  
- **MTTM (Mean Time To Mitigate)**: first signal → compensating control applied (block/isolate/rotate) or patch deployed  
This is consistent with how major incident response guidance emphasizes detection, response, recovery and continuous improvement. citeturn21view0turn2search0

**Use a realistic “speed threat” benchmark**  
Because breakout is now measured in minutes, use a benchmark scenario that forces fast decisions:
- “New KEV vulnerability affects an internet-facing service”
- “Suspicious agent tool-call triggered by untrusted content”
- “RAG memory store contains poisoned entry”
Your KPI target can explicitly reference modern breakout-time dynamics. citeturn5search3turn4search0

**Do an A/B comparison**  
- Baseline: a human analyst receives an alert and follows a playbook manually  
- Treatment: your defensive agent proposes and executes the mitigation under policy  
Your “50% reduction” claim becomes: median(Treatment MTTM) ≤ 0.5 × median(Baseline MTTM). The credibility comes from showing the timestamps and evidence objects in your War Room.

**Auditability score**  
Add a second score so you don’t “win by recklessness”:
- % of mitigations that include: evidence bundle + policy rule + change diff + rollback plan  
This directly reflects the idea that response must be accountable and transparent, not an opaque black box. citeturn2search5turn3search2turn20search20

**Regulatory realism (optional but powerful in Europe)**  
If you want an extra “enterprise believability” layer, include a “reporting readiness” view:
- Can your system produce an “early warning” summary quickly (analogous to NIS2-style reporting cadence)? citeturn8search0turn8search2  
Even if you’re not building compliance tooling, it’s a persuasive way to show your incident timeline and evidence are structured enough for real-world reporting pressure.