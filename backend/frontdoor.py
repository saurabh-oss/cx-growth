"""
INTELLIGENT CUSTOMER FRONTIER — IVR transformation layer.

The IVR stops being a menu and becomes a treatment decision. Every contact is scored on
what we already know — before a word is spoken to an agent:

    CONTACT ─▶ IVR TREATMENT ─▶ BACKGROUND MODEL ─▶ SEGMENT ─▶ SOLVE or SELL ─▶ ROUTE
                                        ▲                                          │
                                        └────────── FEEDBACK LOOP ◀────────────────┘

Two ideas make this different from ordinary propensity scoring:

1. The model runs on BACKGROUND data — entitlement, utilisation, tenure, open issues —
   not on conversation. The decision exists before the agent says hello.

2. SEGMENT CAN OVERRIDE PROPENSITY. A Service Recovery contact routes to SOLVE even when
   its propensity clears the threshold. That is the guardrail, expressed in the model
   rather than bolted on afterwards.

This module holds what is WRITTEN about the Frontier: the segment definitions and the
per-contact narrative. What is COMPUTED — features, propensity, segment, decision,
guardrails, routing and offer — comes from frontier_engine.decide(), run on the
customer's profile. treatment_for() joins the two.
"""
import frontier_engine as fe
import demo_profiles as dp

FRONT_DOOR_NAME = "Intelligent Customer Frontier"
FRONT_DOOR_TAGLINE = "Every contact treated before it reaches an agent"
PROPENSITY_THRESHOLD = fe.THRESHOLD

# ══════════════════════════════════════════════════════════════════════════════
#  COMMON SEGMENTS — every contact lands in exactly one
#  `share` is the design assumption. The share counted from simulated traffic is
#  attached at request time and is what the screen shows.
# ══════════════════════════════════════════════════════════════════════════════
SEGMENTS = [
    {"id": "capacity", "name": "Capacity Constrained", "tone": "blue", "share": 0.11,
     "definition": "Has run out, or nearly — storage, credits, licences or devices.",
     "default": "sell",
     "playbook": "Fix what is stuck first. Then offer the plan that stops it happening again."},

    {"id": "value", "name": "Value Seeker", "tone": "amber", "share": 0.08,
     "definition": "Thinking about the price — comparing plans, or calling to cancel.",
     "default": "sell",
     "playbook": "Find the plan that fits what they use. A smaller plan that keeps them beats a discount."},

    {"id": "growth", "name": "Growth Ready", "tone": "green", "share": 0.06,
     "definition": "Happy and growing. Nothing is broken — there is simply more they could do.",
     "default": "sell",
     "playbook": "Suggest what would help them next. Never invent a reason to hurry."},

    {"id": "recovery", "name": "Service Recovery", "tone": "red", "share": 0.09,
     "definition": "Something went wrong, or a promise was broken. Trust is damaged.",
     "default": "solve", "overrides": True,
     "playbook": "Put it right on this call. No offers until it is fixed."},

    {"id": "access", "name": "Access & Admin", "tone": "neutral", "share": 0.52,
     "definition": "A routine request — signing in, a billing detail, an account change.",
     "default": "solve",
     "playbook": "Fix it quickly and finish. A short, clean call is the right result."},

    {"id": "explorer", "name": "Explorer", "tone": "purple", "share": 0.14,
     "definition": "On a free or starter plan, and running into features that need a paid one.",
     "default": "sell",
     "playbook": "Talk only about the features they actually needed. Offer a free trial first."},
]

SEG = {s["id"]: s for s in SEGMENTS}


# ══════════════════════════════════════════════════════════════════════════════
#  PER-CONTACT NARRATIVE — the part a model cannot write
#  `expect` is the decision the demo script depends on. tests/test_engine.py fails if
#  the engine stops producing it.
# ══════════════════════════════════════════════════════════════════════════════
NOTES = {
    "aisha-storage-full": {
        "expect": "sell",
        "rationale": "Her storage is completely full, she is taking more photos every year, and there are two bigger plans she could move to.",
        "feedback": {"actual": "Upgrade accepted · $120", "match": True,
                     "note": "The engine read her correctly. A full plan on a growing account is a reliable sign."},
    },
    "tom-cancel-save": {
        "expect": "sell",
        "rationale": "He wants to cancel, but he uses two of the apps every week. The problem is the price of what he does not use — so a smaller plan has a real chance of keeping him.",
        "feedback": {"actual": "Plan switched · $240 retained", "match": True,
                     "note": "A customer calling to cancel is often a customer on the wrong plan."},
    },
    "nina-express-premium": {
        "expect": "sell",
        "rationale": "She keeps running into paid features, she is making designs for a shop, and she has never tried the paid version.",
        "feedback": {"actual": "Trial started · pending", "match": None,
                     "note": "Too early to say. The result is recorded when her free trial ends."},
    },
    "marcus-generative-credits": {
        "expect": "sell",
        "rationale": "He runs out of credits every month, his work earns him money, and he is paying someone else for video editing that Acme also sells.",
        "feedback": {"actual": "Upgrade accepted · $480", "match": True,
                     "note": "Paying a competitor turned out to matter more than the engine assumed. It has been taught to weigh it more."},
    },
    "priya-individual-to-teams": {
        "expect": "sell",
        "rationale": "Three people are working from a licence meant for one. The product is fine — they have simply outgrown the plan.",
        "feedback": {"actual": "3 Teams licences provisioned · $2,520", "match": True,
                     "note": "More people than licences is the single clearest sign a business has outgrown its plan."},
    },
    "ravi-creative-to-experience": {
        "expect": "sell",
        "rationale": "Nothing is broken and he is not complaining. His next problem is one that nothing he owns can solve — the answer sits in a different part of Acme.",
        "feedback": {"actual": "Specialist handoff accepted · pending", "match": None,
                     "note": "Passed to the specialist team. The result is recorded when they report back."},
    },
    "lucia-sign-contracts": {
        "expect": "sell",
        "rationale": "Her freelance work is growing and she needs contracts signed — something her plan cannot do. The language she speaks made no difference to the decision.",
        "feedback": {"actual": "DocuForge Pro added · $240", "match": True,
                     "note": "The decision is made on what we know about the customer, in any language."},
    },
    "robert-signin": {
        "expect": "solve",
        "rationale": "He cannot sign in. He is settled on his plan and has turned down two offers this year. There is nothing to sell — fix it and let him go.",
        "feedback": {"actual": "Resolved — no opportunity", "match": True,
                     "note": "Correctly left alone. Most calls are like this one."},
    },
    "elena-double-charge": {
        "expect": "solve",
        "rationale": "On paper she is likely to buy: her plan is full, she has been a customer for six years and she spends well. None of that matters while a billing mistake is unresolved and she is calling about it for the second time.",
        "feedback": {"actual": "Refund processed · no offer made", "match": True,
                     "note": "Held back, as it should be. She can be offered something once the problem is fixed and two weeks have passed."},
    },
}

# Kept for callers that iterate the demo contacts.
TREATMENTS = NOTES


def _predicted(d):
    if d["override"]:
        return "Held back — %s" % ("unresolved problem" if d["segment"] == "recovery" else "safety check")
    if d["decision"] == "solve":
        return "No opportunity"
    if d["offer"]:
        return "%s · %s" % (d["offer"]["type"], d["offer"]["estimated_value"])
    return "Opportunity — offer to be matched in conversation"


def treatment_for(scenario_id, model=None, threshold=None, profile=None):
    """The computed treatment for a demo contact, with its narrative attached."""
    if scenario_id not in dp.PROFILES:
        return None
    ctx = dp.CONTEXTS[scenario_id]
    d = fe.decide(profile or dp.PROFILES[scenario_id], ctx, model,
                  threshold if threshold is not None else PROPENSITY_THRESHOLD)
    note = NOTES.get(scenario_id, {})
    i = fe.intent(ctx["intent"])
    # The curated rationale describes the scripted decision. If the model in production
    # decides otherwise, say what it actually did.
    on_script = d["decision"] == note.get("expect", d["decision"])
    fb = dict(note.get("feedback", {})) if on_script else {
        "actual": "Not yet handled", "match": None,
        "note": "The engine has been retrained and now treats this contact differently. Reset it on the Technology screen to restore the rehearsed outcome."}
    fb["predicted"] = _predicted(d)
    return {
        **d,
        "ivr": {"path": i["path"], "intent": ctx["intent"], "identity": ctx["identity"],
                "duration": ctx["duration"], "language": ctx["language"]},
        "rationale": note["rationale"] if (on_script and note.get("rationale")) else d["rationale"],
        "computed_rationale": d["rationale"],
        "on_script": on_script,
        "feedback": fb,
        "segment_detail": SEG.get(d["segment"], {}),
    }


def segments_with(simulated):
    """Segment definitions with the share counted from simulated traffic."""
    out = []
    for s in SEGMENTS:
        got = (simulated or {}).get(s["id"])
        out.append({**s, "assumed_share": s["share"],
                    "share": got["share"] if got else s["share"],
                    "count": got["count"] if got else None})
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  FEEDBACK LOOP — the steps. The metrics are computed in main.py from the simulation.
# ══════════════════════════════════════════════════════════════════════════════
FEEDBACK_LOOP = [
    {"step": "What happened", "detail": "Offer accepted, declined, or nothing to offer"},
    {"step": "The agent records it", "detail": "One click at the end of the call"},
    {"step": "Matched to the sale", "detail": "A later purchase is traced back to this call"},
    {"step": "A new version is trained", "detail": "And tested on calls it has never seen"},
    {"step": "A person approves it", "detail": "The engine never changes itself"},
]


def feedback_metrics(summary):
    q, g = summary["quality"], summary["guardrails"]
    made = g["recovery_offers_made"]
    tone = lambda ok, warn=False: "green" if ok else ("amber" if warn else "red")
    return [
        {"name": "Tells real opportunities apart", "value": "%.2f" % q["auc"], "tone": tone(q["auc"] >= 0.7, q["auc"] >= 0.6),
         "note": "1.00 is perfect, 0.50 is a coin toss. Technical name: AUC"},
        {"name": "Its confidence can be trusted", "value": "±%.2f" % (q["calibration_error"] or 0),
         "tone": tone((q["calibration_error"] or 0) <= 0.05, (q["calibration_error"] or 0) <= 0.1),
         "note": "When it says 80% likely, about 80% turn out to be. Technical name: calibration"},
        {"name": "Never sold to an upset customer", "value": "100%" if made == 0 else "%d breaches" % made,
         "tone": tone(made == 0),
         "note": "%s customers with an unresolved problem · %d offers made" % ("{:,}".format(g["recovery_contacts"]), made)},
        {"name": "Sent to sell, nothing there", "value": "%.0f%%" % (100 * q["no_opportunity_rate"]), "tone": "amber",
         "note": "The number that learning from outcomes brings down"},
    ]
