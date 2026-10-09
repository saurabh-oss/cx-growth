"""
INTELLIGENT CUSTOMER FRONTIER — the decision engine.

frontdoor.py describes the treatment. This module computes it.

    profile + IVR context ─▶ features ─▶ propensity ─▶ segment ─▶ guardrails ─▶ SOLVE / SELL ─▶ route

Every number the Frontier shows is produced here from the customer's profile and the
intent the IVR captured. Change an attribute on the profile and the decision changes
with it — that is the difference between a model and a slide.

THE MODEL is a logistic regression over seventeen background features. It is deliberately
simple and fully inspectable: each feature has one weight, each contribution is
weight x value, and the propensity is the logistic of their sum. A contact centre
director can read it. A gradient-boosted model would score a little better and explain
nothing.

THE GUARDRAILS are code, not policy. Service recovery, marketing consent, offer cooldown
and identity are each checked on every contact, and a contact that fails any of them is
treated SOLVE whatever its propensity. They are exercised by tests/test_engine.py.
"""
import math
from datetime import datetime, timedelta, timezone

import catalogue as cat

THRESHOLD = 0.55
OFFER_COOLDOWN_DAYS = 30
RECOVERY_SUPPRESSION_DAYS = 14

# ══════════════════════════════════════════════════════════════════════════════
#  IVR INTENTS — what the Frontier can capture before an agent is involved
#  signal: the intent's own commercial lean, -1 (purely transactional) to +1
# ══════════════════════════════════════════════════════════════════════════════
INTENTS = {
    "storage.limit":      {"label": "Storage full / sync stopped",     "path": "Main › Studio Cloud › Storage & Sync",
                           "family": "capacity", "signal": 0.8,  "queue": "creative"},
    "credits.exhausted":  {"label": "Generative credits exhausted",    "path": "Main › Studio Cloud › Generative AI & Credits",
                           "family": "capacity", "signal": 0.8,  "queue": "creative"},
    "account.concurrent": {"label": "Signed out — used elsewhere",     "path": "Main › Account & Sign-in › Used on another device",
                           "family": "capacity", "signal": 0.7,  "queue": "creative"},
    "feature.gated":      {"label": "Premium feature blocked",         "path": "Web widget › Acme Express › Feature help",
                           "family": "explorer", "signal": 0.7,  "queue": "express"},
    "assets.versioning":  {"label": "Libraries, sharing & versions",   "path": "Main › Studio Cloud › Libraries & Sharing",
                           "family": "growth",   "signal": 0.5,  "queue": "creative"},
    "documents.sign":     {"label": "PDF export & signatures",         "path": "Main › Studio Cloud › Export & PDF",
                           "family": "growth",   "signal": 0.7,  "queue": "creative"},
    "howto.feature":      {"label": "How-to question",                 "path": "Main › Studio Cloud › Using the apps",
                           "family": "growth",   "signal": 0.1,  "queue": "creative"},
    "plan.compare":       {"label": "Plan & pricing question",         "path": "Main › Billing & Plans › Compare plans",
                           "family": "value",    "signal": 0.9,  "queue": "creative"},
    "billing.cancel":     {"label": "Cancel subscription",             "path": "Main › Billing & Plans › Cancel Subscription",
                           "family": "value",    "signal": 0.85, "queue": "retention"},
    "billing.dispute":    {"label": "Incorrect charge",                "path": "Main › Billing & Plans › Incorrect charge",
                           "family": "recovery", "signal": -0.2, "queue": "billing"},
    "refund.status":      {"label": "Refund status",                   "path": "Main › Billing & Plans › Refund status",
                           "family": "recovery", "signal": -0.4, "queue": "billing"},
    "account.access":     {"label": "Password / sign-in help",         "path": "Main › Account & Sign-in › Password help",
                           "family": "access",   "signal": -1.0, "queue": "access", "transactional": True},
    "account.profile":    {"label": "Change email or profile",         "path": "Main › Account & Sign-in › Update details",
                           "family": "access",   "signal": -0.9, "queue": "access", "transactional": True},
    "billing.payment":    {"label": "Update payment method",           "path": "Main › Billing & Plans › Payment method",
                           "family": "access",   "signal": -0.8, "queue": "billing", "transactional": True},
    "billing.invoice":    {"label": "Invoice or receipt copy",         "path": "Main › Billing & Plans › Invoices",
                           "family": "access",   "signal": -0.8, "queue": "billing", "transactional": True},
    "install.error":      {"label": "Install or update error",         "path": "Main › Studio Cloud › Install & Update",
                           "family": "access",   "signal": -0.7, "queue": "creative", "transactional": True},
    "app.crash":          {"label": "App crash or performance",        "path": "Main › Studio Cloud › Technical issue",
                           "family": "access",   "signal": -0.6, "queue": "creative", "transactional": True},
}

QUEUES = {
    "creative":  "CC-Consumer-Photography-EN",
    "retention": "CC-Consumer-Retention-EN",
    "express":   "CC-Express-Support-EN",
    "access":    "CC-Account-Access-EN",
    "billing":   "CC-Billing-EN",
    "smb":       "CC-SmallBusiness-EN",
}


def intent(intent_id):
    return INTENTS.get(intent_id) or INTENTS["howto.feature"]


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURES — one extractor each: profile + context in, (value, plain-English read) out
# ══════════════════════════════════════════════════════════════════════════════
def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _t(profile):
    t = profile.get("_cxdemo", {})
    return (t.get("entitlement", {}), t.get("usage", {}), t.get("service", {}),
            t.get("health", {}), t.get("commercial", {}))


def _years(months):
    if months < 12:
        return "%d months" % months
    y = months / 12.0
    return ("%d years" % round(y)) if abs(y - round(y)) < 0.2 else "%d months" % months


def f_capacity(p, ctx):
    e, u, *_ = _t(p)
    st, cr = u.get("storageUsedPct", 0), u.get("generativeCreditsUsedPct", 0)
    sx, cx = _clamp((st - 70) / 30.0), _clamp((cr - 70) / 30.0)
    if sx >= cx:
        return sx, "%d%% of %s storage" % (st, _gb(u.get("storageQuotaGb", 0)))
    return cx, "%d%% of monthly generative credits" % cr


def _gb(g):
    return "%dTB" % (g // 1000) if g >= 1000 else "%dGB" % g


def f_recurring(p, ctx):
    n = _t(p)[1].get("creditsExhaustedMonths", 0)
    return _clamp(n / 3.0), ("Exhausted %d months running" % n if n else "Never exhausted")


def f_licence(p, ctx):
    e, u, *_ = _t(p)
    users, seats = u.get("distinctUsers30d", 1), e.get("seats", 1)
    if e.get("licenceType") != "INDIVIDUAL" or users <= 1:
        return 0.0, "%d user%s on %d seat%s" % (users, "" if users == 1 else "s", seats, "" if seats == 1 else "s")
    return _clamp((users - 1) / 2.0), "%d users · %d devices · %d locations on one individual licence" % (
        users, u.get("concurrentDevices", users), u.get("distinctLocations", 1))


def f_gates(p, ctx):
    n = _t(p)[1].get("featureGateHits30d", 0)
    return _clamp(n / 15.0), "%d premium gates hit in 30 days" % n


def f_headroom(p, ctx):
    code = _t(p)[0].get("planCode")
    return cat.headroom(code), cat.headroom_read(code)


def f_trend(p, ctx):
    v = _t(p)[1].get("usageTrendPct", 0)
    return _clamp(v / 50.0, -1, 1), ("%+d%% usage, year on year" % v if v else "Stable — no growth")


def f_mismatch(p, ctx):
    e, u, *_ = _t(p)
    ent, used = u.get("appsEntitled", 1), u.get("appsUsed30d", 1)
    if ent < 10:
        return 0.0, "%d of %d apps in use" % (used, ent)
    return _clamp(1 - used / 6.0), "Paying for %d apps, using %d" % (ent, used)


def f_engagement(p, ctx):
    e, u, *_ = _t(p)
    ent, used = max(1, u.get("appsEntitled", 1)), u.get("appsUsed30d", 0)
    x = _clamp(used / float(min(ent, 8)))
    return x, "%d of %d apps active in 30 days" % (used, ent)


def f_commercial(p, ctx):
    v = _t(p)[4].get("commercialUse")
    return (1.0, str(v)) if v else (0.0, "Personal use")


def f_thirdparty(p, ctx):
    v = _t(p)[4].get("thirdPartySpend")
    return (1.0, str(v)) if v else (0.0, "None detected")


def f_gap(p, ctx):
    e, u, *_ = _t(p)
    assets, brands = u.get("assetsPerMonth", 0), u.get("brandCount", 1)
    if brands < 2 or cat.EXPERIENCE in e.get("cloudsOwned", []):
        return 0.0, "No cross-cloud gap"
    return _clamp(assets / 200.0), "%d assets / month across %d brands, no governance product" % (assets, brands)


def f_health(p, ctx):
    h = _t(p)[3]
    s = h.get("score", 70)
    return _clamp((s - 60) / 40.0, -1, 1), "%d · NPS %s" % (s, h.get("nps", "—"))


def f_tenure(p, ctx):
    m = _t(p)[0].get("tenureMonths", 0)
    return _clamp(m / 48.0), _years(m)


def f_value(p, ctx):
    v = _t(p)[0].get("annualValue", 0)
    return _clamp(v / 720.0), "${:,.2f}/yr".format(v)


def f_intent(p, ctx):
    i = intent(ctx.get("intent"))
    return i["signal"], i["label"]


def f_service(p, ctx):
    s = _t(p)[2]
    n = int(s.get("openCaseCount", 0))
    x = _clamp(0.5 * n + 0.3 * bool(s.get("repeatContact7d")) + 0.4 * bool(s.get("duplicateChargeFlag")))
    bits = []
    if s.get("duplicateChargeFlag"):
        bits.append("duplicate charge")
    if n:
        bits.append("%d open case%s" % (n, "" if n == 1 else "s"))
    if s.get("repeatContact7d"):
        bits.append("repeat contact in 7 days")
    return x, (", ".join(bits).capitalize() if bits else "None open")


def f_declined(p, ctx):
    n = _t(p)[4].get("offersDeclined12m", 0)
    return _clamp(n / 3.0), ("%d declined in 12 months" % n if n else "None declined in 12 months")


FEATURES = [
    {"id": "capacity",    "name": "Storage or credits used up",        "fn": f_capacity},
    {"id": "recurring",   "name": "Runs out month after month",        "fn": f_recurring},
    {"id": "licence",     "name": "People sharing one licence",        "fn": f_licence},
    {"id": "gates",       "name": "Blocked by paid features",          "fn": f_gates},
    {"id": "headroom",    "name": "Room to move up a plan",            "fn": f_headroom},
    {"id": "trend",       "name": "Using it more each year",           "fn": f_trend},
    {"id": "mismatch",    "name": "Paying for more than they use",     "fn": f_mismatch},
    {"id": "engagement",  "name": "How much they use it",              "fn": f_engagement},
    {"id": "commercial",  "name": "Uses it for business",              "fn": f_commercial},
    {"id": "thirdparty",  "name": "Pays someone else for what we sell", "fn": f_thirdparty},
    {"id": "gap",         "name": "Needs something outside their plan", "fn": f_gap},
    {"id": "health",      "name": "Health of the relationship",        "fn": f_health},
    {"id": "tenure",      "name": "Time as a customer",                "fn": f_tenure},
    {"id": "value",       "name": "What they spend with us",           "fn": f_value},
    {"id": "intent",      "name": "Why they are calling",              "fn": f_intent},
    {"id": "service",     "name": "Unresolved problems",               "fn": f_service},
    {"id": "declined",    "name": "Offers already turned down",        "fn": f_declined},
]
FEATURE_IDS = [f["id"] for f in FEATURES]
FEATURE_NAME = {f["id"]: f["name"] for f in FEATURES}

# Baseline weights — model v1, the champion at start-up.
BASELINE = {
    "version": "v1",
    "bias": -2.30,
    "weights": {
        "capacity":   1.05, "recurring":  0.30, "licence":    1.35, "gates":      0.65,
        "headroom":   0.50, "trend":      0.50, "mismatch":   2.30, "engagement": 0.40,
        "commercial": 0.45, "thirdparty": 0.20, "gap":        1.20, "health":     0.30,
        "tenure":     0.25, "value":      0.60, "intent":     1.55, "service":   -0.25,
        "declined":  -0.90,
    },
}


def sigmoid(z):
    if z < -40:
        return 0.0
    if z > 40:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def extract(profile, ctx):
    """Feature vector plus the human-readable read of each feature."""
    xs, reads = {}, {}
    for f in FEATURES:
        x, read = f["fn"](profile, ctx)
        xs[f["id"]] = float(x)
        reads[f["id"]] = read
    return xs, reads


def propensity(xs, model):
    z = model["bias"] + sum(model["weights"][k] * xs[k] for k in FEATURE_IDS)
    return sigmoid(z)


def contributions(xs, reads, model, top=7):
    """Each feature's share of the decision, largest first. Shares are of the total
    absolute movement, so they sum to 1 and are comparable across contacts."""
    rows = []
    for k in FEATURE_IDS:
        c = model["weights"][k] * xs[k]
        rows.append({"id": k, "name": FEATURE_NAME[k], "value": reads[k], "x": round(xs[k], 3),
                     "coef": round(model["weights"][k], 3), "contribution": round(c, 3),
                     "direction": "up" if c >= 0 else "down"})
    total = sum(abs(r["contribution"]) for r in rows) or 1.0
    for r in rows:
        r["weight"] = round(abs(r["contribution"]) / total, 2)
    rows.sort(key=lambda r: -abs(r["contribution"]))
    return [r for r in rows if abs(r["contribution"]) > 0.001][:top]


# ══════════════════════════════════════════════════════════════════════════════
#  SEGMENT — every contact lands in exactly one
# ══════════════════════════════════════════════════════════════════════════════
def segment_for(profile, ctx, xs=None):
    e, u, s, h, cm = _t(profile)
    i = intent(ctx.get("intent"))
    if xs is None:
        xs, _ = extract(profile, ctx)

    if s.get("duplicateChargeFlag") or (s.get("openCaseCount", 0) and s.get("repeatContact7d")) \
            or (i["family"] == "recovery" and s.get("openCaseCount", 0)):
        return "recovery", "Something went wrong and has not been put right"
    if i["family"] == "recovery":
        return "recovery", "They are calling about a billing mistake"
    if i["family"] == "value":
        return "value", "They are calling about price, or whether the plan fits"
    if i.get("transactional"):
        return "access", "A routine request — nothing to sell here"
    if cat.plan(e.get("planCode"))["tier"] == 0:
        return "explorer", "On the free plan and running into paid features"
    if xs["capacity"] >= 0.8 or xs["recurring"] >= 0.66 or xs["licence"] >= 0.5:
        return "capacity", "Has run out of storage, credits or licences"
    if i["family"] == "explorer":
        return "explorer", "Running into paid features on a starter plan"
    if xs["health"] >= 0.25 and xs["trend"] > 0 and (xs["gap"] > 0 or xs["headroom"] > 0 or i["signal"] >= 0.5):
        return "growth", "Happy, growing, and nothing is broken"
    return "access", "Nothing suggests they want to buy"


SELL_SEGMENTS = {"capacity", "value", "growth", "explorer"}


# ══════════════════════════════════════════════════════════════════════════════
#  GUARDRAILS — checked on every contact, in code
# ══════════════════════════════════════════════════════════════════════════════
def _parse(ts):
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _offer_age(days):
    if days <= 0:
        return "An offer was made today"
    return "An offer was made %d day%s ago" % (days, "" if days == 1 else "s")


def guardrails(profile, ctx, segment, now=None):
    now = now or datetime.now(timezone.utc)
    e, u, s, h, cm = _t(profile)
    consent = (((profile.get("consents") or {}).get("marketing") or {}).get("any") or {}).get("val", "y")
    last_offer = _parse(cm.get("lastOfferDate"))
    suppressed = _parse(cm.get("suppressedUntil"))
    cooling = bool(last_offer and (now - last_offer) < timedelta(days=OFFER_COOLDOWN_DAYS))
    held = bool(suppressed and suppressed > now)
    out = [
        # name: the check, as a statement that should be true.  block: what to call it when it is not.
        {"id": "recovery", "name": "No unresolved problem", "block": "An unresolved problem",
         "pass": segment != "recovery",
         "detail": "Something went wrong and has not been put right. No offer until it is."
                   if segment == "recovery" else "Nothing outstanding on the account"},
        {"id": "consent", "name": "Customer accepts offers", "block": "Customer opted out of offers",
         "pass": consent != "n",
         "detail": "This customer has asked not to receive offers" if consent == "n" else "Consent is on record"},
        {"id": "cooldown", "name": "No offer in the last %d days" % OFFER_COOLDOWN_DAYS,
         "block": "%d-day pause between offers" % OFFER_COOLDOWN_DAYS,
         "pass": not cooling,
         "detail": (_offer_age((now - last_offer).days)) if cooling else "No recent offer"},
        {"id": "suppression", "name": "No hold after a complaint", "block": "On hold after a complaint",
         "pass": not held,
         "detail": ("No offers until %s" % suppressed.strftime("%d %b")) if held else "No hold on the account"},
    ]
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTING
# ══════════════════════════════════════════════════════════════════════════════
def route(profile, ctx, segment, decision, offer):
    e = _t(profile)[0]
    i = intent(ctx.get("intent"))
    smb = profile.get("_cxdemo", {}).get("customerType") == "Small Business"
    queue = QUEUES["smb"] if smb else QUEUES[i["queue"]]

    if segment == "recovery":
        skill, why = "Billing · Tier 2 · Recovery", \
            "Goes to an agent who can put it right on the spot. No offers for %d days afterwards." % RECOVERY_SUPPRESSION_DAYS
    elif decision == "solve":
        skill, why = "Service · Tier 1", \
            "Goes to the first available agent. The right outcome is a quick, clean fix."
    elif segment == "value":
        skill, why = "Retention-certified · Tier 2", "Goes to an agent who can change the plan — a better fit, not a discount."
    elif smb and offer and offer["offer"]["crosses_cloud"]:
        skill, why = "Small business · Cross-cloud qualified", \
            "Goes to an agent who can introduce the %s specialists personally." % offer["offer"]["to"][0]["cloud"]
    elif smb:
        skill, why = "Small business · Licence advisory", \
            "Goes to an agent who can set up team licences and company invoicing."
    elif offer and offer["offer"]["crosses_cloud"]:
        skill, why = "Growth-enabled · Cross-cloud", "Goes to an agent who can sell across Acme's product lines."
    elif offer and offer.get("trial"):
        skill, why = "Growth-enabled · Tier 1", "Goes to an agent who can start a free trial on the call."
    else:
        skill, why = "Growth-enabled · Tier 1", "Goes to an agent trained and authorised to make an offer."

    lang = (ctx.get("language") or "en-GB")
    translated = not lang.lower().startswith("en")
    if translated:
        why += " Language does not limit who can take it — live translation is switched on."
    return {"queue": queue, "skill": skill, "why": why, "language": lang, "translation": translated}


# ══════════════════════════════════════════════════════════════════════════════
#  THE DECISION
# ══════════════════════════════════════════════════════════════════════════════
def rationale(top, segment, decision, override):
    ups = [r for r in top if r["direction"] == "up"][:3]
    downs = [r for r in top if r["direction"] == "down"][:2]
    def names(rs):
        return ", ".join("%s (%s)" % (r["name"].lower(), r["value"]) for r in rs)
    if override:
        return "On paper, likely to buy: %s. %s" % (names(ups) or "a valuable account", override)
    if decision == "sell":
        return "Likely to buy. The strongest reasons: %s." % names(ups)
    if downs:
        return "Unlikely to buy. What counts against it: %s." % names(downs)
    return "Nothing about this customer or this request points to a sale."


def decide(profile, ctx, model=None, threshold=THRESHOLD, now=None, light=False):
    """The full treatment for one contact. `light` skips the explanatory fields — used
    when scoring thousands of simulated contacts."""
    model = model or BASELINE
    xs, reads = extract(profile, ctx)
    p = propensity(xs, model)
    seg, seg_why = segment_for(profile, ctx, xs)
    rails = guardrails(profile, ctx, seg, now)
    failed = [g for g in rails if not g["pass"]]

    wants_sell = p >= threshold and seg in SELL_SEGMENTS
    clears = p >= threshold
    decision = "sell" if (wants_sell and not failed) else "solve"

    override = None
    if clears and failed:
        g = failed[0]
        override = {
            "recovery": "Held back: there is an unresolved problem on this account. No offer is made, however likely the sale.",
            "consent": "Held back: this customer has opted out of offers.",
            "cooldown": "Held back: an offer was already made in the last %d days." % OFFER_COOLDOWN_DAYS,
            "suppression": "Held back: the account is on hold after a complaint.",
        }[g["id"]]

    offer = cat.match_offer(profile, ctx.get("intent"), seg) if decision == "sell" else None
    if light:
        return {"xs": xs, "propensity": p, "segment": seg, "decision": decision,
                "override": override, "held_by": failed[0]["id"] if (clears and failed) else None,
                "offer": offer, "failed": [g["id"] for g in failed]}

    top = contributions(xs, reads, model)
    return {
        "features": top,
        "vector": {k: round(v, 3) for k, v in xs.items()},
        "segment": seg,
        "segment_reason": seg_why,
        "propensity": round(p, 2),
        "propensity_raw": p,
        "threshold": threshold,
        "decision": decision,
        "override": override,
        "held_by": failed[0]["id"] if (clears and failed) else None,
        "intent_label": intent(ctx.get("intent"))["label"],
        "guardrails": rails,
        "rationale": rationale(top, seg, decision, override),
        "routing": route(profile, ctx, seg, decision, offer),
        "offer": offer,
        "model_version": model.get("version", "v1"),
    }
