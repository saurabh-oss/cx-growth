"""
FEEDBACK LOOP — outcomes retrain the model.

    outcome ─▶ disposition ─▶ attribution ─▶ reweighting ─▶ next contact

The Frontier runs a CHAMPION model. The feedback loop trains a CHALLENGER on what
actually happened to the contacts the champion routed, and scores both on a day
neither has seen. A person promotes the challenger — the loop never promotes itself.

Three design choices worth defending in the room:

1. CHAMPION / CHALLENGER, NOT ONLINE LEARNING. A model that reweights itself after every
   call cannot be audited and cannot be rolled back. This one changes when someone
   presses Promote, and the previous version is kept.

2. EXPLORATION. The champion only sees outcomes for contacts it chose to route, so left
   alone it can never learn it was wrong to ignore something. Two percent of
   below-threshold contacts are routed anyway to keep it honest.

3. GUARDRAILS ARE NOT LEARNED. Service recovery, consent and cooldown are rules in
   frontier_engine.py. No amount of training data can teach the model to sell into a
   complaint, because that decision is not the model's to make.

Model state is held in memory and resets to the baseline on restart, so a rehearsal can
never leave the demo in a surprising state.
"""
import copy, math, random, threading, time
from datetime import datetime, timezone

import frontier_engine as fe
import simulation as sim

TRAINING_DAYS = (-1, -2, -3)      # the challenger learns from these; both models are judged on day 0
EXPLORATION_WEIGHT_CAP = 8.0

_lock = threading.Lock()
_state = {
    "champion": None,        # the model the Frontier is scoring with
    "challenger": None,      # trained, evaluated, awaiting a decision
    "history": [],           # every version that has been champion
    "labelled": [],          # agent dispositions from handled contacts
    "threshold": fe.THRESHOLD,
}
_days = {}


def _baseline():
    m = copy.deepcopy(fe.BASELINE)
    m.update(version="v1", trained_on=None, created="baseline", note="Baseline weights — set by hand from domain judgement")
    return m


def champion():
    with _lock:
        if _state["champion"] is None:
            _state["champion"] = _baseline()
            _state["history"] = [{"version": "v1", "event": "Baseline deployed", "at": _now()}]
        return _state["champion"]


def threshold():
    return _state["threshold"]


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def day(offset=0, daily_contacts=9200):
    """Simulated days are expensive to build and immutable once built — cache them."""
    key = (offset, daily_contacts)
    if key not in _days:
        _days[key] = sim.Day(daily_contacts=daily_contacts, day_offset=offset)
    return _days[key]


# ══════════════════════════════════════════════════════════════════════════════
#  TRAINING
# ══════════════════════════════════════════════════════════════════════════════
def _examples(d, model, thr):
    """Labelled examples: every contact that was routed to sell or explored. The label is
    whether a real opportunity was found — the agent's wrap-up disposition."""
    d.score(model)
    idx = {k["id"]: k for k in d.contacts}
    out = []
    for r in d.decide(thr):
        if r["treated"]:
            k = idx[r["id"]]
            # Explored contacts stand in for the many like them that were not routed. The
            # weight is capped: forty-nine imaginary contacts per real one is too much to
            # hang on a single outcome.
            weight = min(1.0 / sim.EXPLORATION_RATE, EXPLORATION_WEIGHT_CAP) if r["explore"] else 1.0
            out.append(([k["xs"][f] for f in fe.FEATURE_IDS], 1.0 if r["opportunity"] else 0.0, weight))
    return out


def fit(examples, start, epochs=30, lr=0.06, l2=0.0004, seed=11):
    """Weighted logistic regression by stochastic gradient descent, warm-started from the
    champion and pulled gently back toward it — so the challenger is an adjustment of the
    model in production, not a stranger to it."""
    ids = fe.FEATURE_IDS
    n = len(ids)
    w = [start["weights"][k] for k in ids]
    b = start["bias"]
    w0, b0 = list(w), b
    rng = random.Random(seed)
    order = list(range(len(examples)))
    exp = math.exp
    for ep in range(epochs):
        rng.shuffle(order)
        step = lr / (1.0 + 0.25 * ep)
        for i in order:
            x, y, wt = examples[i]
            z = b
            for j in range(n):
                z += w[j] * x[j]
            p = 1.0 / (1.0 + exp(-z)) if z > -35 else 0.0
            g = (p - y) * wt * step
            b -= g + step * l2 * (b - b0)
            for j in range(n):
                w[j] -= g * x[j] + step * l2 * (w[j] - w0[j])
    return {"bias": round(b, 3), "weights": {k: round(v, 3) for k, v in zip(ids, w)}}


def evaluate(model, d, thr, volume=None):
    """Score a model on a day using ground truth for every scoreable, sell-leaning
    contact — something only a simulation can do, and the honest way to compare."""
    ids = fe.FEATURE_IDS
    d.score(champion())                          # feature vectors and truth are model-independent
    pairs, sell, found, revenue_pairs = [], 0, 0, []
    for k in d.contacts:
        if k["anonymous"] or k["segment"] not in fe.SELL_SEGMENTS or k["failed"]:
            continue
        p = fe.sigmoid(model["bias"] + sum(model["weights"][f] * k["xs"][f] for f in ids))
        y = k["u_opp"] < k["truth"]
        pairs.append((p, y))
        if p >= thr:
            sell += 1
            found += 1 if y else 0
    # The fair comparison between two models is at equal workload: give each the same
    # number of contacts to route and count the real opportunities it finds.
    ranked = sorted(pairs, key=lambda t: -t[0])
    volume = volume or sell
    at_volume = sum(1 for _, y in ranked[:volume] if y)
    brier = sum((p - (1.0 if y else 0.0)) ** 2 for p, y in pairs) / float(len(pairs) or 1)
    bands, cal = sim.calibration([(p, y) for p, y in pairs if p >= thr], bins=5, lo=min(thr, 0.95))
    total_opps = sum(1 for _, y in pairs if y)
    return {
        "auc": round(sim.auc(pairs) or 0, 3),
        "brier": round(brier, 4),
        "calibration_error": cal,
        "calibration": bands,
        "routed": sell,
        "opportunities_found": found,
        "precision": round(found / float(sell or 1), 3),
        "recall": round(found / float(total_opps or 1), 3),
        "no_opportunity": sell - found,
        "eligible": len(pairs),
        "volume": volume,
        "found_at_volume": at_volume,
    }


def train():
    """Train a challenger on yesterday, evaluate both models on today."""
    champ = champion()
    thr = threshold()
    t0 = time.time()
    test_day = day(0)
    examples = []
    for offset in TRAINING_DAYS:
        examples.extend(_examples(day(offset), champ, thr))
    for lab in _state["labelled"]:
        examples.append((lab["x"], lab["y"], 1.0))
    fitted = fit(examples, champ)
    n = int(champ["version"].lstrip("v")) + 1
    while any(h["version"] == "v%d" % n for h in _state["history"]):
        n += 1
    chall = {**fitted, "version": "v%d" % n, "created": _now(),
             "trained_on": {"examples": len(examples),
                            "routed": sum(1 for e in examples if e[2] == 1.0),
                            "explored": sum(1 for e in examples if e[2] > 1.0),
                            "agent_dispositions": len(_state["labelled"]),
                            "positives": int(sum(e[1] for e in examples))},
             "note": "Trained on %d simulated days of routed and explored contacts" % len(TRAINING_DAYS)}
    before = evaluate(champ, test_day, thr)
    after = evaluate(chall, test_day, thr, volume=before["routed"])
    moves = []
    for k in fe.FEATURE_IDS:
        a, b = champ["weights"][k], chall["weights"][k]
        moves.append({"id": k, "name": fe.FEATURE_NAME[k], "from": round(a, 2), "to": round(b, 2),
                      "delta": round(b - a, 2)})
    moves.sort(key=lambda m: -abs(m["delta"]))
    chall["evaluation"] = {"champion": before, "challenger": after, "holdout": "A simulated day neither model has seen",
                           "seconds": round(time.time() - t0, 2)}
    chall["moves"] = moves
    chall["verdict"] = _verdict(before, after)
    chall["demo_impact"] = demo_impact(chall, thr)
    with _lock:
        _state["challenger"] = chall
    return chall


def _verdict(before, after):
    better = after["auc"] > before["auc"] + 0.003 and after["brier"] <= before["brier"]
    return {
        "recommend": "promote" if better else "hold",
        "reason": ("Ranks contacts better and is no worse calibrated on unseen traffic."
                   if better else "No reliable improvement on unseen traffic — keep the champion."),
        "auc_gain": round(after["auc"] - before["auc"], 3),
        "volume": before["routed"],
        "extra_opportunities": after["found_at_volume"] - before["found_at_volume"],
        "extra_per_year": (after["found_at_volume"] - before["found_at_volume"]) * 365,
    }


def demo_impact(model, thr):
    """What promoting this model would do to the nine demo contacts. A presenter should
    know before pressing the button, not find out mid-demo."""
    import demo_profiles as dp
    out = []
    champ = champion()
    for sid, prof in dp.PROFILES.items():
        a = fe.decide(prof, dp.CONTEXTS[sid], champ, thr, light=True)
        b = fe.decide(prof, dp.CONTEXTS[sid], model, thr, light=True)
        out.append({"id": sid, "name": prof["person"]["name"]["firstName"],
                    "from": round(a["propensity"], 2), "to": round(b["propensity"], 2),
                    "decision_from": a["decision"], "decision_to": b["decision"],
                    "flips": a["decision"] != b["decision"]})
    return out


def promote():
    with _lock:
        c = _state["challenger"]
        if not c:
            return None
        _state["champion"] = {k: v for k, v in c.items()
                              if k not in ("evaluation", "moves", "verdict", "demo_impact")}
        _state["history"].append({"version": c["version"], "event": "Promoted by a person", "at": _now(),
                                  "auc_gain": c["verdict"]["auc_gain"]})
        _state["challenger"] = None
        return _state["champion"]


def reset():
    with _lock:
        _state["champion"] = _baseline()
        _state["challenger"] = None
        _state["labelled"] = []
        _state["threshold"] = fe.THRESHOLD
        _state["history"] = [{"version": "v1", "event": "Reset to baseline", "at": _now()}]
    return _state["champion"]


def record_disposition(xs, opportunity, contact_id=None, disposition=None):
    """An agent's wrap-up choice is a labelled training example."""
    with _lock:
        _state["labelled"] = [l for l in _state["labelled"] if l.get("contact_id") != contact_id]
        _state["labelled"].append({"x": [xs[f] for f in fe.FEATURE_IDS], "y": 1.0 if opportunity else 0.0,
                                   "contact_id": contact_id, "disposition": disposition, "at": _now()})
    return len(_state["labelled"])


def model_card():
    champ = champion()
    rows = []
    for k in fe.FEATURE_IDS:
        rows.append({"id": k, "name": fe.FEATURE_NAME[k], "weight": champ["weights"][k],
                     "direction": "up" if champ["weights"][k] >= 0 else "down"})
    rows.sort(key=lambda r: -abs(r["weight"]))
    ch = _state["challenger"]
    return {
        "champion": {"version": champ["version"], "created": champ.get("created"), "note": champ.get("note"),
                     "bias": champ["bias"], "weights": rows, "trained_on": champ.get("trained_on")},
        "challenger": ch,
        "history": list(_state["history"]),
        "labelled": len(_state["labelled"]),
        "threshold": threshold(),
        "exploration_rate": sim.EXPLORATION_RATE,
        "kind": "Logistic regression · %d background features" % len(fe.FEATURE_IDS),
    }
