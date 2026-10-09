"""
PRODUCT ADVISORY — the plan catalogue and the offer matcher.

This is the Acme Product Advisory Agent's working memory: what plans exist, what they
cost, which tier sits above which, and the rules that turn a customer's actual usage
into one specific recommendation with a computed value.

Nothing here is looked up from a script. An offer's value is arithmetic on the price
list — Photography 20GB to Photography 1TB is $9.99/mo to $19.99/mo, so the incremental
ARR is $120 — which is why the same matcher serves the nine demo contacts, the simulated
traffic and a live free-form contact alike.

PRICES ARE ILLUSTRATIVE. They are set to be plausible for a consumer subscription
business and must be replaced with a real price book before any real use.
"""

CREATIVE, DOCUMENT, EXPERIENCE = "Studio Cloud", "Docs Cloud", "Engage Cloud"

# tier: position on the upgrade ladder inside a family. headroom is derived from it.
PLANS = {
    "EXPRESS_FREE":    {"name": "Acme Express (Free)",          "cloud": CREATIVE, "family": "express",
                        "monthly": 0.00,  "tier": 0, "licence": "INDIVIDUAL", "storage_gb": 5,
                        "apps": ["Acme Express"], "apps_entitled": 1},
    "EXPRESS_PREMIUM": {"name": "Acme Express Premium",         "cloud": CREATIVE, "family": "express",
                        "monthly": 9.99,  "tier": 1, "licence": "INDIVIDUAL", "storage_gb": 100,
                        "apps": ["Acme Express", "Acme Fonts"], "apps_entitled": 1},
    "PHOTO_20GB":      {"name": "Photography 20GB",              "cloud": CREATIVE, "family": "creative",
                        "monthly": 9.99,  "tier": 1, "licence": "INDIVIDUAL", "storage_gb": 20,
                        "apps": ["LightVault", "PhotoForge"], "apps_entitled": 2},
    "PHOTO_1TB":       {"name": "Photography 1TB",               "cloud": CREATIVE, "family": "creative",
                        "monthly": 19.99, "tier": 2, "licence": "INDIVIDUAL", "storage_gb": 1000,
                        "apps": ["LightVault", "PhotoForge"], "apps_entitled": 2},
    "SINGLE_APP":      {"name": "Single App",                    "cloud": CREATIVE, "family": "creative",
                        "monthly": 22.99, "tier": 2, "licence": "INDIVIDUAL", "storage_gb": 100,
                        "apps": ["One Studio Cloud app"], "apps_entitled": 1},
    "CC_ALL_APPS":     {"name": "Studio Cloud All Apps",       "cloud": CREATIVE, "family": "creative",
                        "monthly": 59.99, "tier": 3, "licence": "INDIVIDUAL", "storage_gb": 100,
                        "apps": ["PhotoForge", "VectorForge", "PageForge", "ClipForge Pro", "+ 16 more"],
                        "apps_entitled": 20},
    "CC_TEAMS":        {"name": "Studio Cloud for teams",      "cloud": CREATIVE, "family": "creative",
                        "monthly": 89.99, "tier": 4, "licence": "TEAMS", "storage_gb": 1000,
                        "per_seat": True,
                        "apps": ["All Apps", "Admin Console", "Shared libraries"], "apps_entitled": 20},
    "DOCS_PRO":     {"name": "DocuForge Pro",                   "cloud": DOCUMENT, "family": "document",
                        "monthly": 19.99, "tier": 1, "licence": "INDIVIDUAL", "storage_gb": 100,
                        "apps": ["DocuForge Pro", "DocuForge Sign (e-signatures)"], "apps_entitled": 1},
    "STORAGE_ADDON":   {"name": "Cloud storage add-on 1TB",      "cloud": CREATIVE, "family": "addon",
                        "monthly": 9.99,  "tier": 1, "licence": "INDIVIDUAL", "storage_gb": 1000,
                        "apps": ["+1TB cloud storage"], "apps_entitled": 0},
    "CREDITS_ADDON":   {"name": "Generative credits add-on",     "cloud": CREATIVE, "family": "addon",
                        "monthly": 4.99,  "tier": 1, "licence": "INDIVIDUAL", "storage_gb": 0,
                        "apps": ["Additional monthly generative credits"], "apps_entitled": 0},
    # Engage Cloud is priced by quote. The figure is an indicative entry point used for sizing.
    "VAULT_ASSETS":      {"name": "ContentVault Assets",     "cloud": EXPERIENCE, "family": "experience",
                        "monthly": 300.00, "tier": 1, "licence": "ORG", "quote_based": True,
                        "apps": ["Governed asset library", "Versioning", "Brand portal"], "apps_entitled": 1},
    "SUITE_ANALYTICS": {"name": "Acme Analytics",               "cloud": EXPERIENCE, "family": "experience",
                        "monthly": 0.00,  "tier": 2, "licence": "ORG", "quote_based": True,
                        "apps": ["Creative and campaign performance"], "apps_entitled": 1},
}

TOP_CONSUMER_TIER = 3          # All Apps is the ceiling for an individual


def plan(code):
    return PLANS.get(code) or PLANS["PHOTO_1TB"]


def annual(code, seats=1):
    p = plan(code)
    return round(p["monthly"] * 12 * (seats if p.get("per_seat") else 1), 2)


def headroom(code):
    """How much room there is to grow inside the customer's own product family — 0 to 1."""
    p = plan(code)
    if p["family"] == "express":
        return 1.0 if p["tier"] == 0 else 0.5
    if p["family"] == "creative":
        return max(0.0, min(1.0, (TOP_CONSUMER_TIER - p["tier"]) / 2.0))
    return 0.0


def headroom_read(code):
    h = headroom(code)
    if plan(code)["family"] == "express" and h == 1.0:
        return "Free tier — never converted"
    if h >= 1.0:
        return "Entry tier — two tiers above"
    if h >= 0.5:
        return "One tier above"
    return "Top tier — no upgrade path"


def money(v):
    return "${:,.0f}".format(round(v))


def _offer(kind, from_code, to, value, value_note, action, why, seats_from=1, note=None, trial=False):
    fp = plan(from_code)
    crosses = any(plan(t["code"])["cloud"] != fp["cloud"] for t in to)
    return {
        "type": kind,
        "value": round(value),
        "estimated_value": money(value),
        "value_note": value_note,
        "recommended_action": action,
        "why": why,
        "trial": trial,
        "offer": {
            "from": {"product": fp["name"] + (" · Individual" if fp["licence"] == "INDIVIDUAL"
                                               and fp["tier"] >= 3 and any(plan(t["code"])["licence"] == "TEAMS" for t in to) else ""),
                     "cloud": fp["cloud"], "code": from_code,
                     "annual": annual(from_code, seats_from)},
            "to": [{"product": plan(t["code"])["name"] + (" × %d" % t["seats"] if t.get("seats", 1) > 1 else ""),
                    "cloud": plan(t["code"])["cloud"], "code": t["code"],
                    "annual": annual(t["code"], t.get("seats", 1)),
                    **({"phase": t["phase"]} if t.get("phase") else {})} for t in to],
            "crosses_cloud": crosses,
            "note": note or "",
        },
    }


def match_offer(profile, intent_id=None, segment=None):
    """One recommendation, or None. Rules run in priority order and the first match wins —
    an agent presented with three offers presents none of them well.

    Returns None for any contact in Service Recovery: there is no offer to match while a
    failure is unresolved."""
    t = profile.get("_cxdemo", {})
    e, u, cm = t.get("entitlement", {}), t.get("usage", {}), t.get("commercial", {})
    code = e.get("planCode", "PHOTO_1TB")
    p = plan(code)
    seats = int(e.get("seats", 1) or 1)
    cur = float(e.get("annualValue") or annual(code, seats))

    if segment == "recovery":
        return None

    # 1 — Retention: cancelling a plan they mostly do not use.
    if intent_id == "billing.cancel":
        used, ent = u.get("appsUsed30d", 0), p["apps_entitled"]
        if code == "CC_ALL_APPS" and 0 < used <= 3:
            keep = annual("PHOTO_1TB")
            return _offer("Retention", code, [{"code": "PHOTO_1TB"}], keep, "kept, every year",
                          "Switch from All Apps to Photography plan with 1TB — retains the apps actually "
                          "in use at $19.99/mo instead of losing the account entirely.",
                          "Using %d of %d apps. The objection is the price of what is unused, not the tools." % (used, ent),
                          note="A plan change that retains, not a discount that erodes.")
        if code == "PHOTO_1TB" and u.get("storageUsedPct", 0) < 15:
            keep = annual("PHOTO_20GB")
            return _offer("Retention", code, [{"code": "PHOTO_20GB"}], keep, "kept, every year",
                          "Move to Photography 20GB — same apps at $9.99/mo, matched to the storage in use.",
                          "Using under 15% of 1TB. Storage is what is being overpaid for.")
        return None

    # 2 — Licence model: one individual licence, several people.
    users = int(u.get("distinctUsers30d", 1) or 1)
    if p["licence"] == "INDIVIDUAL" and users >= 2 and p["family"] == "creative":
        to_val = annual("CC_TEAMS", users)
        return _offer("Upsell", code, [{"code": "CC_TEAMS", "seats": users}], to_val - cur, "more, every year",
                      "Move from one individual licence to %d Studio Cloud for teams licences — Admin Console, "
                      "per-seat management, 1TB per user, shared libraries and company invoicing." % users,
                      "%d people working from one individual licence. The licence model is the constraint." % users,
                      note="From one licence to %d, inside Studio Cloud." % users)

    # 3 — Cross-cloud: the problem is asset governance, not creative tooling.
    if (u.get("assetsPerMonth", 0) >= 150 and u.get("brandCount", 1) >= 2
            and EXPERIENCE not in e.get("cloudsOwned", [])):
        return _offer("Cross-Sell", code,
                      [{"code": "VAULT_ASSETS"}, {"code": "SUITE_ANALYTICS", "phase": "follow-on"}],
                      annual("VAULT_ASSETS"), "more, every year",
                      "Acme ContentVault Assets for governed, versioned asset management across %d brands — "
                      "with Acme Analytics positioned as the follow-on for creative performance." % u.get("brandCount", 2),
                      "%d assets a month across %d brands with no governance layer." % (u.get("assetsPerMonth", 0), u.get("brandCount", 2)),
                      seats_from=seats,
                      note="A Studio Cloud customer with an Engage Cloud need. A sales team organised by "
                           "product line would not have made this offer.")

    # 4 — Cross-cloud: documents and signatures.
    if intent_id == "documents.sign" and DOCUMENT not in e.get("cloudsOwned", []):
        return _offer("Cross-Sell", code, [{"code": "DOCS_PRO"}], annual("DOCS_PRO"), "more, every year",
                      "Add DocuForge Pro at $19.99/mo — editable PDFs and legally binding e-signatures, "
                      "alongside the Studio Cloud plan already in place.",
                      "Sending contracts for signature with no Docs Cloud product owned.",
                      note="Studio Cloud customer, Docs Cloud need.")

    # 5 — Free to paid.
    if code == "EXPRESS_FREE" and u.get("featureGateHits30d", 0) >= 5:
        return _offer("New Sale", code, [{"code": "EXPRESS_PREMIUM"}], annual("EXPRESS_PREMIUM"), "new, every year",
                      "Acme Express Premium at $9.99/mo — unlocks background removal, premium templates and "
                      "Acme Fonts. Start on the free trial to de-risk the decision.",
                      "%d premium feature gates hit in 30 days." % u.get("featureGateHits30d", 0), trial=True)

    # 6 — Generative credits exhausted, with the adjacent capability bought elsewhere.
    if code in ("PHOTO_1TB", "PHOTO_20GB", "SINGLE_APP") and u.get("creditsExhaustedMonths", 0) >= 2:
        extra = " and replaces the separate video subscription" if cm.get("thirdPartySpend") else ""
        return _offer("Upsell", code, [{"code": "CC_ALL_APPS"}], annual("CC_ALL_APPS") - cur, "more, every year",
                      "Upgrade %s → Studio Cloud All Apps at $59.99/mo — higher generative allocation plus "
                      "ClipForge Pro%s." % (p["name"], extra),
                      "Generative credits exhausted %d months running." % u.get("creditsExhaustedMonths", 0))

    # 7 — Storage ceiling.
    if code == "PHOTO_20GB" and u.get("storageUsedPct", 0) >= 90:
        return _offer("Upsell", code, [{"code": "PHOTO_1TB"}], annual("PHOTO_1TB") - cur, "more, every year",
                      "Upgrade to Photography plan with 1TB storage — $19.99/mo, activates immediately and "
                      "restores sync today.",
                      "Storage at %d%% of 20GB." % u.get("storageUsedPct", 0))

    # 8 — Single app user working across several apps.
    if code == "SINGLE_APP" and u.get("featureGateHits30d", 0) >= 6:
        return _offer("Upsell", code, [{"code": "CC_ALL_APPS"}], annual("CC_ALL_APPS") - cur, "more, every year",
                      "Move from Single App to Studio Cloud All Apps at $59.99/mo — every app, one subscription.",
                      "Repeatedly opening apps outside the single-app entitlement.")

    # 9 — Plan question from someone already at the edge of their plan.
    if intent_id == "plan.compare":
        if code == "PHOTO_20GB" and u.get("storageUsedPct", 0) >= 60:
            return _offer("Upsell", code, [{"code": "PHOTO_1TB"}], annual("PHOTO_1TB") - cur, "more, every year",
                          "Photography plan with 1TB — $19.99/mo, the same apps with fifty times the storage.",
                          "Asking about plans with storage at %d%%." % u.get("storageUsedPct", 0))
        if code == "EXPRESS_FREE" and u.get("featureGateHits30d", 0) >= 1:
            return _offer("New Sale", code, [{"code": "EXPRESS_PREMIUM"}], annual("EXPRESS_PREMIUM"), "new, every year",
                          "Acme Express Premium at $9.99/mo, starting on the free trial.",
                          "Asking about plans after meeting premium feature gates.", trial=True)

    # 10 — Storage ceiling on any other paid plan.
    if p["monthly"] > 0 and p["family"] in ("creative", "express") and u.get("storageUsedPct", 0) >= 92:
        return _offer("Upsell", code, [{"code": "STORAGE_ADDON"}], annual("STORAGE_ADDON"), "more, every year",
                      "Add 1TB of cloud storage at $9.99/mo — keeps the current plan and removes the ceiling.",
                      "Storage at %d%% of %dGB." % (u.get("storageUsedPct", 0), p["storage_gb"]))

    # 11 — Credits exhausted on a plan with nowhere higher to go.
    if p["monthly"] > 0 and u.get("creditsExhaustedMonths", 0) >= 1:
        return _offer("Upsell", code, [{"code": "CREDITS_ADDON"}], annual("CREDITS_ADDON"), "more, every year",
                      "Add the generative credits pack at $4.99/mo — tops up the monthly allocation.",
                      "Generative credits exhausted %d month%s running." % (
                          u.get("creditsExhaustedMonths", 0), "" if u.get("creditsExhaustedMonths", 0) == 1 else "s"))

    # 12 — Express Premium creator outgrowing the tool.
    if code == "EXPRESS_PREMIUM" and u.get("contentCreated30d", 0) >= 60 and cm.get("commercialUse"):
        return _offer("Upsell", code, [{"code": "PHOTO_1TB"}], annual("PHOTO_1TB"), "more, every year",
                      "Add the Photography plan with 1TB at $19.99/mo — PhotoForge and LightVault for the "
                      "product photography Express cannot do.",
                      "Commercial content volume beyond what Express is built for.")
    return None


def catalogue_view():
    """Grouped by cloud so a cross-cloud recommendation is visibly a boundary crossing."""
    out = {}
    for code, p in PLANS.items():
        out.setdefault(p["cloud"], []).append({
            "code": code, "name": p["name"], "monthly": p["monthly"],
            "annual": annual(code), "quote_based": bool(p.get("quote_based")),
            "per_seat": bool(p.get("per_seat"))})
    return [{"cloud": k, "plans": v} for k, v in out.items()]
