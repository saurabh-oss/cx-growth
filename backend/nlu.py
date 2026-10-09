"""
CONVERSATION ENGINE — signal detection on whatever the customer actually says.

The nine demo contacts play a written conversation with curated analysis, because a
guided demo needs to land the same way every time. This module is what runs when the
conversation is NOT written in advance: a live contact where someone in the room plays
the customer and types — or says — whatever they like.

    utterance ─▶ detectors ─▶ signals ─▶ lead score ─▶ next best action ─▶ grounded in knowledge

It is a rules engine: eighteen detectors, each a handful of patterns. That is a deliberate
floor, not a ceiling. It needs no API key and no network, so the live contact works in
any room; with ANTHROPIC_API_KEY set, Claude reads the same conversation and its
analysis is layered on top. evaluation() reports how far the rules agree with the
curated analysis on the scripted contacts, so nobody has to take their quality on trust.
"""
import math, re

import frontier_engine as fe
import knowledge as kb

# category: how the signal is labelled.  weight: how far it moves the lead score.
DETECTORS = [
    {"id": "capacity", "category": "Upsell", "type": "expansion", "weight": 0.80, "conf": 0.84,
     "label": "Capacity ceiling reached",
     "patterns": [r"storage (is |was )?(completely )?full", r"out of (space|storage|(generative )?credits)",
                  r"stopped syncing", r"(hit|reached|at) (the|my) limit", r"no (more )?(space|credits|room)",
                  r"run(ning)? out of", r"(credits|storage) (have|has) run out", r"keeps? (telling|saying) .{0,30}full"]},
    {"id": "recurring", "category": "Upsell", "type": "expansion", "weight": 0.45, "conf": 0.82,
     "label": "The limit is recurring, not a one-off",
     "patterns": [r"(second|third|fourth|\d+(st|nd|rd|th)) (month|time)", r"every (single )?month", r"keeps happening",
                  r"again and again", r"month(s)? running", r"out of .{0,25} again"]},
    {"id": "growth", "category": "Upsell", "type": "expansion", "weight": 0.60, "conf": 0.87,
     "label": "Usage is growing",
     "patterns": [r"(a lot|much|way|far) more", r"more and more", r"started (doing|shooting|making|selling|taking)",
                  r"(business|shop|channel|studio) (is|has) (growing|grown|taken off)", r"taken on", r"busier",
                  r"getting bigger", r"expanding"]},
    {"id": "team", "category": "Upsell", "type": "expansion", "weight": 0.90, "conf": 0.90,
     "label": "More than one person on the account",
     "patterns": [r"colleague", r"(two|three|four|five|six|\d+) of us", r"shar(e|ing) (my|the|one|a) (login|account|licen[cs]e)",
                  r"my (team|staff|designers|employees|assistant)", r"signed out", r"used (somewhere|on another)",
                  r"(hired|taken on) .{0,20}(designer|people|staff|someone)"]},
    {"id": "admin", "category": "Upsell", "type": "upsell", "weight": 0.55, "conf": 0.88,
     "label": "Needs business administration",
     "patterns": [r"(company|proper|vat|tax) invoice", r"accountant", r"purchase order", r"(manage|add|remove) (users|seats|people)",
                  r"set up (correctly|properly)", r"built for (small )?(studios|businesses|teams)"]},
    {"id": "commercial", "category": "Upsell", "type": "expansion", "weight": 0.50, "conf": 0.86,
     "label": "Commercial use — output earns money",
     "patterns": [r"(my|our) (clients?|customers)", r"(my|a|our) (small )?(shop|store|business|studio|channel|agency)",
                  r"\betsy\b", r"youtube", r"freelanc", r"how i earn", r"for (my )?work", r"sell(s|ing)? better", r"listings?",
                  r"campaign", r"wedding(s)?"]},
    {"id": "urgency", "category": "Upsell", "type": "upsell", "weight": 0.45, "conf": 0.88,
     "label": "Deadline pressure",
     "patterns": [r"deadline", r"(by|before|this|on) (monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|the weekend)",
                  r"urgent", r"asap", r"right away", r"can'?t afford (for )?(it|this)",
                  r"(need|want|sorted|fixed|working) .{0,24}today", r"lose a day"]},
    {"id": "willing", "category": "Upsell", "type": "upsell", "weight": 0.85, "conf": 0.93,
     "label": "Willing to pay for a fix",
     "patterns": [r"whatever (it takes|gets it working|works)", r"happy to pay", r"worth paying", r"how much (is|would|does)",
                  r"what (would|does) (it|that) cost", r"i'?d (rather|like to) (upgrade|be set up|pay)", r"just need it sorted",
                  r"(can|could) i upgrade", r"sign me up", r"let'?s do (it|that)", r"yes,? please"]},
    {"id": "cancel", "category": "Retention", "type": "cross_sell", "weight": 0.35, "conf": 0.81,
     "label": "Cancellation intent — a price objection",
     "patterns": [r"\bcancel", r"too (expensive|much)", r"can'?t justify", r"not worth", r"stop paying", r"cheaper"]},
    {"id": "mismatch", "category": "Retention", "type": "cross_sell", "weight": 0.80, "conf": 0.92,
     "label": "Paying for capability that is not used",
     "patterns": [r"(only|just) (use|using|need) ", r"just (photoforge|lightvault|vectorforge)", r"never (opened|used|touched)",
                  r"paying for .{0,40}(don'?t|never|not) (use|open)", r"apps i'?ve never", r"that'?s it"]},
    {"id": "save", "category": "Retention", "type": "cross_sell", "weight": 0.85, "conf": 0.95,
     "label": "Save condition stated",
     "patterns": [r"i'?d stay", r"if it (were|was) (cheaper|a sensible|less)", r"i do (like|use)", r"i still use",
                  r"use (it|them) most (weeks|days)", r"at the right price"]},
    {"id": "competitor", "category": "Upsell", "type": "upsell", "weight": 0.80, "conf": 0.93,
     "label": "Paying a third party for an adjacent capability",
     "patterns": [r"paying for .{0,45}separately", r"(another|a different|a separate) (\w+ )?(app|tool|subscription|service|program)",
                  r"into something else", r"\b(canva|capcut|figma|dropbox|davinci|final cut|docusign)\b"]},
    {"id": "gate", "category": "New Sale", "type": "new_product", "weight": 0.70, "conf": 0.74,
     "label": "Premium feature gate met",
     "patterns": [r"premium feature", r"\blocked\b", r"need(s)? to upgrade", r"not available on my plan", r"greyed out",
                  r"is that a glitch"]},
    {"id": "fit", "category": "New Sale", "type": "new_product", "weight": 0.70, "conf": 0.90,
     "label": "Sees the value — unsure of the fit",
     "patterns": [r"worth (paying|it)", r"paying for stuff i don'?t need", r"do sell better", r"it matters", r"slowing me (right )?down"]},
    {"id": "governance", "category": "Cross-Sell", "type": "cross_sell", "weight": 0.85, "conf": 0.88,
     "label": "Asset governance gap — outside Studio Cloud",
     "patterns": [r"out-?of-?date", r"old(er)? version", r"which (one|version) is (approved|current|right)", r"wrong (version|image|asset|file)",
                  r"(just|everyone) guess", r"approved", r"last season", r"nobody caught"]},
    {"id": "scale", "category": "Upsell", "type": "expansion", "weight": 0.45, "conf": 0.88,
     "label": "Operating at volume",
     "patterns": [r"\b(\d+|ten|fifteen|twenty|thirty|forty|fifty|hundred|thousands?)\b.{0,40}\b(a|per|every|this) (month|week)",
                  r"\bthousands\b", r"(four|three|several|multiple|\d+) brands", r"\bvolume\b"]},
    {"id": "measure", "category": "Cross-Sell", "type": "cross_sell", "weight": 0.60, "conf": 0.90,
     "label": "Wants to measure what performs",
     "patterns": [r"which .{0,30}(drive|perform|work|sell|convert)", r"\bmeasure", r"\banalytics\b", r"track (the )?performance"]},
    {"id": "document", "category": "Cross-Sell", "type": "cross_sell", "weight": 0.85, "conf": 0.88,
     "label": "Needs documents signed — outside Studio Cloud",
     "patterns": [r"\bsign(ed|ing|ature|atures)?\b", r"contracts?", r"e-?sign", r"(print|printing) .{0,30}scan", r"approve .{0,20}pdf"]},
]

# Things a customer says that mean: do not sell. They move sentiment and hold the score down.
FAILURE = [r"charged (me )?twice", r"double charged", r"\brefund", r"nothing has happened", r"not good enough",
           r"\bignored\b", r"complain", r"unacceptable", r"second (call|time)", r"still (waiting|not|outstanding)",
           r"i rang last week", r"money back"]
TRANSACTIONAL = [r"password", r"can'?t (sign|log) in", r"locked out", r"reset", r"update my (card|email|address)",
                 r"(copy of|download) (my|the|an) invoice", r"won'?t install", r"error code", r"crash"]

POSITIVE = [r"thank", r"brilliant", r"perfect", r"great", r"lovely", r"that would be", r"yes,? please", r"makes sense",
            r"exactly", r"i'?d (love|rather|like)", r"helpful", r"sorted", r"please\."]
NEGATIVE = [r"ridiculous", r"frustrat", r"annoy", r"nightmare", r"not good enough", r"ignored", r"can'?t", r"stopped",
            r"keeps? (telling|getting|saying)", r"messy", r"slowing", r"charged (me )?twice", r"nothing has happened",
            r"too expensive", r"cancel", r"lose", r"wrong", r"problem", r"again"]
AGENT_LIFT = [r"i can see", r"let me", r"i'?m (processing|sending|escalating|applying)", r"i'?ll ", r"that should",
              r"sorry", r"you'?re right", r"understood", r"straightforward"]


def _find(patterns, text):
    hits = []
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            hits.append(m.group(0).strip())
    return hits


def detect(text):
    """Signals in one customer utterance."""
    out = []
    for d in DETECTORS:
        hits = _find(d["patterns"], text)
        if hits:
            out.append({"detector": d["id"], "type": d["type"], "category": d["category"], "signal": d["label"],
                        "keywords": hits[:3], "confidence": round(min(0.97, d["conf"] + 0.03 * (len(hits) - 1)), 2),
                        "weight": d["weight"]})
    return out


def utterance_sentiment(role, text):
    pos, neg = len(_find(POSITIVE, text)), len(_find(NEGATIVE, text)) + 2 * len(_find(FAILURE, text))
    if role == "agent":
        return None, len(_find(AGENT_LIFT, text))
    if not pos and not neg:
        return 0.5, 0
    return max(0.05, min(0.95, 0.5 + 0.17 * pos - 0.15 * neg)), 0


def _logit(p):
    p = max(0.01, min(0.99, p))
    return math.log(p / (1 - p))


# ══════════════════════════════════════════════════════════════════════════════
#  ANALYSIS — the whole conversation so far, in one call
# ══════════════════════════════════════════════════════════════════════════════
def analyse(conversation, treatment, profile=None, intent_id=None):
    """conversation: [{role, text}], in order. treatment: what the Frontier decided.
    Returns the same shape the scripted analysis does, so the workspace cannot tell them apart."""
    routed = treatment["decision"] == "sell"
    p0 = treatment.get("propensity_raw", treatment["propensity"])
    seen, signals, sentiment = set(), [], 0.5
    failure_hits, transactional_hits = [], []
    sentiments = []

    for i, m in enumerate(conversation):
        text = m.get("text_en") or m["text"]
        s, lift = utterance_sentiment(m["role"], text)
        if m["role"] == "customer":
            failure_hits += _find(FAILURE, text)
            transactional_hits += _find(TRANSACTIONAL, text)
            sentiment = 0.55 * sentiment + 0.45 * s
            for sig in detect(text):
                if sig["detector"] not in seen:
                    seen.add(sig["detector"])
                    signals.append({**sig, "turn": i})
        else:
            sentiment = min(0.95, sentiment + 0.04 * lift)
        sentiments.append(round(sentiment, 2))

    # A failure raised in conversation suppresses the commercial motion even if the
    # profile did not flag one — the customer's word outranks the data.
    raised_failure = len(failure_hits) >= 2
    if raised_failure:
        routed = False

    if routed:
        z = -1.05 + 0.5 * _logit(p0) + sum(s["weight"] for s in signals)
        score = int(round(100 * fe.sigmoid(z)))
    else:
        score = int(round(100 * fe.sigmoid(-2.6 + 0.2 * len(signals) - 0.3 * len(failure_hits))))
        signals = []

    qualified = routed and score >= 80 and len(signals) >= 2
    offer = treatment.get("offer")
    stage = ("suppressed" if (treatment.get("override") or raised_failure)
             else "standard" if not routed
             else "qualified" if qualified
             else "warming" if signals else "listening")

    return {
        "signals": [{k: v for k, v in s.items() if k != "weight"} for s in signals],
        "lead_score": score,
        "sentiment": round(sentiment, 2),
        "sentiments": sentiments,
        "routed": routed,
        "qualified": qualified,
        "stage": stage,
        "raised_failure": raised_failure,
        "coaching": coaching(stage, treatment, signals, profile, intent_id),
        "grounding": kb.grounding(intent_id, offer if routed and signals else None,
                                  retention=bool(offer and offer["type"] == "Retention")),
        "suggested_replies": replies(stage, treatment, conversation, profile, intent_id),
    }


def coaching(stage, treatment, signals, profile, intent_id):
    seg = treatment.get("segment")
    offer = treatment.get("offer")
    if stage == "suppressed":
        return {"suggestion": "No offers on this call. Acknowledge what went wrong without making excuses, "
                              "put it right now rather than passing it on, and give a reference.",
                "priority": "critical", "type": "service"}
    if stage == "standard":
        return {"suggestion": "Nothing to sell here. Fix it quickly — a fast, clean call is the right "
                              "result.", "priority": "low", "type": "service"}
    if stage == "listening":
        opener = {"capacity": "Confirm the limit first and resolve the anxiety before discussing any change of plan.",
                  "value": "Do not lead with an offer. Ask what they actually use — the answer decides whether there is a genuine save.",
                  "explorer": "Answer the question honestly first. Credibility here earns the rest of the conversation.",
                  "growth": "Nothing is broken. Be straight about what the current product does and does not cover."}
        return {"suggestion": opener.get(seg, "Resolve the request first."), "priority": "medium", "type": "service"}
    names = ", ".join(s["signal"].lower() for s in signals[-2:])
    if stage == "warming":
        if offer:
            return {"suggestion": "The need is real: %s. Introduce %s — %s" % (
                names, offer["offer"]["to"][0]["product"], offer["why"]), "priority": "high", "type": "product"}
        return {"suggestion": "The need is real: %s. Ask one more question to establish what would remove it." % names,
                "priority": "high", "type": "product"}
    # qualified
    if offer:
        tail = (" Cross-cloud opportunity — warm handoff to the specialist team, do not try to close it yourself."
                if offer["offer"]["crosses_cloud"] and offer["value"] >= 1000 else
                " Present this one option. Do not oversell.")
        return {"suggestion": offer["recommended_action"] + tail, "priority": "high", "type": "closing"}
    return {"suggestion": "The customer is ready, and there is no catalogue offer that fits. Capture the need and "
                          "refer it rather than improvising one.", "priority": "medium", "type": "closing"}


def replies(stage, treatment, conversation, profile, intent_id):
    """What the agent might say next. Offered, never sent automatically."""
    first = ((profile or {}).get("person", {}).get("name", {}).get("firstName")) or "there"
    ent = ((profile or {}).get("_cxdemo", {}) or {}).get("entitlement", {})
    plan = ent.get("planName", "your plan")
    offer = treatment.get("offer")
    agent_turns = sum(1 for m in conversation if m["role"] == "agent")
    if agent_turns == 0:
        facts = treatment.get("features") or []
        lead = next((f for f in facts if f["direction"] == "up" and f["id"] in ("capacity", "licence", "gates", "mismatch", "gap")), None)
        seen = (", and I can see %s" % (lead["value"][0].lower() + lead["value"][1:])) if lead else ""
        if stage == "suppressed":
            return ["I'm very sorry, %s — that shouldn't have happened. Let me look at this right now." % first]
        return ["Hi %s, thanks for getting in touch. You're on %s%s. Let me take a look." % (first, plan, seen)]
    if stage == "suppressed":
        return ["You're right, and I'm not going to defend it. I'm processing this directly rather than sending it back through the queue.",
                "I'll send written confirmation with a reference, so you have it on record."]
    if stage == "standard":
        return ["That should do it — you'll have an email in the next couple of minutes.",
                "Is there anything else I can help with today?"]
    if stage == "listening":
        return ["That makes sense. Can I ask how you're using it day to day?",
                "Let me check what's happening on the account."]
    if stage == "warming":
        return ["So this isn't a one-off — it's how you work now. Let me look at what would give you room.",
                "Can I ask roughly how often that happens?"]
    if offer:
        return ["There's an option built for exactly this — %s. Shall I walk you through it?" % offer["offer"]["to"][0]["product"],
                "I can set that up now, and you'll keep everything you already have."]
    return ["Let me note exactly what you need and get the right team to come back to you."]


# ══════════════════════════════════════════════════════════════════════════════
#  EVALUATION — the rules engine against the curated analysis
# ══════════════════════════════════════════════════════════════════════════════
def evaluation(scenarios, treatments):
    """For each scripted contact: does the rules engine reach the same outcome the
    curated analysis did, and how many of the curated signals does it find?"""
    rows, found, expected, agree = [], 0, 0, 0
    for sc in scenarios:
        t = treatments[sc["id"]]
        conv = [{"role": m["role"], "text": m.get("text_en") or m["text"]} for m in sc["conversation"]]
        a = analyse(conv, t, None, None)
        curated = sc["ai_analysis"]["signals"]
        cur_turns = sorted(set(s["turn"] for s in curated))
        got_turns = sorted(set(s["turn"] for s in a["signals"]))
        hit = len([x for x in cur_turns if x in got_turns])
        curated_lead = bool(sc["ai_analysis"].get("lead_summary")) and t["decision"] == "sell"
        same = curated_lead == a["qualified"]
        rows.append({"id": sc["id"], "customer": sc["customer"]["name"], "type": sc["type"],
                     "curated_signals": len(cur_turns), "found": hit,
                     "engine_signals": len(a["signals"]),
                     "curated_score": sc["ai_analysis"]["lead_score_progression"][-1], "engine_score": a["lead_score"],
                     "curated_outcome": "lead" if curated_lead else "no lead",
                     "engine_outcome": "lead" if a["qualified"] else "no lead", "agree": same})
        found += hit
        expected += len(cur_turns)
        agree += 1 if same else 0
    return {"contacts": len(rows), "outcome_agreement": agree, "signal_turns_expected": expected,
            "signal_turns_found": found, "recall": round(found / float(expected or 1), 2), "rows": rows}
