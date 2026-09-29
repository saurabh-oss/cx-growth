"""
TO-BE architecture model — the target state.

This mirrors the target architecture diagram so the demo can render it live and
light components up as a contact flows through them. Each component carries an honest
`status`, which is what makes this useful rather than decorative:

    built     — working in this POC today
    partial   — partially modelled; the surface exists, the depth does not
    planned   — on the POC roadmap, with the increment that delivers it
    reference — real in the target architecture, deliberately not demoed
                (infrastructure with no demo value)

Colour keys map to the legend on the source diagram:
    existing | vendor | ai | connector | foundation
"""

# The "Magnificent 7" are goal-based AI AGENTS, not architecture components. They are
# defined in AGENTS_M7 below and mapped onto the components where each one operates.

LEGEND = [
    {"key": "existing",   "label": "Existing (AS-IS)"},
    {"key": "vendor",     "label": "NEW — Acme CX / AI Stack"},
    {"key": "ai",         "label": "NEW — AI Enablement"},
    {"key": "connector",  "label": "Integration / Connector"},
    {"key": "foundation", "label": "Foundation (Existing)"},
]

STATUS_LABEL = {
    "built":     "Built in this POC",
    "partial":   "Partially modelled",
    "planned":   "On the POC roadmap",
    "reference": "Reference only — not demoed",
}


def _c(id, name, kind, status, items, poc, star=False, m7=False, increment=None):
    return {"id": id, "name": name, "kind": kind, "status": status, "items": items,
            "poc": poc, "star": star, "m7": m7, "increment": increment}


LAYERS = [
    {
        "id": "channels", "type": "row", "title": "Channels",
        "components": [
            _c("voice", "Voice Channels", "existing", "partial",
               ["Inbound / Outbound Calls", "IVR / Callback"],
               "Inbound voice is modelled end to end — IVR treatment, captured intent, identity, queue wait and "
               "contact ID — including a Spanish contact handled in English and an unscripted contact spoken or "
               "typed live. Audio is synthesised in the browser. Telephony, outbound and callback are not connected: "
               "that is the Amazon Connect increment."),
            _c("digital", "Digital Channels", "existing", "partial",
               ["Web Chat • Email • SMS", "Mobile App"],
               "Chat appears as a channel on one contact in the queue. Email and SMS are not modelled."),
            _c("concierge", "Acme Brand Assistant", "vendor", "planned",
               ["Conversational AI (Text/Voice/Image)", "Product Advisor + Site Advisory Agent", "Cross-Session Persistence"],
               "Increment C: a pre-contact Concierge session that resolves what it can, then escalates to a live agent with full context handoff.",
               star=True, increment="C"),
            _c("selfservice", "Self-Service AI Portal", "ai", "partial",
               ["AI Knowledge Base Bot", "FAQ Deflection + Guided Triage"],
               "The Digital Self Service Agent answers a typed question from the knowledge base and resolves it, or "
               "hands over to an agent with the question, the articles shown and the captured intent. Containment is "
               "sized on the Executive View. It is one turn, not a conversation, and is not embedded in a web widget.",
               star=True, increment="F"),
        ],
    },
    {
        "id": "edge", "type": "connector",
        "title": "Omnichannel Event Streams → Web SDK / Mobile SDK → Acme AXP Edge Network",
    },
    {
        "id": "orchestration", "type": "band", "tone": "vendor", "highlight": True,
        "title": "AI & AGENT ORCHESTRATION — Acme Experience Platform Agent Orchestrator",
        "badge": "KEY NEW LAYER",
        "components": [
            _c("orchestrator", "AXP Agent Orchestrator", "vendor", "planned",
               ["Reasoning Engine + Dynamic Planning", "Multi-Agent Coordination (A2A/MCP)", "Human-in-the-Loop Governance"],
               "Increment D: a live reasoning trace — goal, plan, agent selection, A2A/MCP calls — with an approval gate before any commercial action executes.",
               increment="D"),
            _c("prebuilt", "Pre-Built AXP Agents", "vendor", "planned",
               ["Journey • Audience • Data Insights", "Experimentation • Content Production", "Optimisation • Product Support"],
               "Increment D: Product Support, Offer, Knowledge and Journey agents coordinated by the Orchestrator. Experimentation and Optimisation stay as reference.",
               increment="D"),
            _c("knowledge", "Knowledge Fabric & Content", "vendor", "partial",
               ["Acme GenForge • Glowfly (Gen AI)", "Brand Intelligence + CX Models", "Content Supply Chain"],
               "Every copilot recommendation cites the knowledge articles it rests on, retrieved by BM25 ranking. The "
               "articles are illustrative and stand in for Acme's approved content. Generated offer creative "
               "(GenForge, Glowfly) is not built.",
               increment="E"),
            _c("platform-intel", "AI Platform Intelligence", "ai", "partial",
               ["CX Engagement Intelligence", "Intent Classification + Sentiment", "3rd-Party LLM Integration"],
               "Intent, sentiment and signal detection run on a rules engine that needs no network, with Claude layered "
               "on top when a key is present. Voice of Customer themes are rolled up across all treated contacts. "
               "CX Engagement Intelligence as a product is not modelled.",
               star=True),
        ],
    },
    {
        "id": "actions", "type": "connector",
        "title": "Agent Actions → Context Handoff → Live Agent Escalation → Case Creation → Journey Triggers",
    },
    {
        "id": "core", "type": "band", "tone": "aws",
        "title": "CONTACT CENTRE CORE — AWS CONNECT",
        "badge": "Existing + AI Augmentation",
        "components": [
            _c("connect", "AWS Connect Platform", "existing", "partial",
               ["Contact Flows • Queues", "Routing Profiles • Skills Routing", "Real-Time & Historical Metrics"],
               "Queues, routing profile, contact attributes, real-time metrics and ACW are all modelled. Contact flows themselves are not authored."),
            _c("console", "Omnichannel Agent Console", "existing", "built",
               ["Agent Desktop", "Screen Pop + Customer Context", "Monitor / Alert"],
               "Fully built: CCP softphone, agent states, screen pop, contact attributes, wrap-up and disposition."),
            _c("assist", "AI Agent Assist", "ai", "built",
               ["Real-Time Transcription + Copilot", "Next-Best-Action Suggestions", "Auto-Summarisation"],
               "This is the Growth Engine — the core of the POC. Triage, signal detection, lead scoring, next-best-action and auto-summary all working.",
               star=True),
            _c("routing", "AI-Predictive Routing", "ai", "built",
               ["Intent-Based + Value Scoring", "Acme Segment-Aware Routing", "Skill + Context Matching"],
               "The Intelligent Customer Frontier computes every treatment from the customer profile: seventeen "
               "features, a propensity, a segment, four guardrails, then queue and skill. A champion and challenger "
               "model are compared on unseen traffic and promoted by a person. The decision is written to the contact "
               "as attributes; invoking it from a live Connect contact flow is the Amazon Connect increment.",
               star=True),
        ],
    },
    {
        "id": "sync", "type": "connector",
        "title": "Bi-Directional Sync → ServiceNow API → AXP Destinations → Kinesis / S3 Event Streams → MCP Connectors",
    },
    {
        "id": "data", "type": "band", "tone": "vendor", "width": 0.5,
        "title": "CUSTOMER DATA & JOURNEY — Acme",
        "components": [
            _c("cdp", "Acme Real-Time CDP", "vendor", "partial",
               ["Unified Profile + Identity Graph", "Real-Time / Edge Segmentation", "Data Governance + Consent"],
               "Profiles and events are held in Acme's Open Data Model on a swappable customer platform — a "
               "built-in store, or Apache Unomi, the open-source CDP. Audiences are defined once and rendered as Unomi "
               "conditions and as AXP AQL. Outcomes are written back and change the next decision. The AXP adapter is "
               "written but not exercised — there is no sandbox. No identity graph, no governance labels.",
               star=True, increment="B"),
            _c("journeys", "Acme Journey Composer", "vendor", "partial",
               ["Omnichannel Journey Canvas", "Real-Time Decisioning + Offers", "Experiment Optimisation"],
               "At wrap-up the outcome triggers a journey — steps, channels and timing chosen by the kind of offer. "
               "The journey is composed and shown, not sent: Journey Composer is a stand-in here.",
               increment="E"),
        ],
    },
    {
        "id": "foundation", "type": "band", "tone": "foundation", "width": 0.5,
        "title": "CASE MGMT • IDENTITY • AWS FOUNDATION",
        "components": [
            _c("cases", "ServiceNow + Cases", "foundation", "partial",
               ["Incident / Problem Mgmt", "Amazon Connect Cases", "SLA + Escalation"],
               "A case is raised at wrap-up where follow-up is owed — a service-recovery case with its commitment, or a "
               "specialist referral for a cross-cloud opportunity. ServiceNow is a stand-in: the case is composed and "
               "shown, not created in a real instance.",
               increment="E"),
            _c("identity", "Identity & HCM", "foundation", "reference",
               ["Okta / SSO / IAM", "Workday Integration", "Agent Skills + Scheduling"],
               "Deliberately not demoed. Real in the target architecture, but building screens for SSO and scheduling is effort without demo value."),
            _c("aws", "AWS Infrastructure", "foundation", "reference",
               ["Lambda • DynamoDB • S3", "MPLS • CloudWatch", "Bedrock AgentCore"],
               "Deliberately not demoed. Infrastructure is shown as present and accounted for rather than simulated.",
               star=True),
        ],
    },
]

# The path a contact takes through the architecture. Drives the trace animation.
TRACE = [
    {"target": "voice",          "caption": "Intelligent Customer Frontier: IVR captures intent and resolves identity"},
    {"target": "edge",           "caption": "Behavioural and contact events stream to the AXP Edge Network"},
    {"target": "cdp",            "caption": "Customer profile read in ODM — entitlement, utilisation, tenure, open issues"},
    {"target": "routing",        "caption": "Propensity scored, segment assigned, guardrails checked — SOLVE or SELL"},
    {"target": "connect",        "caption": "Decision written to the contact as attributes; queue and skill selected"},
    {"target": "console",        "caption": "Screen pop — the agent opens with full customer context"},
    {"target": "assist",         "caption": "Growth Engine: signal detection → offer match → next-best-action"},
    {"target": "knowledge",      "caption": "Recommendation grounded in knowledge, with the articles cited"},
    {"target": "actions",        "caption": "Agent action taken — offer presented and accepted"},
    {"target": "platform-intel", "caption": "Contact scored for quality; themes rolled up across every contact"},
    {"target": "cdp",            "caption": "Outcome written back to the profile — it changes the next decision"},
    {"target": "cases",          "caption": "Case raised where follow-up is owed"},
    {"target": "journeys",       "caption": "Post-contact journey triggered with the next best action"},
]




# ══════════════════════════════════════════════════════════════════════════════
#  THE "MAGNIFICENT 7" — GOAL-BASED AI AGENTS
#  These are agents, not architecture components. Each one is mapped onto the
#  component(s) it operates over, so the map can show where each agent lives.
# ══════════════════════════════════════════════════════════════════════════════

def _a(n, id, name, goal, operates, status, poc, increment=None):
    return {"n": n, "id": id, "name": name, "goal": goal, "operates": operates,
            "status": status, "poc": poc, "increment": increment}


AGENTS_M7 = [
    _a(1, "sales-sim", "ICX Sales Simulation Agent",
       "Detect and score revenue opportunity inside a live service conversation.",
       ["assist"], "built",
       "This is the Growth Engine and the core of the POC — triage, signal detection, "
       "lead scoring, offer matching and capture, all live in the contact. "
       "NOTE: implemented as opportunity simulation on a live contact. If the intent is "
       "agent training simulation (role-play for coaching), that is a different build — "
       "worth confirming."),

    _a(2, "quality", "Sales & Service Quality Agent",
       "Score every contact on both service quality and sales execution, automatically.",
       ["platform-intel", "console"], "built",
       "Scores every contact at wrap-up on service, sales execution and compliance. Each "
       "criterion carries its evidence — the turn and the words that satisfied it — and a "
       "compliance breach caps the score. Rules-based today; the same criteria can be "
       "judged by an LLM."),

    _a(3, "knowledge", "Knowledge Fabric Data Agent",
       "Retrieve and ground answers in approved product, policy and pricing knowledge.",
       ["knowledge"], "partial",
       "Every recommendation cites the articles it rests on, and the self-service agent "
       "answers from the same source. Retrieval is real; the articles are illustrative "
       "and stand in for Acme's approved content.",
       increment="E"),

    _a(4, "product-advisory", "Acme Product Advisory Agent",
       "Recommend the right Acme product and plan for this customer's actual usage.",
       ["concierge", "assist"], "built",
       "Matches one offer to each customer from a priced catalogue across Studio Cloud, "
       "Docs Cloud and Engage Cloud, and computes its value from the price list. Works "
       "on any profile, not only the demo contacts. Increment C extends it into "
       "Brand Assistant for pre-contact advisory.",
       increment="C"),

    _a(5, "voc", "Voice of Customer Agent",
       "Aggregate what customers are actually saying into themes leadership can act on.",
       ["platform-intel"], "built",
       "Rolls every treated contact into themes, measures each against the same day last "
       "week, and sorts them by what to do: fix, productise, deflect or watch. Runs on "
       "simulated traffic; the verbatims are illustrative."),

    _a(6, "self-service", "Digital Self Service Agent",
       "Resolve what does not need an agent, and hand over cleanly what does.",
       ["selfservice"], "partial",
       "Answers a typed question from knowledge when the match is confident and the task "
       "is one a customer can finish alone; otherwise hands over with context. One turn, "
       "not a conversation.",
       increment="F"),

    _a(7, "translation", "Real Time Voice Translation Agent",
       "Remove language as a routing constraint — any agent, any customer.",
       ["assist", "voice"], "partial",
       "A Spanish-speaking customer is scored, routed and handled by an English-speaking "
       "agent, with both languages in the transcript and in audio. The routing and the "
       "workspace are real; the translations on the demo contact are prepared in "
       "advance, not machine-translated live.",
       increment="G"),
]

# Which agents operate over each architecture component.
AGENTS_BY_COMPONENT = {}
for _ag in AGENTS_M7:
    for _cid in _ag["operates"]:
        AGENTS_BY_COMPONENT.setdefault(_cid, []).append(
            {"id": _ag["id"], "n": _ag["n"], "name": _ag["name"], "status": _ag["status"]})


def layers_with_agents():
    """LAYERS with each component annotated by the M7 agents that operate on it."""
    out = []
    for layer in LAYERS:
        if layer["type"] == "connector":
            out.append(layer)
            continue
        comps = [{**c, "agents": AGENTS_BY_COMPONENT.get(c["id"], [])} for c in layer["components"]]
        out.append({**layer, "components": comps})
    return out


def agent_summary():
    counts = {}
    for a in AGENTS_M7:
        counts[a["status"]] = counts.get(a["status"], 0) + 1
    return {"total": len(AGENTS_M7), "by_status": counts}


def trace_with_labels():
    """TRACE annotated with the human name of each target, so the trace controller can
    state exactly which component is lit."""
    names = {}
    for layer in LAYERS:
        if layer["type"] == "connector":
            names[layer["id"]] = layer["title"]
        else:
            for c in layer["components"]:
                names[c["id"]] = c["name"]
    return [{**t, "label": names.get(t["target"], t["target"])} for t in TRACE]


def summary():
    """POC coverage against the target architecture — the honest scorecard."""
    comps = [c for l in LAYERS if l["type"] != "connector" for c in l["components"]]
    counts = {}
    for c in comps:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    return {
        "total": len(comps),
        "by_status": counts,
        "agents": agent_summary(),
    }
