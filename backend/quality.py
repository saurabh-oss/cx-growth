"""
SALES & SERVICE QUALITY AGENT — every contact scored, not a sample of them.

Quality assurance in a contact centre is usually a supervisor listening to two or three
calls per agent per month. This agent reads every transcript at wrap-up and scores it on
three things:

    SERVICE     was the customer's problem handled well?
    SALES       when the engine surfaced an opportunity, was it acted on — properly?
    COMPLIANCE  were the guardrails respected?

Each criterion carries its evidence: the turn it was found in and the words that
satisfied it. A score without evidence is an opinion; an agent can argue with an opinion,
and should.

The checks are pattern rules over the transcript plus the engine's own record of what it
decided. With ANTHROPIC_API_KEY set the same criteria can be judged by Claude; the rules
are the floor that works offline.
"""
import re

GREETING = [r"\bhi\b", r"\bhello\b", r"thanks for (calling|getting in touch)", r"good (morning|afternoon)"]
EMPATHY = [r"\bsorry\b", r"i understand", r"understood", r"you'?re right", r"that makes sense", r"that shouldn'?t have",
           r"completely understood", r"not going to defend", r"that'?s (really )?useful"]
DIAGNOSE = [r"i can see", r"can i (ask|check)", r"let me (check|look)", r"which apps", r"how many", r"roughly how"]
RESOLVE = [r"i'?m (processing|sending|escalating|applying)", r"sending that now", r"i can (send|set|apply|process)",
           r"that should", r"you'?ll (get|have|be)", r"let me (walk|show|lay)", r"i'?ll send", r"straight back in"]
OWNERSHIP = [r"\bi'?m\b", r"\bi'?ll\b", r"\blet me\b", r"\bi can\b"]
DISCOVERY = [r"can i ask", r"which apps", r"how many", r"roughly how", r"what (are|do) you", r"how (are|do) you"]
OFFER = [r"there'?s (an|a straightforward) option", r"there'?s a plan", r"there is,? and it'?s built", r"let me (show|walk|lay)",
         r"an acme side", r"it does,? and it works", r"option that", r"upgrade", r"\bplan built\b", r"move(s)? you to"]
PRESSURE = [r"limited time", r"today only", r"you (need|have) to (buy|upgrade|decide)", r"last chance", r"offer ends",
            r"before it'?s too late", r"you must"]
VERIFY = [r"verif(y|ied)", r"confirm (your|a few) (details|identity)", r"security question"]


def _first(patterns, turns):
    """(turn index, matched words) of the first agent turn matching any pattern."""
    for i, text in turns:
        for p in patterns:
            m = re.search(p, text, re.I)
            if m:
                return i, _quote(text, m)
    return None, None


def _quote(text, m, span=58):
    a = max(0, m.start() - 18)
    b = min(len(text), m.end() + span)
    s = text[a:b].strip()
    return ("…" if a > 0 else "") + s + ("…" if b < len(text) else "")


def _c(name, ok, weight, turn, evidence, why, fail=None):
    return {"name": name, "pass": bool(ok), "weight": weight, "turn": turn, "evidence": evidence, "why": why,
            "fail": fail or name.lower()}


def _pct(items):
    total = sum(c["weight"] for c in items) or 1
    return int(round(100.0 * sum(c["weight"] for c in items if c["pass"]) / total))


def score(conversation, treatment, sentiments=None, lead_captured=False, auth="VERIFIED"):
    """conversation: [{role, text}] — English text for a translated contact."""
    agent = [(i, m["text"]) for i, m in enumerate(conversation) if m["role"] == "agent"]
    cust = [(i, m.get("text_en") or m["text"]) for i, m in enumerate(conversation) if m["role"] == "customer"]
    sell = treatment["decision"] == "sell"
    suppressed = bool(treatment.get("override")) or treatment.get("segment") == "recovery"
    negative_open = bool(sentiments) and min(sentiments[:2] or [0.5]) < 0.35

    # ── SERVICE ──
    gi, ge = _first(GREETING + EMPATHY, agent[:1])
    ei, ee = _first(EMPATHY, agent)
    di, de = _first(DIAGNOSE, agent)
    ri, re_ = _first(RESOLVE, agent[-2:] if len(agent) >= 2 else agent)
    own = sum(1 for _, t in agent if any(re.search(p, t, re.I) for p in OWNERSHIP))
    service = [
        _c("Opened by acknowledging the customer", gi is not None, 1, gi, ge,
           "First words set whether the customer feels heard."),
        _c("Showed empathy" + (" on a negative opening" if negative_open else ""), ei is not None,
           2 if negative_open else 1, ei, ee,
           "Weighted double when the customer opened angry." if negative_open else "Acknowledged the customer's position."),
        _c("Diagnosed before proposing", di is not None, 2, di, de,
           "Looked at the account or asked a question before suggesting anything."),
        _c("Stated a clear resolution", ri is not None, 2, ri, re_,
           "The customer left knowing what happens next."),
        _c("Took ownership", own >= max(1, len(agent) // 2), 1, agent[0][0] if agent else None,
           "%d of %d agent turns in the first person" % (own, len(agent)),
           "Says \"I'll\", not \"the system will\"."),
    ]

    # ── SALES ──
    oi, oe = _first(OFFER, agent)
    qi, qe = _first(DISCOVERY, agent)
    pi, pe = _first(PRESSURE, agent)
    first_agent = agent[0][0] if agent else 0
    sales = []
    if sell:
        sales = [
            _c("Resolved first, offered second", oi is not None and oi > first_agent, 2, oi, oe,
               "An offer in the opening turn is a pitch. After the diagnosis it is advice."),
            _c("Asked a discovery question", qi is not None, 2, qi, qe,
               "The customer's own description of the need is what makes the offer fit."),
            _c("Acted on the signal the engine surfaced", oi is not None, 3, oi, oe,
               "The engine found an opportunity. Did the agent open the door to it?"),
            _c("No pressure language", pi is None, 2, pi, pe or "None found in the transcript",
               "No urgency was manufactured."),
            _c("Opportunity captured", lead_captured, 1, None,
               "Lead written to the contact record" if lead_captured else "No lead recorded",
               "The conversation reached a qualified lead."),
        ]

    # ── COMPLIANCE ──
    vi, ve = _first(VERIFY, agent)
    compliance = [
        _c("Identity verified before account changes", auth == "VERIFIED" or vi is not None, 1, vi,
           ve or ("Verified in the IVR" if auth == "VERIFIED" else "Challenge failed and no agent verification found"),
           "Plan, billing and email changes need a verified identity.",
           fail="the account was changed without verifying who was calling"),
    ]
    if not sell:
        compliance.append(_c(
            "No offer on a contact treated SOLVE" if not suppressed else "Commercial hold respected",
            oi is None, 3, oi, oe or "No offer language anywhere in the transcript",
            "The Frontier decided this contact was not a selling opportunity. The agent honoured it.",
            fail="an offer was made on a contact the engine had held back"))
    compliance.append(_c("No pressure language", pi is None, 1, pi, pe or "None found in the transcript",
                         "Applies to every contact, sold to or not.", fail="pressure language was used"))

    s_service, s_sales = _pct(service), (_pct(sales) if sales else None)
    breach = [c for c in compliance if not c["pass"]]
    overall = s_service if s_sales is None else int(round(0.5 * s_service + 0.5 * s_sales))
    if breach:
        overall = min(overall, 49)               # a compliance breach caps the score, whatever else went well

    misses = [c for c in service + sales if not c["pass"]]
    coach = ("Compliance breach: %s." % breach[0]["fail"]) if breach else (
        "Strongest area to work on: %s." % misses[0]["name"].lower() if misses
        else "Nothing to correct. Use this contact as a coaching example.")
    return {
        "overall": overall, "service": s_service, "sales": s_sales,
        "compliance": "pass" if not breach else "breach",
        "band": "Exemplary" if overall >= 90 else "Meets standard" if overall >= 75 else "Coach" if overall >= 50 else "Review",
        "sections": [
            {"id": "service", "name": "Service", "score": s_service, "criteria": service},
            {"id": "sales", "name": "Sales execution", "score": s_sales, "criteria": sales,
             "note": None if sales else "Not scored — the Frontier treated this contact SOLVE."},
            {"id": "compliance", "name": "Compliance", "score": None, "criteria": compliance,
             "status": "pass" if not breach else "breach"},
        ],
        "coaching_note": coach,
        "coverage": "Every contact is scored. Manual QA typically samples two to three per agent per month.",
        "agent": "Sales & Service Quality Agent",
    }
