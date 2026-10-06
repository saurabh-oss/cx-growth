"""
Growth Engine POC — the API.

Start the application with main.py, not this file: main.py loads the brand pack first,
so that every module — this one included — is read with the right names in it.
"""
import os, json, time, copy, uuid, hashlib, sqlite3, asyncio, random
from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path


def utcnow() -> str:
    """Timezone-aware UTC timestamp (datetime.utcnow() is deprecated on 3.12+)."""
    return datetime.now(timezone.utc).isoformat()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

# ── Try to import Anthropic ──
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

app = FastAPI(title="Growth Engine POC", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_PATH = Path(__file__).parent / "leads.db"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# ══════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            scenario_id TEXT,
            customer_name TEXT,
            company TEXT,
            lead_type TEXT,
            lead_score REAL,
            confidence REAL,
            summary TEXT,
            signals TEXT,
            coaching TEXT,
            status TEXT DEFAULT 'new',
            estimated_value TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            data TEXT,
            created_at TEXT
        );
    """)
    conn.close()

init_db()

# ══════════════════════════════════════
#  DEMO SCENARIOS
# ══════════════════════════════════════
# Scenario content lives in scenarios.py so the demo narrative can be edited
# without touching the server logic.
from scenarios import (SCENARIOS, SCALE_MODEL, TRIAGE_THRESHOLD,
                       AGENT, CONTACTS, QUEUE_METRICS, DISPOSITIONS, DISPOSITION_LABEL,
                       EXEC_MODEL, PRODUCT_CATALOGUE)
import architecture as arch
import frontdoor as fd
import story as story_mod

# The engine: what is computed rather than written.
import brand
import cdp
import trainer
import catalogue as cat
import demo_profiles as dp
import frontier_engine as fe
import simulation as sim
import learning
import nlu
import knowledge as kb
import quality as qa
import voc as voc_mod
import journey as jn

SCENARIO = {s["id"]: s for s in SCENARIOS}

# ══════════════════════════════════════
#  CUSTOMER PLATFORM
# ══════════════════════════════════════
PLATFORM = cdp.get_platform()


def seed_platform():
    """Demo customers and their history, written through whichever adapter is active."""
    if isinstance(PLATFORM, cdp.LocalPlatform):
        PLATFORM.wipe()
    dp.seed(PLATFORM)

try:
    seed_platform()
except Exception as ex:                       # a remote platform failing must not stop the demo
    print("  [cdp] seeding failed on %s (%s) — falling back to the built-in store" % (PLATFORM.key, ex))
    cdp._platform = PLATFORM = cdp.LocalPlatform()
    seed_platform()


# ══════════════════════════════════════
#  COMPUTED VIEWS
# ══════════════════════════════════════
_cache = {}


def _key():
    m = learning.champion()
    return (m["version"], m["bias"], learning.threshold())


def cached(name, build):
    """Simulation summaries are deterministic for a given model and threshold."""
    k = (name,) + _key()
    if k not in _cache:
        if len(_cache) > 60:
            _cache.clear()
        _cache[k] = build()
    return _cache[k]


def treatment(scenario_id):
    return cached("t:" + scenario_id,
                  lambda: fd.treatment_for(scenario_id, learning.champion(), learning.threshold()))


def summary():
    def build():
        s = sim.summarise(learning.day(0), learning.champion(), learning.threshold(), SCALE_MODEL)
        # Ranking quality is judged the same way the model card judges it — against ground
        # truth for every eligible contact — so the two screens cannot disagree.
        s["quality"]["auc"] = learning.evaluate(learning.champion(), learning.day(0), learning.threshold())["auc"]
        return s
    return cached("summary", build)


def sim_clock():
    """The simulated day replays against the wall clock. Outside working hours the clock
    is folded back into them, so a late rehearsal still sees a live contact centre."""
    now = datetime.now()
    if 8 <= now.hour <= 19:
        return now
    return now.replace(hour=9 + now.hour % 9)


def _fill(obj, values):
    """Substitute {tokens} in every string of a nested structure."""
    if isinstance(obj, str):
        for k, v in values.items():
            obj = obj.replace("{" + k + "}", str(v))
        return obj
    if isinstance(obj, list):
        return [_fill(x, values) for x in obj]
    if isinstance(obj, dict):
        return {k: _fill(v, values) for k, v in obj.items()}
    return obj


def scenario_view(s, full=True):
    """A scripted scenario with everything computable replaced by what the engine computed."""
    t = treatment(s["id"])
    sell = t["decision"] == "sell"
    scripted = s["triage"]
    on_script = t["on_script"]
    suppression = None
    if t["override"]:
        suppression = "service_recovery" if t["segment"] == "recovery" else \
            next((g["id"] for g in t["guardrails"] if not g["pass"]), "guardrail")
    triage = {
        "decision": "growth_engine" if sell else "standard",
        "propensity": t["propensity"],
        "reason": scripted["reason"] if on_script else t["rationale"],
        "suppression": suppression,
        "turn": scripted["turn"],
        "segment": t["segment"],
        "model_version": t["model_version"],
    }
    contact = copy.deepcopy(CONTACTS.get(s["id"], {}))
    if contact:
        contact["queue"] = t["routing"]["queue"]
        # What the contact flow writes onto the contact before it reaches an agent.
        contact["attributes"] = {**contact.get("attributes", {}),
                                 "frontierSegment": t["segment"].upper(),
                                 "frontierTreatment": t["decision"].upper(),
                                 "frontierPropensity": "%.2f" % t["propensity"],
                                 "frontierModel": t["model_version"]}
    out = {"id": s["id"], "title": s["title"], "description": s["description"], "type": s["type"],
           "icon": s["icon"], "customer": s["customer"], "contact": contact, "treatment": t,
           "triage": triage, "translation": s.get("translation"), "profile_id": dp.PROFILE_ID[s["id"]]}
    if not full:
        return out

    analysis = copy.deepcopy(s["ai_analysis"])
    offer = t.get("offer")
    sources = kb.grounding(dp.CONTEXTS[s["id"]]["intent"], offer,
                           retention=bool(offer and offer["type"] == "Retention"))
    service_sources = kb.grounding(dp.CONTEXTS[s["id"]]["intent"])
    for c in analysis["coaching_suggestions"]:
        c["sources"] = sources if c["type"] in ("product", "closing") else service_sources[:2]
    if not sell and not analysis.get("resolution_summary"):
        # A scripted sale that the model in production no longer routes.
        analysis["resolution_summary"] = {
            "outcome": "Resolved — nothing to sell",
            "detail": "The engine (version %s) judged this customer {pct}%% likely to buy and treated the "
                      "call as service only. %s" % (t["model_version"], t["rationale"]),
            "why_no_lead": ["The engine has been retrained and no longer sees a sale here",
                            "Reset it on the Technology screen to restore the rehearsed outcome"]}
    out.update({"conversation": s["conversation"], "ai_analysis": analysis})
    return _fill(out, {"propensity": "%.2f" % t["propensity"], "pct": "%d" % round(t["propensity"] * 100)})


# ══════════════════════════════════════
#  AI ENGINE (Claude Integration)
# ══════════════════════════════════════
MODEL = "claude-opus-5"
AI_TIMEOUT_SECONDS = 6.0      # never let a slow API call stall the demo playback
AI_MAX_FAILURES = 3           # after repeated failures, stop trying for this process

_ai_state = {"failures": 0, "last_error": None}
_client_cache = {}

# Structured output schema — guarantees parseable JSON, no markdown-fence stripping.
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "signals_detected": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["upsell", "cross_sell", "new_product"]},
                    "category": {"type": "string", "enum": ["Upsell", "Cross-Sell", "New Sale"]},
                    "signal": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                },
                "required": ["type", "category", "signal", "keywords", "confidence"],
                "additionalProperties": False,
            },
        },
        "lead_score": {"type": "integer"},
        "sentiment": {"type": "number"},
        "coaching_suggestion": {"type": "string"},
        "coaching_priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "lead_qualified": {"type": "boolean"},
        "summary": {"type": "string"},
    },
    "required": ["signals_detected", "lead_score", "sentiment", "coaching_suggestion",
                 "coaching_priority", "lead_qualified", "summary"],
    "additionalProperties": False,
}


def get_claude_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not (api_key and ANTHROPIC_AVAILABLE):
        return None
    if "c" not in _client_cache:
        _client_cache["c"] = anthropic.Anthropic(api_key=api_key, max_retries=1)
    return _client_cache["c"]


def ai_available() -> bool:
    return get_claude_client() is not None and _ai_state["failures"] < AI_MAX_FAILURES


def _call_claude_sync(conversation_text: str, customer_context: str) -> dict:
    """Blocking Claude call — always invoked off the event loop via asyncio.to_thread."""
    client = get_claude_client()
    prompt = f"""You are a real-time sales signal detection system listening to a live
contact centre conversation. Identify genuine revenue opportunities — upsell (expand an
existing product), cross-sell (add an adjacent product), or new product sale.

CUSTOMER CONTEXT:
{customer_context}

CONVERSATION SO FAR:
{conversation_text}

Score the lead 0-100 on buying propensity. Weight heavily: explicit need, budget
availability, executive sponsorship, urgency, and competitive evaluation. Give the agent
one concrete next-best-action they could say or do right now."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "effort": "low",  # latency matters — playback advances every ~3.5s
            "format": {"type": "json_schema", "schema": ANALYSIS_SCHEMA},
        },
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


async def analyze_with_claude(conversation_text: str, customer_context: str) -> Optional[dict]:
    """Best-effort live analysis. Returns None on any failure — never raises,
    never blocks the event loop, never exceeds AI_TIMEOUT_SECONDS."""
    if not ai_available():
        return None
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_call_claude_sync, conversation_text, customer_context),
            timeout=AI_TIMEOUT_SECONDS,
        )
        _ai_state["failures"] = 0
        return result
    except asyncio.TimeoutError:
        _ai_state["failures"] += 1
        _ai_state["last_error"] = f"timeout after {AI_TIMEOUT_SECONDS}s"
        print(f"  [ai] timeout ({_ai_state['failures']}/{AI_MAX_FAILURES}) — using scripted analysis")
        return None
    except Exception as e:
        _ai_state["failures"] += 1
        _ai_state["last_error"] = str(e)
        print(f"  [ai] error ({_ai_state['failures']}/{AI_MAX_FAILURES}): {e}")
        return None


def _transcript(conversation):
    """English text of a conversation, whatever language it was held in."""
    return "\n".join(
        f"{'Customer' if m['role'] == 'customer' else 'Agent'}: {m.get('text_en') or m['text']}"
        for m in conversation)


# ══════════════════════════════════════
#  API ENDPOINTS
# ══════════════════════════════════════
@app.get("/api/health")
async def health():
    m = learning.champion()
    return {
        "status": "ok",
        "ai_enabled": ai_available(),
        "model": MODEL if ai_available() else None,
        "sdk_installed": ANTHROPIC_AVAILABLE,
        "key_present": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "ai_last_error": _ai_state["last_error"],
        "platform": PLATFORM.key,
        "platform_label": PLATFORM.label,
        "frontier_model": m["version"],
        "threshold": learning.threshold(),
        "timestamp": utcnow(),
    }

@app.get("/api/scenarios")
async def list_scenarios():
    return [scenario_view(s, full=False) for s in SCENARIOS]

@app.get("/api/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    s = SCENARIO.get(scenario_id)
    if not s:
        raise HTTPException(404, "Scenario not found")
    return scenario_view(s)

@app.get("/api/story")
async def story():
    """The guided demo flow — what to show, what to say, what to point at. Figures in the
    script are filled from what the engine computed, so the words match the screen."""
    s = summary()
    a = arch.summary()
    values = {"p." + sid.split("-")[0]: "%.2f" % treatment(sid)["propensity"] for sid in dp.PROFILES}
    values.update({"pct." + sid.split("-")[0]: "%d" % round(treatment(sid)["propensity"] * 100) for sid in dp.PROFILES})
    values.update({
        "threshold": "%.2f" % learning.threshold(),
        "contacts": "{:,}".format(s["contacts"]),
        "converted": "{:,}".format(s["funnel"][-1]["value"]),
        "built": a["by_status"].get("built", 0), "partial": a["by_status"].get("partial", 0),
        "planned": a["by_status"].get("planned", 0),
        "agents_built": a["agents"]["by_status"].get("built", 0),
        "agents_partial": a["agents"]["by_status"].get("partial", 0),
        "platform": PLATFORM.label,
    })
    return {"steps": _fill(story_mod.STORY, values), "acts": story_mod.ACTS,
            "total_minutes": story_mod.TOTAL_MINUTES}


@app.get("/api/frontdoor")
async def frontdoor():
    """Intelligent Customer Frontier — the IVR transformation layer."""
    s = summary()
    curve = cached("sweep", lambda: sim.sweep(learning.day(0), learning.champion(), EXEC_MODEL["cost_per_contact"]))
    return {
        "name": fd.FRONT_DOOR_NAME,
        "tagline": fd.FRONT_DOOR_TAGLINE,
        "threshold": learning.threshold(),
        "segments": fd.segments_with(s["segments"]),
        "funnel": {"threshold": s["threshold"], "sell_leaning_share": s["rates"]["sell_leaning"],
                   "triage_rate": s["rates"]["triage"], "stages": s["funnel"],
                   "source": "One simulated day · %s synthetic contacts · model %s" % (
                       "{:,}".format(s["contacts"]), s["model_version"])},
        "rates": s["rates"],
        "reconcile": s["reconcile"],
        "guardrails": s["guardrails"],
        "quality": s["quality"],
        "offer_mix": s["offer_mix"],
        "revenue_day": s["revenue_day"],
        "revenue_year": s["revenue_year"],
        "sweep": curve,
        "feedback": {"window": "One simulated day", "metrics": fd.feedback_metrics(s), "loop": fd.FEEDBACK_LOOP},
        "catalogue": PRODUCT_CATALOGUE,
        "price_list": cat.catalogue_view(),
        "treatments": {k: treatment(k) for k in dp.PROFILES},
        "intents": [{"id": k, "label": v["label"], "family": v["family"], "path": v["path"]}
                    for k, v in fe.INTENTS.items()],
        "whatifs": WHATIFS,
        "is_simulated": True,
    }


@app.get("/api/frontier/feed")
async def frontier_feed(limit: int = 14):
    """Contacts arriving now, each already treated."""
    return sim.feed(learning.day(0), learning.champion(), learning.threshold(), sim_clock(), min(limit, 40))


# What-if switches: one change to the profile or the contact, and the decision re-computed.
T = cdp.TENANT
WHATIFS = [
    {"id": "consent", "label": "Marketing consent withdrawn",
     "changes": {"consents.marketing.any.val": "n"}},
    {"id": "cooldown", "label": "Offer made 10 days ago",
     "changes": {T + ".commercial.lastOfferDate": "@days_ago:10"}},
    {"id": "case", "label": "Unresolved case, second call this week",
     "changes": {T + ".service.openCases": ["CASE-51102"], T + ".service.openCaseCount": 1,
                 T + ".service.repeatContact7d": True}},
    {"id": "declined", "label": "Declined three offers this year",
     "changes": {T + ".commercial.offersDeclined12m": 3}},
    {"id": "password", "label": "Calling about a password instead", "intent": "account.access"},
    {"id": "clean", "label": "Failure resolved, no open case",
     "changes": {T + ".service.openCases": [], T + ".service.openCaseCount": 0,
                 T + ".service.repeatContact7d": False, T + ".service.duplicateChargeFlag": False},
     "intent": "plan.compare"},
]


@app.post("/api/frontier/whatif")
async def frontier_whatif(request: Request):
    """Re-score a demo contact with switches applied. Nothing is written — the customer's
    profile on the platform is untouched."""
    body = await request.json()
    sid = body.get("scenario_id")
    if sid not in dp.PROFILES:
        raise HTTPException(404, "Scenario not found")
    profile = copy.deepcopy(dp.PROFILES[sid])
    ctx = dict(dp.CONTEXTS[sid])
    applied = []
    for w in WHATIFS:
        if w["id"] in (body.get("switches") or []):
            applied.append(w["label"])
            for path, value in (w.get("changes") or {}).items():
                if isinstance(value, str) and value.startswith("@days_ago:"):
                    value = cdp.ago(days=int(value.split(":")[1]))
                cdp.set_path(profile, path, value)
            if w.get("intent"):
                ctx["intent"] = w["intent"]
    thr = float(body.get("threshold") or learning.threshold())
    d = fe.decide(profile, ctx, learning.champion(), thr)
    base = treatment(sid)
    i = fe.intent(ctx["intent"])
    return {**d, "applied": applied, "segment_detail": fd.SEG.get(d["segment"], {}),
            "ivr": {"path": i["path"], "intent": ctx["intent"], "identity": ctx["identity"],
                    "duration": ctx["duration"], "language": ctx["language"]},
            "baseline": {"decision": base["decision"], "propensity": base["propensity"], "segment": base["segment"]},
            "changed": d["decision"] != base["decision"]}


@app.get("/api/frontier/model")
async def frontier_model():
    return learning.model_card()


@app.post("/api/frontier/model/train")
async def frontier_train():
    """Train a challenger on simulated outcomes. Runs off the event loop — it takes a second or two."""
    return await asyncio.to_thread(learning.train)


@app.post("/api/frontier/model/promote")
async def frontier_promote():
    m = learning.promote()
    if not m:
        raise HTTPException(409, "No challenger to promote — train one first")
    return learning.model_card()


@app.post("/api/frontier/model/reset")
async def frontier_reset():
    learning.reset()
    return learning.model_card()


@app.get("/api/architecture")
async def architecture():
    """The TO-BE architecture, with an honest build status on every component."""
    return {
        "legend": arch.LEGEND,
        "status_label": arch.STATUS_LABEL,
        "layers": arch.layers_with_agents(),
        "trace": arch.trace_with_labels(),
        "summary": arch.summary(),
        "m7": arch.AGENTS_M7,
    }


@app.get("/api/executive")
async def executive():
    """The commercial case, derived from the same SCALE_MODEL the demo runs on so the
    per-contact figures and the headline ARR can never drift apart."""
    m, e = SCALE_MODEL, EXEC_MODEL
    annual_calls = m["daily_calls"] * 365
    annual_arr = (annual_calls * m["triage_rate"] * m["capture_rate"]
                  * m["conversion_rate"] * m["avg_value"])

    rev_per_contact = annual_arr / annual_calls
    cost = e["cost_per_contact"]

    # Run-rate ARR at each coverage step, so the curve reconciles to the headline.
    curve = [{**q, "run_rate": int(annual_arr * q["coverage"])} for q in e["value_curve"]]
    # Year-one realised revenue: each quarter contributes a quarter of its run rate.
    realised_y1 = sum(q["run_rate"] for q in curve) / 4.0
    payback_months = (e["programme_cost_year1"] / realised_y1 * 12.0) if realised_y1 else None

    s = summary()
    themes = await voc_view()
    return {
        "cost_per_contact": cost,
        "revenue_per_contact_today": e["revenue_per_contact_today"],
        "revenue_per_contact_target": round(rev_per_contact, 2),
        "net_cost_today": round(cost - e["revenue_per_contact_today"], 2),
        "net_cost_target": round(cost - rev_per_contact, 2),
        "cost_offset_pct": round(rev_per_contact / cost * 100),
        "annual_arr": int(annual_arr),
        "annual_calls": int(annual_calls),
        "programme_cost_year1": e["programme_cost_year1"],
        "realised_year1": int(realised_y1),
        "payback_months": round(payback_months, 1) if payback_months else None,
        "roi_year1": round(realised_y1 / e["programme_cost_year1"], 1) if realised_y1 else None,
        "value_curve": curve,
        "maturity": e["maturity"],
        "maturity_today": e["maturity_today"],
        "maturity_after_pilot": e["maturity_after_pilot"],
        "guardrails": e["guardrails"],
        "guardrail_evidence": s["guardrails"],
        "benchmark": e["benchmark"],
        "agent_variance": e["agent_variance"],
        "roadmap": e["roadmap"],
        # The assumptions, checked against a scored run of synthetic traffic.
        "evidence": {"reconcile": s["reconcile"], "simulated_arr": s["revenue_year"],
                     "contacts": s["contacts"], "model_version": s["model_version"]},
        "deflection": themes["deflection"],
        "is_model": True,
    }


@app.get("/api/workspace")
async def workspace():
    """Agent identity, real-time queue metrics and wrap-up dispositions —
    the Amazon Connect agent workspace context."""
    queues = sim.queue_metrics(learning.day(0), learning.champion(), learning.threshold(),
                               QUEUE_METRICS, sim_clock())
    return {
        "agent": AGENT,
        "queues": queues,
        "dispositions": DISPOSITIONS,
        "contacts_in_queue": sum(q["in_queue"] for q in queues),
        "agents_online": sum(q["agents"] for q in queues),
        "service_level": round(sum(q["sla"] for q in queues) / len(queues)),
        "platform": {"key": PLATFORM.key, "label": PLATFORM.label},
    }


@app.post("/api/analyze")
async def analyze_conversation(request: Request):
    body = await request.json()
    scenario_id = body.get("scenario_id")
    turn_index = body.get("turn_index", 0)

    raw = SCENARIO.get(scenario_id)
    if not raw:
        raise HTTPException(404, "Scenario not found")
    scenario = scenario_view(raw)

    analysis = scenario["ai_analysis"]
    triage = scenario["triage"]
    routed = triage["decision"] == "growth_engine"

    # The scripted analysis is ALWAYS the backbone of the response. This guarantees the
    # demo tells a complete story — signals, score, coaching, and the lead capture at the
    # end — whether or not the API key is set and whether or not the network cooperates.
    signals_so_far = [s for s in analysis["signals"] if s["turn"] <= turn_index] if routed else []
    coaching = [c for c in analysis["coaching_suggestions"] if c["turn"] <= turn_index]
    score = analysis["lead_score_progression"][min(turn_index, len(analysis["lead_score_progression"])-1)]
    sentiment = analysis["sentiment_progression"][min(turn_index, len(analysis["sentiment_progression"])-1)]
    if not routed:
        score = min(score, 12)

    # Triage resolves one turn in, so the routing decision is visible early — the branch
    # is the point of the demo, not an afterthought at the end of the call.
    triage_done = turn_index >= triage["turn"]
    last_turn = turn_index >= len(scenario["conversation"]) - 1

    payload = {
        "source": "scripted",
        "turn_index": turn_index,
        "signals": signals_so_far,
        "coaching": coaching[-1] if coaching else None,
        "lead_score": score,
        "sentiment": sentiment,
        "triage": triage if triage_done else None,
        "triage_threshold": learning.threshold(),
        "routed_to_engine": routed,
        # A lead can only be captured on a call the engine actually routed to itself.
        "lead_qualified": routed and score >= 80,
        "lead_summary": analysis.get("lead_summary") if (routed and score >= 80) else None,
        # Calls routed to standard handling report their own outcome instead.
        "resolution_summary": analysis.get("resolution_summary") if (not routed and last_turn) else None,
        "ai": None,
    }

    # Live Claude analysis is layered ON TOP as an additive overlay — it enriches the
    # panel but can never remove the lead_summary that drives lead capture. It is skipped
    # entirely on calls triaged away from sales: a live model must not be able to talk the
    # engine into selling to a customer the triage rules deliberately protected.
    if turn_index > 0 and routed and ai_available():
        conv_text = _transcript(scenario["conversation"][:turn_index + 1])
        ctx = json.dumps(scenario["customer"], indent=2)
        claude_result = await analyze_with_claude(conv_text, ctx)
        if claude_result:
            payload["source"] = "scripted+claude"
            payload["ai"] = claude_result
            # Blend the live score in, but never let it drop below the scripted
            # progression — the demo's narrative arc must always move forward.
            payload["lead_score"] = max(score, int(claude_result.get("lead_score", score)))
            payload["sentiment"] = claude_result.get("sentiment", sentiment)
            if payload["lead_score"] >= 80:
                payload["lead_qualified"] = True
                payload["lead_summary"] = analysis.get("lead_summary")

    return payload


# ══════════════════════════════════════
#  CUSTOMER PLATFORM — profile, history, portability
# ══════════════════════════════════════
EVENT_LABEL = {
    "productUsage.syncFailed": "Sync failed", "productUsage.storageThreshold": "Storage threshold crossed",
    "productUsage.monthlySummary": "Monthly usage summary", "productUsage.featureGateHit": "Premium feature gate",
    "productUsage.creditsExhausted": "Generative credits exhausted", "productUsage.exportTarget": "Export to third-party tool",
    "productUsage.concurrentSignInBlocked": "Concurrent sign-in blocked",
    "productUsage.libraryVersionConflict": "Library version conflict", "productUsage.exportPdf": "PDF exports",
    "web.webpagedetails.pageViews": "Page viewed", "web.webinteraction.linkClicks": "Link clicked",
    "billing.chargePosted": "Charge posted", "billing.invoiceRequested": "Invoice requested",
    "application.loginFailed": "Sign-in failed", "commerce.purchases": "Purchase",
    "commerce.offerDeclined": "Offer declined", "commerce.offerPresented": "Offer presented",
    "commerce.offerAccepted": "Offer accepted", "commerce.holdApplied": "Commercial hold applied",
    "leadOperation.newLead": "Lead created", "case.opened": "Case opened", "case.resolved": "Case resolved",
    "case.slaBreached": "Case commitment missed", "contactCentre.interaction": "Contact centre interaction",
    "contactCentre.treatmentDecided": "Frontier treatment decided",
}
EVENT_TONE = {"billing": "amber", "case": "red", "commerce": "green", "leadOperation": "green",
              "contactCentre": "accent", "productUsage": "blue", "web": "neutral", "application": "neutral"}


def _ago(ts):
    try:
        d = datetime.now(timezone.utc) - datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return ""
    s = int(d.total_seconds())
    if s < 90:
        return "just now"
    if s < 3600:
        return "%d min ago" % (s // 60)
    if s < 86400:
        return "%d h ago" % (s // 3600)
    return "%d days ago" % (s // 86400)


def _event_view(ev):
    payload = {k: v for k, v in (ev.get(cdp.TENANT) or {}).items() if k != "source"}
    bits = []
    for k, v in payload.items():
        if k in ("contactId", "modelVersion"):
            continue
        if isinstance(v, bool):
            if v:
                bits.append(k)
        elif isinstance(v, list):
            bits.append("%s: %s" % (k, ", ".join(str(x) for x in v)))
        elif v not in (None, ""):
            bits.append("%s: %s" % (k, v))
    return {"id": ev["_id"], "type": ev["eventType"], "label": EVENT_LABEL.get(ev["eventType"], ev["eventType"]),
            "tone": EVENT_TONE.get(ev["eventType"].split(".")[0], "neutral"),
            "timestamp": ev["timestamp"], "ago": _ago(ev["timestamp"]), "detail": " · ".join(bits[:4]),
            "source": (ev.get(cdp.TENANT) or {}).get("source", "runtime"),
            "channel": (ev.get("channel") or {}).get("mediaType"), "record": ev}


def profile_view(profile_id):
    p = PLATFORM.get_profile(profile_id)
    if not p:
        return None
    t = p[cdp.TENANT]
    names = {a["id"]: a for a in cdp.AUDIENCES}
    auds = PLATFORM.audiences_for(profile_id)
    consent = p.get("consents", {}).get("marketing", {})
    return {
        "id": profile_id, "name": cdp.full_name(p),
        "language": p.get("preferredLanguage"), "country": p.get("homeAddress", {}).get("countryCode"),
        "customer_type": t.get("customerType"),
        "identities": [{"namespace": ns, "id": i["id"], "primary": i.get("primary", False)}
                       for ns, ids in p.get("identityMap", {}).items() for i in ids],
        "consent": {"marketing": consent.get("any", {}).get("val", "y"), "email": consent.get("email", {}).get("val", "y"),
                    "call": consent.get("call", {}).get("val", "y"),
                    "personalize": p.get("consents", {}).get("personalize", {}).get("content", {}).get("val", "y")},
        "entitlement": t["entitlement"], "usage": t["usage"], "service": t["service"],
        "health": t["health"], "commercial": t["commercial"],
        "audiences": [{"id": a, "name": names[a]["name"], "description": names[a]["description"]}
                      for a in auds if a in names],
        "events": [_event_view(e) for e in PLATFORM.events_for(profile_id, 30)],
        "record": p,
        "platform": {"key": PLATFORM.key, "label": PLATFORM.label},
    }


@app.get("/api/platform")
async def platform_info():
    """Which customer platform is answering, and how each operation maps onto AXP."""
    return {
        "active": await asyncio.to_thread(PLATFORM.info),
        "adapters": [
            {"key": "local", "label": "Built-in profile store", "status": "available",
             "note": "SQLite, in-process. Always on, so the demo always has a platform."},
            {"key": "unomi", "label": "Apache Unomi 3", "status": "available",
             "note": "Open-source CDP, Apache 2.0. Start it from platform/docker-compose.yml and set CUSTOMER_PLATFORM=unomi."},
            {"key": "vendor", "label": cdp.VendorPlatform(env={}).label, "status": "needs a sandbox",
             "note": "Adapter written against Acme's published API reference. Not exercised — no sandbox."},
        ],
        "portability": cdp.portability(),
        "audiences": cdp.audience_renderings(),
        "tenant": cdp.TENANT,
        "contract": brand.pack().get("schema_name", "Open data model"),
        "sample_event": cdp.event_doc("contactCentre.treatmentDecided", "priya-raman", {
            "intent": "account.concurrent", "segment": "capacity", "propensity": treatment("priya-individual-to-teams")["propensity"],
            "decision": "SELL"}, channel="voice", eid="sample"),
    }


@app.get("/api/profiles/{key}")
async def get_profile(key: str):
    """key is a scenario id or a profile id."""
    pid = dp.PROFILE_ID.get(key, key)
    v = await asyncio.to_thread(profile_view, pid)
    if not v:
        raise HTTPException(404, "Profile not found")
    return v


# ══════════════════════════════════════
#  CONTACT LIFECYCLE — start and wrap-up
# ══════════════════════════════════════
def _write_back(profile_id, plan):
    for ev in plan["events"]:
        PLATFORM.record_event(profile_id, ev)
    if plan["changes"]:
        PLATFORM.patch_profile(profile_id, plan["changes"])


@app.post("/api/contacts/{scenario_id}/start")
async def contact_start(scenario_id: str):
    """A demo contact is routed. The customer is restored to the state they were in
    before the call, so a replay always starts from the same place."""
    if scenario_id not in dp.PROFILES:
        raise HTTPException(404, "Scenario not found")
    await asyncio.to_thread(dp.seed, PLATFORM, scenario_id)
    return {"status": "routed", "profile_id": dp.PROFILE_ID[scenario_id]}


@app.post("/api/contacts/{scenario_id}/wrapup")
async def contact_wrapup(scenario_id: str, request: Request):
    """After Contact Work: score the contact, write the outcome to the customer platform,
    trigger what follows, and hand the disposition to the feedback loop."""
    body = await request.json()
    live = LIVE.get(scenario_id)
    if live:
        profile, ctx, t = live["profile"], live["ctx"], live["treatment"]
        conversation = live["conversation"]
        a = nlu.analyse(conversation, t, profile, ctx["intent"])
        sentiments, lead = a["sentiments"], (live.get("lead") if body.get("lead_captured") else None)
        contact_id = live["contact"]["contact_id"]
    else:
        raw = SCENARIO.get(scenario_id)
        if not raw:
            raise HTTPException(404, "Scenario not found")
        sc = scenario_view(raw)
        profile, ctx, t = copy.deepcopy(dp.PROFILES[scenario_id]), dp.CONTEXTS[scenario_id], sc["treatment"]
        turns = int(body.get("turns") or len(sc["conversation"]))
        conversation = [{"role": m["role"], "text": m.get("text_en") or m["text"]} for m in sc["conversation"][:turns]]
        sentiments = sc["ai_analysis"]["sentiment_progression"][:turns]
        lead = sc["ai_analysis"].get("lead_summary") if body.get("lead_captured") else None
        contact_id = sc["contact"].get("contact_id")
        await asyncio.to_thread(dp.seed, PLATFORM, scenario_id)       # idempotent: wrap-up can be re-submitted

    quality = qa.score(conversation, t, sentiments, lead_captured=bool(lead), auth=ctx.get("auth", "VERIFIED"))
    disposition = body.get("disposition")
    plan = jn.plan(scenario_id, profile, ctx, t, {
        "disposition": disposition, "lead": lead, "talk_seconds": int(body.get("talk_seconds") or 0),
        "signals": int(body.get("signals") or 0), "quality": quality, "contact_id": contact_id})
    try:
        await asyncio.to_thread(_write_back, profile["_id"], plan)
        written = True
    except Exception as ex:
        print("  [cdp] write-back failed: %s" % ex)
        written = False

    labelled = None
    if disposition and t["decision"] == "sell" and disposition in DISPOSITION_LABEL:
        labelled = learning.record_disposition(t["vector"], DISPOSITION_LABEL[disposition]["opportunity"],
                                               contact_id, disposition)
    nxt = jn.next_contact(profile, plan["changes"], ctx, learning.champion(), learning.threshold())
    return {
        "quality": quality,
        "events": [_event_view(e) for e in plan["events"]],
        "profile_changes": plan["profile_changes"],
        "journey": plan["journey"],
        "case": plan["case"],
        "next_contact": nxt,
        "written": written,
        "platform": {"key": PLATFORM.key, "label": PLATFORM.label},
        "feedback": {"labelled": labelled is not None, "examples_waiting": learning.model_card()["labelled"],
                     "label": (DISPOSITION_LABEL.get(disposition) or {}).get("opportunity") if labelled is not None else None},
    }


# ══════════════════════════════════════
#  LIVE CONTACT — unscripted; someone in the room plays the customer
# ══════════════════════════════════════
LIVE = {}


def _customer_card(profile):
    t = profile[cdp.TENANT]
    e, u, h = t["entitlement"], t["usage"], t["health"]
    smb = t["customerType"] == "Small Business"
    months = e.get("tenureMonths", 0)
    trend = u.get("usageTrendPct", 0)
    return {
        "name": cdp.full_name(profile),
        "role": "%s · %s" % ("Small business" if smb else "Individual", e.get("planName")),
        "company": t["customerType"], "tier": e.get("planName"),
        "account_value": "${:,.2f}/yr".format(e.get("annualValue", 0)),
        "products": e.get("products") or cat.plan(e.get("planCode"))["apps"],
        "tenure": ("%d months" % months) if months < 24 else ("%d years" % round(months / 12.0)),
        "health_score": h.get("score"), "nps": h.get("nps"),
        "usage_trend": ("↑ %d%% usage" % trend) if trend > 0 else ("↓ %d%% usage" % -trend if trend < 0 else "→ stable"),
        "contract_renewal": "%s%s" % (e.get("billingCycle", "—"), (" · renews " + e["renewalDate"]) if e.get("renewalDate") else ""),
        "team_size": e.get("seats", 1),
    }


def _lead_from(offer, a):
    conf = round(min(0.97, 0.55 + a["lead_score"] / 250.0), 2)
    steps = ["Apply the change in-call and confirm it has taken effect",
             "Send written confirmation of what changed and what it costs",
             "Set a 30-day check-in on fit"]
    if offer["offer"]["crosses_cloud"] and offer["value"] >= 1000:
        steps = ["Warm handoff to the %s specialist team within 48h" % offer["offer"]["to"][0]["cloud"],
                 "Pass on the volume and structure captured in this contact",
                 "Do not quote — the specialist scopes and prices"]
    elif offer.get("trial"):
        steps = ["Start the trial in-call and unblock what they were doing",
                 "Send the walkthrough for the feature that brought them in",
                 "Follow up at day 12 of the trial"]
    return {"type": offer["type"], "estimated_value": offer["estimated_value"], "value_note": offer["value_note"],
            "confidence": conf, "recommended_action": offer["recommended_action"],
            "urgency": "Established in conversation — %d signals detected" % len(a["signals"]),
            "offer": offer["offer"], "next_steps": steps}


@app.get("/api/live/options")
async def live_options():
    """Who can call, and about what."""
    people = [{"id": sid, "name": cdp.full_name(p), "plan": p[cdp.TENANT]["entitlement"]["planName"],
               "intent": dp.CONTEXTS[sid]["intent"], "kind": "demo"} for sid, p in dp.PROFILES.items()]
    people.append({"id": "random", "name": "A customer at random", "plan": "From the synthetic population of %s" %
                   "{:,}".format(sim.POPULATION), "intent": None, "kind": "population"})
    return {"customers": people,
            "intents": [{"id": k, "label": v["label"], "family": v["family"]} for k, v in fe.INTENTS.items()],
            "speech": "Browser speech recognition is used for the microphone where the browser provides it"}


@app.post("/api/live/start")
async def live_start(request: Request):
    body = await request.json()
    who = body.get("customer") or "random"
    if who in dp.PROFILES:
        profile = copy.deepcopy(dp.PROFILES[who])
        ctx = dict(dp.CONTEXTS[who])
        await asyncio.to_thread(dp.seed, PLATFORM, who)
    else:
        customers, _, intents = sim.population()
        rng = random.Random()
        idx = rng.randrange(len(customers))
        profile = copy.deepcopy(customers[idx])
        ctx = {"intent": sim._pick(rng, intents[idx]), "auth": "VERIFIED", "channel": "voice",
               "language": "en-GB", "identity": "Authenticated — registered number", "duration": "0:%02d" % rng.randint(12, 44)}
        await asyncio.to_thread(PLATFORM.upsert_profile, profile)
    if body.get("intent") in fe.INTENTS:
        ctx["intent"] = body["intent"]
    if body.get("channel") in ("voice", "chat"):
        ctx["channel"] = body["channel"]

    d = fe.decide(profile, ctx, learning.champion(), learning.threshold())
    i = fe.intent(ctx["intent"])
    sid = "live-" + uuid.uuid4().hex[:10]
    t = {**d, "ivr": {"path": i["path"], "intent": ctx["intent"], "identity": ctx["identity"],
                      "duration": ctx["duration"], "language": ctx["language"]},
         "segment_detail": fd.SEG.get(d["segment"], {}), "on_script": True,
         "feedback": {"predicted": fd._predicted(d), "actual": "In progress", "match": None,
                      "note": "Outcome is whatever this conversation produces."}}
    sell = d["decision"] == "sell"
    e, u, s = profile[cdp.TENANT]["entitlement"], profile[cdp.TENANT]["usage"], profile[cdp.TENANT]["service"]
    contact = {
        "contact_id": str(uuid.uuid4()), "channel": ctx["channel"].upper(), "initiation": "INBOUND",
        "queue": d["routing"]["queue"], "queue_wait": "00:%02d" % random.randint(14, 58),
        "priority": 1 if d["segment"] in ("recovery", "value") else 3, "ivr_path": i["path"],
        "attributes": {"customerSegment": profile[cdp.TENANT]["customerType"], "planCode": e["planCode"],
                       "tenureMonths": str(e.get("tenureMonths", 0)), "authStatus": ctx["auth"],
                       "languageCode": ctx["language"], "capturedIntent": ctx["intent"],
                       "frontierSegment": d["segment"].upper(), "frontierTreatment": d["decision"].upper(),
                       "frontierPropensity": "%.2f" % d["propensity"], "frontierModel": d["model_version"]}}
    suppression = None
    if d["override"]:
        suppression = "service_recovery" if d["segment"] == "recovery" else \
            next((g["id"] for g in d["guardrails"] if not g["pass"]), "guardrail")
    a = nlu.analyse([], t, profile, ctx["intent"])
    scenario = {
        "id": sid, "live": True, "title": "Live contact — %s" % i["label"],
        "description": "%s. Unscripted — analysed as it is spoken." % i["label"],
        "type": (d["offer"]["type"] if d["offer"] else ("Suppressed" if d["override"] else ("Upsell" if sell else "No Action"))),
        "icon": "🎙️", "customer": _customer_card(profile), "contact": contact, "treatment": t,
        "triage": {"decision": "growth_engine" if sell else "standard", "propensity": d["propensity"],
                   "reason": d["rationale"], "suppression": suppression, "turn": 0, "segment": d["segment"],
                   "model_version": d["model_version"]},
        "conversation": [], "profile_id": profile["_id"],
        "ai_analysis": {"signals": [], "lead_score_progression": [a["lead_score"]], "sentiment_progression": [0.5],
                        "coaching_suggestions": [], "lead_summary": None},
        "opening": {"coaching": {**a["coaching"], "sources": a["grounding"]},
                    "suggested_replies": a["suggested_replies"], "lead_score": a["lead_score"]},
    }
    LIVE[sid] = {"profile": profile, "ctx": ctx, "treatment": t, "conversation": [], "contact": contact,
                 "lead": None, "started": time.time()}
    if len(LIVE) > 40:
        for k in sorted(LIVE, key=lambda k: LIVE[k]["started"])[:-40]:
            LIVE.pop(k, None)
    return scenario


@app.post("/api/live/turn")
async def live_turn(request: Request):
    body = await request.json()
    s = LIVE.get(body.get("session_id"))
    if not s:
        raise HTTPException(404, "Live contact not found — it may have ended")
    text = (body.get("text") or "").strip()
    role = "agent" if body.get("role") == "agent" else "customer"
    if not text:
        raise HTTPException(400, "Nothing was said")
    s["conversation"].append({"role": role, "text": text[:1200], "delay": int(time.time() - s["started"])})
    t, profile, ctx = s["treatment"], s["profile"], s["ctx"]
    a = nlu.analyse(s["conversation"], t, profile, ctx["intent"])
    routed = a["routed"]

    lead = None
    if a["qualified"] and t.get("offer"):
        lead = _lead_from(t["offer"], a)
        s["lead"] = lead
    resolution = None
    if not routed:
        resolution = {
            "outcome": "Resolved — no offer made" if a["stage"] == "suppressed" else "Resolved — nothing to sell",
            "detail": ("The customer said something had gone wrong. The engine stood down, whatever their record said."
                       if a["raised_failure"] else t["rationale"]),
            "why_no_lead": [t["segment_reason"]] + [g["detail"] for g in t["guardrails"] if not g["pass"]]
                           + (["Only %d%% likely to buy — the line is %d%%" % (
                               round(t["propensity"] * 100), round(t["threshold"] * 100))]
                              if t["propensity"] < t["threshold"] else [])}
    triage = {"decision": "growth_engine" if routed else "standard", "propensity": t["propensity"],
              "reason": ("The customer said something had gone wrong. No offer will be made."
                         if a["raised_failure"] else t["rationale"]),
              "suppression": ("service_recovery" if (a["raised_failure"] or t["segment"] == "recovery") and not routed
                              and (t["propensity"] >= t["threshold"] or a["raised_failure"]) else
                              (next((g["id"] for g in t["guardrails"] if not g["pass"]), None) if t["override"] else None)),
              "turn": 0, "segment": t["segment"], "model_version": t["model_version"]}
    payload = {
        "source": "rules", "turn_index": len(s["conversation"]) - 1,
        "signals": a["signals"], "coaching": {**a["coaching"], "sources": a["grounding"]},
        "lead_score": a["lead_score"], "sentiment": a["sentiment"], "sentiments": a["sentiments"],
        "triage": triage, "triage_threshold": learning.threshold(), "routed_to_engine": routed,
        "lead_qualified": bool(lead), "lead_summary": lead, "resolution_summary": resolution,
        "stage": a["stage"], "suggested_replies": a["suggested_replies"], "ai": None,
    }
    if role == "customer" and routed and ai_available():
        r = await analyze_with_claude(_transcript(s["conversation"]), json.dumps(_customer_card(profile), indent=2))
        if r:
            payload["source"] = "rules+claude"
            payload["ai"] = r
    return payload


# ══════════════════════════════════════
#  TRAINING — the agent practises; the engine plays the customer
# ══════════════════════════════════════
TRAIN = {}

VOICE_SCHEMA = {"type": "object", "properties": {"line": {"type": "string"}}, "required": ["line"], "additionalProperties": False}


def _voice_sync(brief, transcript, planned, why):
    """Claude voices the persona's next line so it answers the agent's exact words. The
    rules have already decided what the customer does; this only decides how it is said."""
    client = get_claude_client()
    prompt = f"""You are playing a customer on a phone call to a software company's support line,
so that a human agent can practise. Stay in character. Speak as the customer, in the first
person, in one or two natural spoken sentences. Never help the agent, never sell, never
break character, never mention that this is practice.

WHO YOU ARE:
{brief}

THE CALL SO FAR:
{transcript}

WHAT YOU DO NEXT (decided already — keep this meaning and these facts exactly):
{planned}
(The reason you say this: {why}.)

Rewrite that line so it answers what the agent just said, in your own words and mood."""
    response = client.messages.create(
        model=MODEL, max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": VOICE_SCHEMA}},
    )
    text = next(b.text for b in response.content if b.type == "text")
    line = (json.loads(text).get("line") or "").strip()
    return line if 8 <= len(line) <= 400 else None


async def voice_with_claude(brief, transcript, planned, why):
    if not ai_available():
        return None
    try:
        r = await asyncio.wait_for(asyncio.to_thread(_voice_sync, brief, transcript, planned, why), timeout=AI_TIMEOUT_SECONDS)
        _ai_state["failures"] = 0
        return r
    except Exception as e:                                   # noqa: BLE001 — best effort, never breaks the call
        _ai_state["failures"] += 1
        _ai_state["last_error"] = str(e)
        return None


def _training_analysis(s):
    """The same analysis the live workspace shows, over the training conversation."""
    p, t = s["persona"], s["treatment"]
    a = nlu.analyse(s["conversation"], t, p.profile, p.ctx["intent"])
    routed = a["routed"]
    lead = _lead_from(t["offer"], a) if a["qualified"] and t.get("offer") else None
    resolution = None
    if not routed and s["conversation"]:
        resolution = {"outcome": "Resolved — no offer made" if a["stage"] == "suppressed" else "Resolved — nothing to sell",
                      "detail": t["rationale"], "why_no_lead": [t["segment_reason"]] + [g["detail"] for g in t["guardrails"] if not g["pass"]]}
    return {"signals": a["signals"], "coaching": {**a["coaching"], "sources": a["grounding"]},
            "lead_score": a["lead_score"], "sentiment": a["sentiment"], "sentiments": a["sentiments"],
            "triage": {"decision": "growth_engine" if routed else "standard", "propensity": t["propensity"], "reason": t["rationale"],
                       "suppression": ("service_recovery" if t.get("segment") == "recovery" and t.get("override") else
                                       (next((g["id"] for g in t["guardrails"] if not g["pass"]), None) if t.get("override") else None)),
                       "turn": 0, "segment": t["segment"], "model_version": t["model_version"]},
            "routed_to_engine": routed, "lead_qualified": bool(lead), "lead_summary": lead,
            "resolution_summary": resolution, "stage": a["stage"], "suggested_replies": a["suggested_replies"]}


@app.get("/api/training/options")
async def training_options():
    o = trainer.options(learning.champion(), learning.threshold())
    o["speech"] = {"voice": "Synthesised in the browser from the persona's lines — no recording.",
                   "microphone": "Browser speech recognition where the browser provides it; typing always works.",
                   "claude_voices_persona": ai_available()}
    return o


@app.post("/api/training/start")
async def training_start(request: Request):
    body = await request.json()
    sid = body.get("persona")
    if sid not in trainer.SCENARIO_BY_ID:
        raise HTTPException(404, "No such customer")
    s = trainer.start(sid, body.get("difficulty") or "steady", learning.champion(), learning.threshold())
    p, t = s["persona"], s["treatment"]
    s["started"] = time.time()
    TRAIN[s["id"]] = s
    if len(TRAIN) > 40:
        for k in sorted(TRAIN, key=lambda k: TRAIN[k]["started"])[:-40]:
            TRAIN.pop(k, None)
    await asyncio.to_thread(dp.seed, PLATFORM, sid)
    sc = trainer.SCENARIO_BY_ID[sid]
    i = fe.intent(p.ctx["intent"])
    contact = {**copy.deepcopy(CONTACTS.get(sid, {})), "contact_id": str(uuid.uuid4()), "channel": "VOICE"}
    contact["queue"] = t["routing"]["queue"]
    contact["attributes"] = {**contact.get("attributes", {}), "frontierSegment": t["segment"].upper(),
                             "frontierTreatment": t["decision"].upper(), "frontierPropensity": "%.2f" % t["propensity"],
                             "frontierModel": t["model_version"], "trainingMode": "TRUE"}
    opening = p.opening()
    return {
        "id": s["id"], "training": True, "title": "Practice — %s" % i["label"],
        "difficulty": p.difficulty, "focus": trainer.focus_for(sc, t),
        "customer": _customer_card(p.profile), "contact": contact, "treatment": t,
        "profile_id": p.profile["_id"], "persona": p.state(),
        "opening": {"text": opening, "mood": p.state()["mood"], "mood_label": p.state()["mood_label"]},
        "objectives": p.objectives([]),
        "analysis": _training_analysis(s),
        "voice": {"lang": "en-GB", "role": "customer"},
    }


@app.post("/api/training/turn")
async def training_turn(request: Request):
    body = await request.json()
    s = TRAIN.get(body.get("session_id"))
    if not s:
        raise HTTPException(404, "Practice call not found — it may have ended")
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Nothing was said")
    p = s["persona"]
    if not s["conversation"]:
        s["conversation"].append({"role": "customer", "text": p.opening(), "delay": 0})
    now = int(time.time() - s["started"])
    s["conversation"].append({"role": "agent", "text": text[:1200], "delay": now})
    m = trainer.moves(text)
    reply = p.respond(text, m)
    if reply["why"] not in ("ended",) and ai_available():
        brief = "%s. %s. Plan: %s. Mood right now: %s. Reason for calling: %s." % (
            p.sc["customer"]["name"], p.sc["customer"]["role"], p.sc["customer"]["tier"], reply["mood_label"], p.sc["description"])
        voiced = await voice_with_claude(brief, _transcript(s["conversation"]), reply["text"], reply["why"])
        if voiced:
            reply = {**reply, "text": voiced, "voiced_by": "claude"}
    s["conversation"].append({"role": "customer", "text": reply["text"], "delay": now + 2})
    return {"agent_moves": sorted(m), "customer": reply, "persona": p.state(),
            "objectives": p.objectives(s["conversation"]), "analysis": _training_analysis(s), "ended": p.ended}


@app.post("/api/training/end")
async def training_end(request: Request):
    body = await request.json()
    s = TRAIN.get(body.get("session_id"))
    if not s:
        raise HTTPException(404, "Practice call not found — it may have ended")
    d = trainer.debrief(s, hints_used=int(body.get("hints_used") or 0), ended_by=body.get("ended_by") or "agent")
    d["transcript"] = s["conversation"]
    d["talk_seconds"] = int(time.time() - s["started"])
    return d


# ══════════════════════════════════════
#  AGENTS — knowledge, self-service, voice of customer, evaluation
# ══════════════════════════════════════
@app.get("/api/knowledge/search")
async def knowledge_search(q: str = "", k: int = 3):
    return {"query": q, "results": kb.search(q, min(k, 8)) if q.strip() else [],
            "articles": len(kb.ARTICLES), "illustrative": True}


@app.post("/api/selfservice/ask")
async def selfservice_ask(request: Request):
    """Digital Self Service Agent: answer from knowledge, or hand over with context."""
    body = await request.json()
    q = (body.get("question") or "").strip()
    if not q:
        raise HTTPException(400, "Ask a question")
    r = kb.self_service(q[:600])
    if r["suggested_intent"]:
        i = fe.intent(r["suggested_intent"])
        r["routing"] = {"intent": r["suggested_intent"], "label": i["label"], "queue": fe.QUEUES[i["queue"]]}
    return r


async def voc_view():
    return cached("voc", lambda: voc_mod.themes(learning.day(0), learning.day(-7), learning.champion(),
                                                learning.threshold(), EXEC_MODEL["cost_per_contact"]))


@app.get("/api/voc")
async def voc():
    """Voice of Customer Agent: themes, movement, and what to do about each."""
    return await voc_view()


@app.get("/api/evaluation")
async def evaluation():
    """The rules engine judged against the curated analysis of the scripted contacts."""
    ts = {sid: fd.treatment_for(sid, learning.champion(), learning.threshold()) for sid in dp.PROFILES}
    return nlu.evaluation(SCENARIOS, ts)


class LeadCreate(BaseModel):
    scenario_id: str
    customer_name: str
    company: str
    lead_type: str
    lead_score: float
    confidence: float
    summary: str
    signals: str
    coaching: str
    estimated_value: str

@app.post("/api/leads")
async def create_lead(lead: LeadCreate):
    conn = get_db()
    # Server-side idempotency guard: a single scenario run must capture exactly one lead,
    # even if the client fires the request more than once.
    existing = conn.execute(
        "SELECT id FROM leads WHERE scenario_id = ? AND created_at > ? LIMIT 1",
        (lead.scenario_id, (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()),
    ).fetchone()
    if existing:
        conn.close()
        return {"id": existing["id"], "status": "duplicate_ignored"}

    lead_id = hashlib.md5(f"{lead.scenario_id}{time.time()}".encode()).hexdigest()[:12]
    conn.execute(
        "INSERT INTO leads (id, scenario_id, customer_name, company, lead_type, lead_score, confidence, summary, signals, coaching, estimated_value, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (lead_id, lead.scenario_id, lead.customer_name, lead.company, lead.lead_type, lead.lead_score, lead.confidence, lead.summary, lead.signals, lead.coaching, lead.estimated_value, utcnow())
    )
    conn.commit()
    conn.close()
    return {"id": lead_id, "status": "captured"}

@app.get("/api/leads")
async def list_leads():
    conn = get_db()
    rows = conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.patch("/api/leads/{lead_id}")
async def update_lead(lead_id: str, request: Request):
    body = await request.json()
    conn = get_db()
    conn.execute("UPDATE leads SET status = ? WHERE id = ?", (body.get("status", "new"), lead_id))
    conn.commit()
    conn.close()
    return {"status": "updated"}

@app.delete("/api/leads")
async def clear_leads():
    """Clears the pipeline and restores the demo customers to their starting state."""
    conn = get_db()
    conn.execute("DELETE FROM leads")
    conn.commit()
    conn.close()
    try:
        await asyncio.to_thread(seed_platform)
    except Exception as ex:
        print("  [cdp] re-seed failed: %s" % ex)
    LIVE.clear()
    return {"status": "cleared"}

@app.get("/api/analytics")
async def get_analytics():
    conn = get_db()
    leads = conn.execute("SELECT * FROM leads").fetchall()
    conn.close()
    total = len(leads)

    def classify(lead_type: str) -> str:
        """Each lead counts once. 'Upsell + Cross-Sell' is primarily an upsell."""
        t = lead_type or ""
        if "Retention" in t:
            return "retention"
        if "New" in t:
            return "new_sale"
        if "Upsell" in t:
            return "upsell"
        if "Cross" in t:
            return "cross_sell"
        return "upsell"

    buckets = {"upsell": 0, "cross_sell": 0, "new_sale": 0, "retention": 0}
    for l in leads:
        buckets[classify(l["lead_type"])] += 1

    # Consumer deal sizes are small; the business case is volume. Project annual
    # incremental ARR from the modelled funnel so the per-call figure has context.
    m = SCALE_MODEL
    annual_calls = m["daily_calls"] * 365
    routed_calls = annual_calls * m["triage_rate"]
    captured = routed_calls * m["capture_rate"]
    converted = captured * m["conversion_rate"]
    scale = {
        **m,
        "annual_calls": int(annual_calls),
        "routed_calls": int(routed_calls),
        "captured": int(captured),
        "converted": int(converted),
        "annual_arr": int(converted * m["avg_value"]),
        "is_model": True,   # the UI must label this as an assumption, not a result
    }

    # Today by hour, from the simulated day — what the trend chart draws.
    day = learning.day(0)
    day.score(learning.champion())
    hours = [{"hour": h, "routed": 0, "qualified": 0, "converted": 0} for h in range(24)]
    for r in day.decide(learning.threshold()):
        if r["decision"] == "sell":
            h = hours[r["second"] // 3600]
            h["routed"] += 1
            h["qualified"] += 1 if r["qualified"] else 0
            h["converted"] += 1 if r["converted"] else 0
    s = summary()

    return {
        "total_leads": total,
        "by_type": buckets,
        "scale": scale,
        "triage_threshold": learning.threshold(),
        "calls_available": len(SCENARIOS),
        "calls_routed": sum(1 for s_ in SCENARIOS if treatment(s_["id"])["decision"] == "sell"),
        "avg_score": sum(l["lead_score"] for l in leads) / max(total, 1),
        "avg_confidence": sum(l["confidence"] for l in leads) / max(total, 1),
        "total_pipeline_value": sum(int("".join(c for c in (l["estimated_value"] or "0") if c.isdigit()) or 0) for l in leads),
        "conversion_rate": s["rates"]["conversion"],
        "by_hour": [h for h in hours if 7 <= h["hour"] <= 20],
        "now_hour": sim_clock().hour,
        "leads": [dict(l) for l in leads],
    }

# ── Serve frontend ──
_page = {"key": None, "html": ""}


def page():
    """The page, with the brand's names and marks in it. Re-read when the file changes."""
    src = FRONTEND_DIR / "index.html"
    key = (src.stat().st_mtime_ns, brand.pack().get("source"))
    if _page["key"] != key:
        html = brand.apply(src.read_text(encoding="utf-8"))
        marks = json.dumps(brand.public()).replace("</", "<\\/")
        _page.update(key=key, html=html.replace("/*BRAND_JSON*/null/*END*/", marks))
    return _page["html"]


@app.get("/")
async def serve_frontend():
    return HTMLResponse(page())

@app.get("/{path:path}")
async def serve_static(path: str):
    # Unknown API routes must 404, not silently return the SPA shell.
    if path.startswith("api/"):
        raise HTTPException(404, "Not found")
    candidate = (FRONTEND_DIR / path).resolve()
    if candidate.is_relative_to(FRONTEND_DIR.resolve()) and candidate.is_file() and candidate.name != "index.html":
        return FileResponse(str(candidate))
    return HTMLResponse(page())


def banner(port):
    print("\n" + "="*60)
    print("  GROWTH ENGINE POC - Contact Centre AI")
    print("  AI-Driven Sales Lead Identification")
    print("="*60)
    print(f"\n  ->  Open: http://localhost:{port}")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key and ANTHROPIC_AVAILABLE:
        print(f"  [OK]   Claude AI: ENABLED  (model: {MODEL})")
        print(f"         Live analysis layers on top of the scripted demo.")
    else:
        print(f"  [INFO] Claude AI: OFF  (running the scripted demo)")
        if not ANTHROPIC_AVAILABLE:
            print(f"         To enable: pip install anthropic")
        if not api_key:
            print(f"         To enable: set ANTHROPIC_API_KEY=sk-ant-...")
    print(f"  [OK]   Customer platform: {PLATFORM.label}  (CUSTOMER_PLATFORM={PLATFORM.key})")
    print(f"  [OK]   Frontier model {learning.champion()['version']}, threshold {learning.threshold():.2f}")
    print(f"  [OK]   Brand pack: {brand.pack().get('source')}")
    print(f"  [OK]   Demo is fully self-contained - no internet required.")
    print(f"\n{'='*60}\n")
