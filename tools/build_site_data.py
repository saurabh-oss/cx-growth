"""
Build the data behind the project website (docs/).

    python tools/build_site_data.py

The website's interactive parts do not re-implement the engine in JavaScript. Every
number, decision and sentence they show is computed here, by the engine itself, and
written to docs/assets/data.js. Run this again after changing the model, the profiles
or the scenarios, and commit the result.

It always uses the shipped brand pack, never a local one, and it needs no server,
no network and no API key.
"""
import asyncio, itertools, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["BRAND_PACK"] = "default"
os.environ["CUSTOMER_PLATFORM"] = "local"
os.environ.pop("ANTHROPIC_API_KEY", None)
sys.path.insert(0, str(ROOT / "backend"))

import main            # noqa: E402,F401  (loads the brand pack first)
import app as api      # noqa: E402

OUT = ROOT / "docs" / "assets" / "data.js"
CALLS = ["priya-individual-to-teams", "ravi-creative-to-experience", "elena-double-charge"]


class Body:
    """Stands in for a request: the endpoints only ever read its JSON."""
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


def run(coro):
    return asyncio.run(coro)


def pick(d, *keys):
    return {k: d.get(k) for k in keys}


def treatment(t):
    offer = t.get("offer")
    return {
        "propensity": t["propensity"], "threshold": t["threshold"], "decision": t["decision"],
        "segment": t["segment"], "segment_name": t["segment_detail"]["name"], "segment_tone": t["segment_detail"]["tone"],
        "segment_reason": t["segment_reason"], "intent": t["intent_label"],
        "held_by": t.get("held_by"), "override": t.get("override"),
        "rationale": t.get("rationale"),
        "guardrails": [pick(g, "id", "name", "block", "pass", "detail") for g in t["guardrails"]],
        "features": [pick(f, "name", "value", "contribution", "direction") for f in t["features"]],
        "routing": pick(t["routing"], "queue", "skill", "why"),
        "offer": None if not offer else {
            "type": offer["type"], "value": offer["estimated_value"], "action": offer["recommended_action"],
            "why": offer["why"], "crosses": bool((offer.get("offer") or {}).get("crosses_cloud"))},
    }


def outcome(t):
    """A what-if result: the same decision, without the prose that does not change."""
    full = treatment(t)
    return {
        "propensity": full["propensity"], "decision": full["decision"], "segment_name": full["segment_name"],
        "segment_tone": full["segment_tone"], "intent": full["intent"], "held_by": full["held_by"],
        "override": full["override"],
        "guardrails": [pick(g, "id", "pass", "detail") for g in full["guardrails"]],
        "features": full["features"][:5],
        "routing": pick(full["routing"], "queue", "skill"),
        "offer": None if not full["offer"] else pick(full["offer"], "type", "value", "action", "crosses"),
    }


class Strings:
    """The what-if results repeat the same few hundred sentences thousands of times.
    Each is stored once, and referred to as "~12"."""
    def __init__(self):
        self.table, self.index = [], {}

    def pack(self, o):
        if isinstance(o, dict):
            return {k: self.pack(v) for k, v in o.items()}
        if isinstance(o, list):
            return [self.pack(v) for v in o]
        if isinstance(o, str):
            if o not in self.index:
                self.index[o] = len(self.table)
                self.table.append(o)
            return "~%d" % self.index[o]
        return o


def build():
    strings = Strings()
    run(api.frontier_reset())
    fd = run(api.frontdoor())
    scenarios = {s["id"]: s for s in run(api.list_scenarios())}
    switches = [w["id"] for w in fd["whatifs"]]

    customers = []
    for sid, t in fd["treatments"].items():
        s = run(api.get_scenario(sid))
        c = s["customer"]
        what = {}
        for n in range(1, len(switches) + 1):
            for combo in itertools.combinations(switches, n):
                r = run(api.frontier_whatif(Body({"scenario_id": sid, "switches": list(combo)})))
                what["+".join(combo)] = strings.pack(outcome(r))
        customers.append({
            "id": sid, "name": c["name"], "role": c["role"], "plan": c["tier"], "value": c["account_value"],
            "tenure": c["tenure"], "story": s["description"], "channel": s["contact"]["channel"],
            "base": treatment(t), "whatif": what,
            "outcome": t["feedback"]["actual"],
        })

    calls = []
    for sid in CALLS:
        s = run(api.get_scenario(sid))
        turns = []
        for i, u in enumerate(s["conversation"]):
            a = run(api.analyze_conversation(Body({"scenario_id": sid, "turn_index": i})))
            co = a.get("coaching")
            turns.append({
                "role": u["role"], "text": u["text"],
                "score": a["lead_score"], "sentiment": a["sentiment"],
                "signals": [pick(x, "turn", "category", "signal", "confidence") for x in a["signals"]],
                "coaching": None if not co else {
                    "turn": co["turn"], "text": co["suggestion"],
                    "sources": [pick(k, "id", "title") for k in (co.get("sources") or [])]},
                "qualified": a["lead_qualified"], "routed": a["routed_to_engine"],
            })
        last = run(api.analyze_conversation(Body({"scenario_id": sid, "turn_index": len(turns) - 1})))
        summary = last.get("lead_summary")
        calls.append({
            "id": sid, "title": s["title"], "customer": s["customer"]["name"], "role": s["customer"]["role"],
            "about": s["description"], "decision": s["treatment"]["decision"],
            "segment": s["treatment"]["segment_detail"]["name"],
            "propensity": s["treatment"]["propensity"], "override": s["treatment"].get("override"),
            "turns": turns,
            "result": None if not summary else pick(summary, "type", "estimated_value", "recommended_action", "urgency"),
            "resolution": last.get("resolution_summary"),
        })

    trained = run(api.frontier_train())
    trained.pop("created", None)             # a timestamp and a stopwatch: the only things
    trained["evaluation"].pop("seconds", None)   # here that change from one run to the next
    model = run(api.frontier_model())
    run(api.frontier_reset())
    ex = run(api.executive())
    pf = run(api.platform_info())
    arch = run(api.architecture())

    return {
        "model_version": fd["treatments"][CALLS[0]]["model_version"],
        "threshold": fd["threshold"],
        "source": fd["funnel"]["source"],
        "funnel": [pick(s, "stage", "value", "note") for s in fd["funnel"]["stages"]],
        "sweep": fd["sweep"],
        "rates": fd["rates"],
        "reconcile": fd["reconcile"],
        "segments": [pick(s, "id", "name", "tone", "share", "count", "definition", "default", "playbook") for s in fd["segments"]],
        "guardrail_evidence": fd["guardrails"],
        "quality": pick(fd["quality"], "auc", "precision", "missed_opportunities", "exploration_contacts"),
        "revenue_year": fd["revenue_year"],
        "whatifs": [pick(w, "id", "label") for w in fd["whatifs"]],
        "customers": customers,
        "strings": strings.table,
        "calls": calls,
        "model": {
            "kind": model["kind"], "bias": model["champion"]["bias"], "exploration_rate": model["exploration_rate"],
            "weights": [pick(w, "name", "weight") for w in model["champion"]["weights"]],
            "challenger": trained,
        },
        "economics": pick(ex, "cost_per_contact", "revenue_per_contact_today", "revenue_per_contact_target",
                          "net_cost_target", "cost_offset_pct", "annual_arr", "annual_calls", "payback_months",
                          "roi_year1", "deflection"),
        "platform": {
            "contract": pf["contract"], "tenant": pf["tenant"], "vendor_label": pf["portability"]["vendor_label"],
            "operations": pf["portability"]["operations"], "gaps": pf["portability"]["gaps"],
            "audiences": [pick(a, "id", "name", "description", "neutral", "query", "unomi") for a in pf["audiences"]],
        },
        "architecture": arch,
    }


def main_():
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    OUT.write_text("/* Generated by tools/build_site_data.py from the engine. Do not edit by hand. */\n"
                   "window.ENGINE_DATA=" + body + ";\n", encoding="utf-8", newline="\n")
    print("wrote %s  (%d KB, %d customers, %d what-if results, %d calls)" % (
        OUT.relative_to(ROOT), len(body) // 1024, len(data["customers"]),
        sum(len(c["whatif"]) for c in data["customers"]), len(data["calls"])))


if __name__ == "__main__":
    main_()
