"""
SIMULATED TRAFFIC — a synthetic population and one day of contacts.

The business case in scenarios.SCALE_MODEL is a set of assumptions. This module is the
check on them: it builds a population of synthetic customers, generates a day of
contacts from it, and runs every one through the same Frontier engine the demo uses.
The funnel, the segment mix, the calibration and the threshold curve on screen are
counted from that run — nothing here is typed in.

    population (6,000 customers) ─▶ 9,200 contacts ─▶ Frontier ─▶ outcomes ─▶ metrics

EVERYTHING HERE IS SYNTHETIC. There is no Acme data in it. The population mix is tuned
so the run lands near the business-case assumptions, which makes it a consistency check
and a working model of the mechanics — not evidence of what Acme's traffic will do.
That is what Phase 0 is for.

Outcomes come from a hidden "ground truth" that deliberately differs from the champion
model — it values third-party spend and commercial use more, and tenure less. That gap
is what the feedback loop has to find.
"""
import math, random
from datetime import datetime, timedelta, timezone

import catalogue as cat
import frontier_engine as fe
from cdp import profile_doc, full_name

SEED = 20260928
POPULATION = 6000
EXPLORATION_RATE = 0.02      # below-threshold contacts routed to sell anyway, so the model can learn what it is missing

FIRST = ["Olivia", "Noah", "Amara", "Liam", "Sofia", "Ethan", "Zara", "Lucas", "Maya", "Oscar", "Hana", "Leo",
         "Isla", "Arjun", "Freya", "Kofi", "Elif", "Mateo", "Niamh", "Yusuf", "Chloe", "Dev", "Ingrid", "Tariq",
         "Grace", "Hugo", "Anika", "Samuel", "Leila", "Callum", "Mei", "Andre", "Rosa", "Finn", "Nadia", "Jonas",
         "Imani", "Pablo", "Eva", "Rohan", "Clara", "Idris", "Beth", "Marco", "Tanvi", "Owen", "Salma", "Victor"]
LAST = ["Bennett", "Okafor", "Lindqvist", "Hughes", "Moreau", "Iyer", "Castillo", "Walsh", "Nakamura", "Petrov",
        "Adeyemi", "Fischer", "Rahman", "O'Connor", "Silva", "Kowalski", "Haddad", "Jensen", "Mbeki", "Rossi",
        "Chaudhry", "Dubois", "Ferreira", "Novak", "Osei", "Pereira", "Quinn", "Reyes", "Sharma", "Tanaka",
        "Ueda", "Varga", "Wright", "Yilmaz", "Zhou", "Abbasi", "Brandt", "Clarke", "Dlamini", "Eriksen"]

# share of the customer base on each plan
PLAN_MIX = [("EXPRESS_FREE", 0.23), ("EXPRESS_PREMIUM", 0.07), ("PHOTO_20GB", 0.15), ("PHOTO_1TB", 0.15),
            ("SINGLE_APP", 0.12), ("CC_ALL_APPS", 0.22), ("CC_TEAMS", 0.06)]

# The hidden truth the feedback loop is trying to recover.
TRUTH = {
    "bias": -2.30,
    "weights": {
        "capacity":   0.95, "recurring":  0.90, "licence":    1.40, "gates":      1.00,
        "headroom":   0.30, "trend":      0.90, "mismatch":   2.10, "engagement": 0.10,
        "commercial": 1.30, "thirdparty": 1.70, "gap":        1.25, "health":     1.00,
        "tenure":    -0.35, "value":      0.20, "intent":     1.45, "service":   -0.80,
        "declined":  -1.90,
    },
}
QUALIFY_GIVEN_OPPORTUNITY = 0.57     # agent surfaces and qualifies an opportunity that is really there
CONVERT = {"capacity": 0.30, "value": 0.27, "growth": 0.20, "explorer": 0.23}

# How fast each reason for contact is growing, per week. This is what gives the Voice of
# Customer agent something to find: themes that are moving, not just themes that are big.
WEEKLY_DRIFT = {"credits.exhausted": 0.30, "account.concurrent": 0.24, "install.error": 0.38,
                "feature.gated": 0.09, "billing.dispute": -0.14, "documents.sign": 0.18}

# Arrivals by hour of day, as a share of the daily total.
INTRADAY = [0.3, 0.2, 0.2, 0.2, 0.3, 0.6, 1.4, 3.0, 5.6, 7.8, 8.9, 9.1,
            8.4, 8.0, 8.2, 7.9, 7.2, 6.3, 5.1, 3.9, 2.8, 1.9, 1.1, 0.6]


def _pick(rng, pairs):
    r, acc = rng.random() * sum(w for _, w in pairs), 0.0
    for v, w in pairs:
        acc += w
        if r <= acc:
            return v
    return pairs[-1][0]


def _beta(rng, a, b, lo=0, hi=100):
    return int(round(lo + (hi - lo) * rng.betavariate(a, b)))


def _customer(rng, n):
    code = _pick(rng, PLAN_MIX)
    pl = cat.plan(code)
    first, last = rng.choice(FIRST), rng.choice(LAST)
    smb = code == "CC_TEAMS" or (code == "CC_ALL_APPS" and rng.random() < 0.05)
    seats = rng.choice([2, 3, 3, 4, 5, 6, 8, 10, 12]) if code == "CC_TEAMS" else 1
    tenure = max(1, int(rng.expovariate(1 / 26.0)))
    free = code == "EXPRESS_FREE"

    storage = _beta(rng, 1.6, 2.6)
    if rng.random() < (0.42 if code == "PHOTO_20GB" else 0.07):
        storage = rng.randint(92, 100)
    credits = _beta(rng, 1.4, 3.0)
    exhausted = 0
    if code in ("PHOTO_1TB", "PHOTO_20GB", "SINGLE_APP", "CC_ALL_APPS") and rng.random() < 0.13:
        credits, exhausted = 100, rng.choice([1, 2, 2, 3, 3])
    gates = 0
    if free:
        gates = rng.choice([0, 0, 1, 2, 3, 5, 8, 11, 14, 17, 21])
    elif code == "SINGLE_APP":
        gates = rng.choice([0, 0, 0, 1, 2, 4, 7, 9])
    ent = pl["apps_entitled"]
    used = ent if ent <= 2 else max(1, min(ent, int(rng.gammavariate(2.2, 2.0)) + 1))
    users = seats
    if pl["licence"] == "INDIVIDUAL" and code in ("CC_ALL_APPS", "SINGLE_APP") and rng.random() < (0.35 if smb else 0.012):
        users = rng.choice([2, 2, 3, 3, 4])
    commercial = rng.random() < (0.85 if smb else 0.24)
    assets = rng.choice([160, 190, 240, 300, 420]) if (code == "CC_TEAMS" and rng.random() < 0.14) else rng.randint(0, 90)
    brands = rng.choice([2, 3, 4, 5]) if assets >= 150 else 1
    health = _beta(rng, 5.2, 2.4, 20, 100)
    dup = rng.random() < 0.016
    open_cases = ["CASE-%05d" % rng.randint(10000, 99999)] if (dup or rng.random() < 0.03) else []
    repeat = bool(open_cases) and rng.random() < 0.72
    if open_cases:
        health = max(20, health - rng.randint(10, 35))

    return profile_doc(
        pid="c%05d" % n, first=first, last=last,
        email="%s.%s%d@example.com" % (first.lower(), last.lower().replace("'", ""), n),
        customer_type="Small Business" if smb else "Consumer",
        marketing_consent=rng.random() > 0.07,
        entitlement={"planCode": code, "planName": pl["name"], "licenceType": pl["licence"], "seats": seats,
                     "billingCycle": rng.choice(["Monthly", "Monthly", "Annual"]),
                     "annualValue": cat.annual(code, seats), "tenureMonths": tenure,
                     "cloudsOwned": ["Studio Cloud"] + (["Engage Cloud"] if (code == "CC_TEAMS" and rng.random() < 0.12) else [])},
        usage={"storageUsedPct": storage, "storageQuotaGb": pl["storage_gb"] * (seats if pl.get("per_seat") else 1),
               "appsUsed30d": used, "appsEntitled": ent,
               "generativeCreditsUsedPct": credits, "creditsExhaustedMonths": exhausted,
               "featureGateHits30d": gates, "contentCreated30d": rng.randint(2, 400),
               "assetsPerMonth": assets, "brandCount": brands,
               "concurrentDevices": max(users, rng.choice([1, 1, 2])), "distinctLocations": 2 if users > 1 else 1,
               "distinctUsers30d": users, "usageTrendPct": int(rng.gauss(8, 24))},
        service={"openCases": open_cases, "repeatContact7d": repeat, "duplicateChargeFlag": dup,
                 "lastContactDays": rng.randint(1, 600), "contacts90d": rng.choice([0, 0, 0, 1, 1, 2])},
        health={"score": health, "nps": max(0, min(10, int(round(health / 10.0 + rng.gauss(0, 1)))))},
        commercial={"offersDeclined12m": rng.choice([0, 0, 0, 0, 1, 1, 2, 3]),
                    "commercialUse": ("Business use" if commercial else None),
                    "thirdPartySpend": ("Competing subscription" if rng.random() < (0.30 if commercial else 0.10) else None),
                    "lastOfferDate": None})


def _intent_weights(p):
    """Why this customer is calling. Their state drives it: a full drive produces a
    storage call, an open case produces a billing call."""
    t = p["_icxdemo"]
    e, u, s = t["entitlement"], t["usage"], t["service"]
    code = e["planCode"]
    w = {"account.access": 2.9, "account.profile": 0.8, "billing.payment": 1.1, "billing.invoice": 0.8,
         "install.error": 1.4, "app.crash": 1.1, "howto.feature": 4.2, "plan.compare": 0.9,
         "billing.cancel": 0.9 if e["annualValue"] > 0 else 0.0}
    if u["storageUsedPct"] >= 92:
        w["storage.limit"] = 3.5
    if u["creditsExhaustedMonths"] >= 1:
        w["credits.exhausted"] = 3.1
    if u["distinctUsers30d"] > e["seats"] or (e["licenceType"] == "INDIVIDUAL" and u["distinctUsers30d"] >= 2):
        w["account.concurrent"] = 5.0
    if u["featureGateHits30d"] >= 5:
        w["feature.gated"] = 3.3
    elif code == "EXPRESS_FREE":
        w["feature.gated"] = 3.2
    if u["assetsPerMonth"] >= 150:
        w["assets.versioning"] = 3.0
    if t["commercial"].get("commercialUse") and code in ("SINGLE_APP", "PHOTO_1TB", "CC_ALL_APPS"):
        w["documents.sign"] = 0.9
    if u["appsEntitled"] >= 10 and u["appsUsed30d"] <= 3:
        w["billing.cancel"] = 2.6
    if s["duplicateChargeFlag"]:
        w["billing.dispute"] = 9.0
    elif s["openCaseCount"]:
        w["refund.status"] = 4.0
        w["billing.dispute"] = 2.0
    else:
        w["billing.dispute"] = 0.25
    return list(w.items())


def _call_weight(p):
    """Customers with something wrong call more."""
    t = p["_icxdemo"]
    u, s = t["usage"], t["service"]
    w = 1.0
    if s["openCaseCount"]:
        w += 2.0
    if u["storageUsedPct"] >= 92 or u["creditsExhaustedMonths"] >= 1:
        w += 1.5
    if u["featureGateHits30d"] >= 5:
        w += 0.9
    if u["distinctUsers30d"] > t["entitlement"]["seats"]:
        w += 1.6
    return w


_population = {}


def population(seed=SEED, size=POPULATION):
    """The customer base. Built once: the same people call on every simulated day."""
    key = (seed, size)
    if key not in _population:
        prng = random.Random(seed)
        customers = [_customer(prng, n) for n in range(size)]
        cum, acc = [], 0.0
        for c in customers:
            acc += _call_weight(c)
            cum.append(acc)
        _population[key] = (customers, cum, [_intent_weights(c) for c in customers])
    return _population[key]


class Day:
    """One simulated day. Scored once per model; re-decided cheaply per threshold."""

    def __init__(self, daily_contacts=9200, seed=SEED, population_size=POPULATION, day_offset=0):
        rng = random.Random(seed + day_offset * 7919)
        self.offset = day_offset
        self.customers, cum, intents = population(seed, population_size)
        index = list(range(len(self.customers)))
        hours = list(range(24))
        # Reasons for contact drift week to week. Looking back, a rising theme was smaller.
        drift = {k: max(0.2, 1.0 + rate * day_offset / 7.0) for k, rate in WEEKLY_DRIFT.items()}
        self.contacts = []
        for n in range(daily_contacts):
            anonymous = rng.random() < 0.02              # no identity resolved — nothing to score
            ci = rng.choices(index, cum_weights=cum)[0]
            c = self.customers[ci]
            reasons = [(k, w * drift.get(k, 1.0)) for k, w in intents[ci]]
            iid = _pick(rng, reasons) if not anonymous else _pick(
                rng, [("account.access", 5), ("install.error", 2), ("howto.feature", 2), ("plan.compare", 1)])
            hr = rng.choices(hours, INTRADAY)[0]
            sec = hr * 3600 + rng.randint(0, 3599)
            self.contacts.append({
                "n": n, "customer": c, "anonymous": anonymous, "intent": iid, "second": sec,
                "channel": "chat" if (fe.intent(iid)["queue"] == "express" or rng.random() < 0.16) else "voice",
                "u_opp": rng.random(), "u_qual": rng.random(), "u_conv": rng.random(),
                "u_explore": rng.random(), "noise": rng.gauss(0, 0.45),
            })
        self.contacts.sort(key=lambda k: k["second"])
        for i, k in enumerate(self.contacts):
            k["id"] = "sim-%05d" % i
        self._scored_for = None

    # ── scoring ──────────────────────────────────────────────────────────────
    def score(self, model):
        """Feature vector, propensity, segment and guardrails for every contact."""
        key = (model.get("version"), model["bias"], tuple(sorted(model["weights"].items())))
        if self._scored_for == key:
            return
        for k in self.contacts:
            if k["anonymous"]:
                k.update(xs=None, p=None, segment="access", failed=[], truth=0.0)
                continue
            ctx = {"intent": k["intent"], "language": "en-GB"}
            xs, _ = fe.extract(k["customer"], ctx)
            seg, _ = fe.segment_for(k["customer"], ctx, xs)
            rails = fe.guardrails(k["customer"], ctx, seg)
            k["xs"], k["segment"] = xs, seg
            k["p"] = fe.propensity(xs, model)
            k["failed"] = [g["id"] for g in rails if not g["pass"]]
            z = TRUTH["bias"] + sum(TRUTH["weights"][f] * xs[f] for f in fe.FEATURE_IDS) + k["noise"]
            k["truth"] = fe.sigmoid(z) if seg != "recovery" else fe.sigmoid(z) * 0.15
        self._scored_for = key

    def decide(self, threshold):
        """Apply a threshold to the scored day. Returns per-contact outcomes."""
        out = []
        for k in self.contacts:
            if k["anonymous"]:
                out.append({**_blank(k), "decision": "solve", "scored": False})
                continue
            clears = k["p"] >= threshold
            sell_seg = k["segment"] in fe.SELL_SEGMENTS
            blocked = bool(k["failed"])
            sell = clears and sell_seg and not blocked
            explore = (not sell) and sell_seg and not blocked and k["u_explore"] < EXPLORATION_RATE
            treated = sell or explore
            opp = treated and k["u_opp"] < k["truth"]
            qual = opp and k["u_qual"] < QUALIFY_GIVEN_OPPORTUNITY
            offer = cat.match_offer(k["customer"], k["intent"], k["segment"]) if qual else None
            if qual and not offer:
                qual = False                             # an opportunity with nothing to offer is not a lead
            rate = CONVERT.get(k["segment"], 0.25) * (0.45 if (offer and offer["value"] >= 1000) else 1.0)
            conv = qual and k["u_conv"] < rate
            out.append({
                "id": k["id"], "second": k["second"], "scored": True, "segment": k["segment"], "p": k["p"],
                "intent": k["intent"], "channel": k["channel"],
                "decision": "sell" if sell else "solve", "explore": explore,
                "override": clears and blocked, "blocked_by": k["failed"][0] if (clears and blocked) else None,
                "sell_leaning": sell_seg, "treated": treated,
                "opportunity": bool(opp), "qualified": bool(qual), "converted": bool(conv),
                "value": offer["value"] if conv and offer else 0,
                "offer_type": offer["type"] if offer else None,
                "would_have": k["u_opp"] < k["truth"],   # ground truth, visible only to the simulation
            })
        return out


def _blank(k):
    return {"id": k["id"], "second": k["second"], "segment": "access", "p": None, "intent": k["intent"],
            "channel": k["channel"], "explore": False, "override": False, "blocked_by": None,
            "sell_leaning": False, "treated": False, "opportunity": False, "qualified": False,
            "converted": False, "value": 0, "offer_type": None, "would_have": False}


# ══════════════════════════════════════════════════════════════════════════════
#  METRICS
# ══════════════════════════════════════════════════════════════════════════════
def auc(pairs):
    """Area under the ROC curve from (score, label) pairs — rank-based, ties averaged."""
    pairs = sorted(pairs, key=lambda t: t[0])
    n_pos = sum(1 for _, y in pairs if y)
    n_neg = len(pairs) - n_pos
    if not n_pos or not n_neg:
        return None
    rank_sum, i = 0.0, 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        avg = (i + 1 + j) / 2.0
        rank_sum += avg * sum(1 for t in pairs[i:j] if t[1])
        i = j
    return (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def calibration(pairs, bins=5, lo=0.0):
    """Predicted versus realised, in equal-width bands of predicted propensity."""
    if not pairs:
        return [], None
    width = (1.0 - lo) / bins
    out, err, n_all = [], 0.0, 0
    for b in range(bins):
        a, z = lo + b * width, lo + (b + 1) * width
        sel = [(p, y) for p, y in pairs if (a <= p < z) or (b == bins - 1 and p == 1.0)]
        if not sel:
            continue
        pred = sum(p for p, _ in sel) / len(sel)
        real = sum(1 for _, y in sel if y) / float(len(sel))
        out.append({"band": "%.2f–%.2f" % (a, z), "n": len(sel), "predicted": round(pred, 3), "realised": round(real, 3)})
        err += abs(pred - real) * len(sel)
        n_all += len(sel)
    return out, (round(err / n_all, 3) if n_all else None)


def summarise(day, model, threshold, scale_model=None):
    day.score(model)
    rows = day.decide(threshold)
    n = len(rows)
    scored = [r for r in rows if r["scored"]]
    leaning = [r for r in scored if r["sell_leaning"]]
    sell = [r for r in rows if r["decision"] == "sell"]
    qual = [r for r in sell if r["qualified"]]
    conv = [r for r in sell if r["converted"]]
    overrides = [r for r in scored if r["override"]]
    recovery = [r for r in scored if r["segment"] == "recovery"]
    revenue = sum(r["value"] for r in conv)

    seg_counts = {}
    for r in rows:
        seg_counts[r["segment"]] = seg_counts.get(r["segment"], 0) + 1

    treated_pairs = [(r["p"], r["opportunity"]) for r in rows if r["treated"]]
    sell_pairs = [(r["p"], r["opportunity"]) for r in sell]
    bands, cal_err = calibration(sell_pairs, bins=5, lo=min(threshold, 0.95))
    no_opp = sum(1 for r in sell if not r["opportunity"])
    missed = sum(1 for r in scored if r["decision"] == "solve" and r["sell_leaning"] and not r["override"] and r["would_have"])

    out = {
        "threshold": threshold,
        "model_version": model.get("version", "v1"),
        "contacts": n,
        "funnel": [
            # Worded for someone who has never seen a propensity model.
            {"stage": "Customers got in touch", "value": n, "group": "filter", "key": "received",
             "note": "Calls and chats, one simulated day"},
            {"stage": "We recognised who was calling", "value": len(scored), "group": "filter", "key": "scored",
             "note": "%d%% had a customer record to read" % round(100.0 * len(scored) / n)},
            {"stage": "Might welcome an offer", "value": len(leaning), "group": "decide", "key": "leaning",
             "note": "Near a limit, comparing plans, growing, or on a free plan"},
            {"stage": "Worth a sales conversation", "value": len(sell), "group": "decide", "key": "sell",
             "note": "Likely enough to buy, and nothing says hold back"},
            {"stage": "Real opportunity confirmed", "value": len(qual), "group": "opportunity", "key": "qualified",
             "note": "The agent heard it in the conversation"},
            {"stage": "Sale made", "value": len(conv), "group": "opportunity", "key": "converted",
             "note": "Offer accepted"},
        ],
        "rates": {
            "scored": round(len(scored) / float(n), 3),
            "sell_leaning": round(len(leaning) / float(n), 3),
            "triage": round(len(sell) / float(n), 3),
            "capture": round(len(qual) / float(len(sell) or 1), 3),
            "conversion": round(len(conv) / float(len(qual) or 1), 3),
            "avg_value": round(revenue / float(len(conv) or 1)),
        },
        "segments": {k: {"count": v, "share": round(v / float(n), 3)} for k, v in seg_counts.items()},
        "revenue_day": revenue,
        "revenue_year": revenue * 365,
        "guardrails": {
            "overrides": len(overrides),
            "by_rule": _count(overrides, "blocked_by"),
            "recovery_contacts": len(recovery),
            "recovery_offers_made": sum(1 for r in recovery if r["decision"] == "sell"),
        },
        "quality": {
            "auc": round(auc(treated_pairs) or 0, 3),
            "precision": round(1 - no_opp / float(len(sell) or 1), 3),
            "no_opportunity_rate": round(no_opp / float(len(sell) or 1), 3),
            "calibration_error": cal_err,
            "calibration": bands,
            "missed_opportunities": missed,
            "exploration_contacts": sum(1 for r in rows if r["explore"]),
        },
        "offer_mix": _count(conv, "offer_type"),
    }
    if scale_model:
        out["reconcile"] = [
            {"rate": "Routed to sell", "assumed": scale_model["triage_rate"], "simulated": out["rates"]["triage"]},
            {"rate": "Qualified, of routed", "assumed": scale_model["capture_rate"], "simulated": out["rates"]["capture"]},
            {"rate": "Converted, of qualified", "assumed": scale_model["conversion_rate"], "simulated": out["rates"]["conversion"]},
            {"rate": "Value per conversion", "assumed": scale_model["avg_value"], "simulated": out["rates"]["avg_value"], "money": True},
        ]
    return out


def _count(rows, key):
    out = {}
    for r in rows:
        if r.get(key):
            out[r[key]] = out.get(r[key], 0) + 1
    return out


def sweep(day, model, cost_per_contact=5.90, thresholds=None):
    """What moving the threshold buys and what it costs."""
    day.score(model)
    out = []
    for t in (thresholds or [x / 100.0 for x in range(30, 91, 5)]):
        rows = day.decide(t)
        sell = [r for r in rows if r["decision"] == "sell"]
        conv = [r for r in sell if r["converted"]]
        no_opp = sum(1 for r in sell if not r["opportunity"])
        out.append({
            "threshold": t, "sell_treated": len(sell),
            "share": round(len(sell) / float(len(rows)), 3),
            "qualified": sum(1 for r in sell if r["qualified"]),
            "converted": len(conv),
            "revenue_day": sum(r["value"] for r in conv),
            "no_opportunity": no_opp,
            "precision": round(1 - no_opp / float(len(sell) or 1), 3),
        })
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  LIVE FEED — the simulated day replayed against the wall clock
# ══════════════════════════════════════════════════════════════════════════════
def feed(day, model, threshold, now=None, limit=14):
    """Contacts that have 'arrived' by this time of day, newest first, and the running
    totals. At 14:30 the feed shows everything the simulated day produced up to 14:30."""
    day.score(model)
    now = now or datetime.now()
    sec = now.hour * 3600 + now.minute * 60 + now.second
    rows = day.decide(threshold)
    idx = {k["id"]: k for k in day.contacts}
    seen = [r for r in rows if r["second"] <= sec]
    recent = seen[-limit:][::-1]
    items = []
    for r in recent:
        k = idx[r["id"]]
        c = k["customer"]
        i = fe.intent(r["intent"])
        smb = c["_icxdemo"]["customerType"] == "Small Business"
        items.append({
            "id": r["id"], "time": "%02d:%02d:%02d" % (r["second"] // 3600, r["second"] % 3600 // 60, r["second"] % 60),
            "age": sec - r["second"],
            "customer": "Unidentified caller" if k["anonymous"] else full_name(c),
            "plan": "—" if k["anonymous"] else c["_icxdemo"]["entitlement"]["planName"],
            "intent": i["label"], "channel": r["channel"], "segment": r["segment"],
            "propensity": None if r["p"] is None else round(r["p"], 2),
            "decision": r["decision"], "override": r["override"], "blocked_by": r["blocked_by"],
            "explore": r["explore"],
            "queue": fe.QUEUES["smb"] if (smb and not k["anonymous"]) else fe.QUEUES[i["queue"]],
        })
    sell = [r for r in seen if r["decision"] == "sell"]
    return {
        "clock": "%02d:%02d" % (now.hour, now.minute),
        "items": items,
        "so_far": {
            "contacts": len(seen), "of_day": len(rows),
            "sell": len(sell), "solve": len(seen) - len(sell),
            "overrides": sum(1 for r in seen if r["override"]),
            "qualified": sum(1 for r in sell if r["qualified"]),
            "converted": sum(1 for r in sell if r["converted"]),
            "revenue": sum(r["value"] for r in sell if r["converted"]),
        },
        "per_minute": round(sum(1 for r in seen if sec - r["second"] <= 600) / 10.0, 1),
    }


def queue_metrics(day, model, threshold, base, now=None):
    """Queue table for the agent workspace, moved by the simulated arrivals of the last
    fifteen minutes. Staffing and service level stay as configured."""
    day.score(model)
    now = now or datetime.now()
    sec = now.hour * 3600 + now.minute * 60 + now.second
    rows = day.decide(threshold)
    idx = {k["id"]: k for k in day.contacts}
    recent = {}
    for r in rows:
        if 0 <= sec - r["second"] <= 900:
            k = idx[r["id"]]
            smb = (not k["anonymous"]) and k["customer"]["_icxdemo"]["customerType"] == "Small Business"
            q = fe.QUEUES["smb"] if smb else fe.QUEUES[fe.intent(r["intent"])["queue"]]
            recent[q] = recent.get(q, 0) + 1
    out = []
    for q in base:
        arrivals = recent.get(q["queue"], 0)
        waiting = max(0, int(round(arrivals * 0.22 + (100 - q["sla"]) * 0.18)))
        longest = int(waiting * 60 * 0.45 / max(1, q["agents"] / 4.0)) + (100 - q["sla"]) * 3
        out.append({**q, "in_queue": waiting, "arrivals_15m": arrivals,
                    "longest_wait": "%02d:%02d" % (longest // 60, longest % 60)})
    return out
