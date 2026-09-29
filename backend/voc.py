"""
VOICE OF CUSTOMER AGENT — what customers are calling about, and which of it is moving.

A contact centre knows its top ten contact reasons. What it rarely knows is which of
them changed this week, which are commercial, and which should never have been a
contact at all. This agent rolls every treated contact into themes and ranks them by
what leadership can do about them:

    FIX      a rising service theme — something upstream broke
    PRODUCT  a rising commercial theme — customers are outgrowing something
    DEFLECT  a stable transactional theme — answerable without an agent
    WATCH    everything else

Volumes and week-on-week movement are counted from simulated traffic (today against the
same day last week). The verbatims are illustrative of each theme; in production they
are drawn from Contact Lens transcripts.
"""
import frontier_engine as fe
import knowledge as kb

VERBATIMS = {
    "storage.limit":      ["“It keeps telling me my storage is full.”", "“My phone has stopped syncing photos.”"],
    "credits.exhausted":  ["“I'm out of generative credits again.”", "“This is the third month running.”"],
    "account.concurrent": ["“My colleague keeps getting signed out.”", "“It says the account is being used somewhere else.”"],
    "feature.gated":      ["“It says that's a premium feature.”", "“I keep running into locked templates.”"],
    "assets.versioning":  ["“Everyone just guesses which one is approved.”", "“We published last season's packaging.”"],
    "documents.sign":     ["“My clients have to sign the contracts.”", "“I print them, they sign and scan them back.”"],
    "howto.feature":      ["“How do I do this in LightVault?”", "“Is there a way to batch this?”"],
    "plan.compare":       ["“What's the difference between the plans?”", "“Is it worth moving up?”"],
    "billing.cancel":     ["“I can't justify it any more.”", "“I'm paying for apps I've never opened.”"],
    "billing.dispute":    ["“I've been charged twice this month.”", "“I was told it would be refunded.”"],
    "refund.status":      ["“Where is my refund?”", "“Nothing has happened in a week.”"],
    "account.access":     ["“It says my password is incorrect.”", "“I can't sign in.”"],
    "account.profile":    ["“I changed my email with my provider.”", "“I need to update my details.”"],
    "billing.payment":    ["“My card has expired.”", "“I need to change how I pay.”"],
    "billing.invoice":    ["“My accountant needs a proper invoice.”", "“Where do I download a receipt?”"],
    "install.error":      ["“The update fails every time.”", "“It's been stuck installing since yesterday.”"],
    "app.crash":          ["“PhotoForge crashes when I open a large file.”", "“It's running very slowly.”"],
}
# Share of answerable contacts a self-service agent actually contains. An assumption, and a
# deliberately modest one — Phase 0 measures the real figure.
CONTAINMENT = 0.35
CONTAINMENT_PCT = int(CONTAINMENT * 100)

OPENING_SENTIMENT = {"recovery": 0.16, "value": 0.29, "capacity": 0.37, "access": 0.46, "explorer": 0.41, "growth": 0.52}


def _tally(day, rows):
    out = {}
    for r in rows:
        t = out.setdefault(r["intent"], {"n": 0, "sell": 0, "qualified": 0, "converted": 0, "revenue": 0, "override": 0})
        t["n"] += 1
        t["sell"] += 1 if r["decision"] == "sell" else 0
        t["qualified"] += 1 if r["qualified"] else 0
        t["converted"] += 1 if r["converted"] else 0
        t["revenue"] += r["value"]
        t["override"] += 1 if r["override"] else 0
    return out


def themes(today, last_week, model, threshold, cost_per_contact=5.90):
    today.score(model)
    last_week.score(model)
    now, then = _tally(today, today.decide(threshold)), _tally(last_week, last_week.decide(threshold))
    total = float(sum(t["n"] for t in now.values()) or 1)
    deflectable = set(kb.deflectable_intents())
    out = []
    for iid, t in now.items():
        i = fe.intent(iid)
        prev = then.get(iid, {}).get("n", 0)
        wow = (t["n"] - prev) / float(prev) if prev else 0.0
        sell_share = t["sell"] / float(t["n"])
        commercial = i["family"] in fe.SELL_SEGMENTS and sell_share >= 0.25
        rising = wow >= 0.12 and t["n"] >= 60
        if rising and not commercial and i["family"] in ("access", "recovery"):
            action, tone = "fix", "red"
            if i["family"] == "recovery":
                insight = ("Up %d%% on last week. These are customers chasing a promise already made. The process "
                           "that made the promise is the thing to fix, not the queue that hears about it." % round(wow * 100))
            else:
                insight = ("Up %d%% on last week and it is a fault, not a question. Something upstream changed — "
                           "this is an engineering ticket before it is a staffing problem." % round(wow * 100))
        elif rising and commercial:
            action, tone = "product", "green"
            insight = ("Up %d%% on last week, and %d%% of these contacts are commercial. Customers are outgrowing "
                       "something — a proactive in-product offer would reach them before they call." % (
                           round(wow * 100), round(sell_share * 100)))
        elif iid in deflectable and t["n"] >= 150:
            action, tone = "deflect", "accent"
            insight = ("Answerable from a knowledge article. At %d%% containment that is %s contacts a day that "
                       "need no agent — about %s a year." % (
                           CONTAINMENT_PCT, "{:,}".format(int(t["n"] * CONTAINMENT)),
                           _money(t["n"] * CONTAINMENT * cost_per_contact * 365)))
        elif wow <= -0.10 and t["n"] >= 60:
            action, tone = "watch", "neutral"
            insight = "Down %d%% on last week. Whatever was changed is working." % round(-wow * 100)
        elif commercial:
            action, tone = "watch", "neutral"
            insight = "Steady and commercial — %d%% routed to sell, %s won today." % (
                round(sell_share * 100), _money(t["revenue"]))
        else:
            action, tone = "watch", "neutral"
            insight = "Steady. No action indicated."
        out.append({
            "intent": iid, "theme": i["label"], "family": i["family"], "volume": t["n"],
            "share": round(t["n"] / total, 3), "last_week": prev, "wow": round(wow, 3),
            "sentiment": OPENING_SENTIMENT.get(i["family"], 0.45),
            "sell_share": round(sell_share, 3), "qualified": t["qualified"], "converted": t["converted"],
            "revenue": t["revenue"], "suppressed": t["override"],
            "action": action, "tone": tone, "insight": insight,
            "verbatims": VERBATIMS.get(iid, []),
            "deflectable": iid in deflectable,
        })
    rank = {"fix": 0, "product": 1, "deflect": 2, "watch": 3}
    out.sort(key=lambda r: (rank[r["action"]], -abs(r["wow"]) if r["action"] in ("fix", "product") else -r["volume"]))

    defl = [r for r in out if r["deflectable"]]
    defl_n = sum(r["volume"] for r in defl)
    return {
        "themes": out,
        "headline": [r for r in out if r["action"] in ("fix", "product")][:3],
        "contacts": int(total),
        "window": "Today against the same day last week · simulated traffic",
        "deflection": {
            "intents": [r["theme"] for r in defl],
            "contacts_day": defl_n,
            "share": round(defl_n / total, 3),
            "containment": CONTAINMENT,
            "contained_day": int(defl_n * CONTAINMENT),
            "saving_year": int(defl_n * CONTAINMENT * cost_per_contact * 365),
            "cost_per_contact": cost_per_contact,
        },
        "agent": "Voice of Customer Agent",
    }


def _money(v):
    v = float(v)
    if v >= 1000000:
        return "$%.1fM" % (v / 1000000.0)
    if v >= 10000:
        return "$%dK" % round(v / 1000.0)
    return "${:,.0f}".format(v)
