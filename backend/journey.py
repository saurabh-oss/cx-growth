"""
AFTER THE CONTACT — write-back, journey and case.

A lead captured in a contact centre usually dies there: it sits in a wrap-up note nobody
reads. This module is what closes the loop in the target architecture:

    wrap-up ─▶ events written to the customer profile        (Real-Time CDP)
            ─▶ profile updated: last offer, holds, open cases
            ─▶ journey triggered with the next best action   (Journey Composer)
            ─▶ case raised where follow-up is owed           (ServiceNow)

Journey Composer and ServiceNow are STAND-INS here — the journey and the case are
composed in-process and shown, not sent. What is real is the write-back: the events land
on the customer platform as ODM, the profile changes, and the next contact from the same
customer is scored against the changed profile. next_contact() shows exactly that.
"""
import copy, hashlib
from datetime import datetime, timedelta, timezone

import frontier_engine as fe
from cdp import event_doc, iso, TENANT, set_path


def _ref(prefix, *parts):
    return "%s-%s" % (prefix, str(int(hashlib.md5("|".join(parts).encode()).hexdigest()[:7], 16) % 90000 + 10000))


def _journey(offer, treatment, first, language):
    """The steps a journey would run. Timing and channel follow the kind of offer."""
    es = (language or "").lower().startswith("es")
    if treatment.get("segment") == "recovery":
        return {"name": "Service recovery follow-up", "trigger": "case.resolved", "steps": [
            {"when": "Now", "channel": "Email", "title": "Written confirmation of the refund",
             "preview": "%s, your refund has been processed. Reference and expected date inside." % first},
            {"when": "Day 3", "channel": "Email", "title": "Refund landed — check-in",
             "preview": "Has the refund reached your account? Reply to this email and it comes straight to the case owner."},
            {"when": "Day 14", "channel": "—", "title": "Commercial hold lifts",
             "preview": "Profile becomes eligible for offers again. Nothing is sent."},
        ]}
    if not offer:
        return {"name": "No journey", "trigger": None, "steps": []}
    to = offer["offer"]["to"][0]["product"]
    if offer.get("trial"):
        steps = [
            {"when": "Now", "channel": "In-app", "title": "%s trial started" % to,
             "preview": "Your trial is live. The three tools you asked about are unlocked."},
            {"when": "Day 3", "channel": "Email", "title": "Remove a background in three steps",
             "preview": "A walkthrough of the feature that brought you to us, on one of your own designs."},
            {"when": "Day 12", "channel": "Email", "title": "Your trial so far",
             "preview": "What you made with the premium tools — and what happens when the trial ends."},
        ]
    elif offer["offer"]["crosses_cloud"] and offer["value"] >= 1000:
        steps = [
            {"when": "Now", "channel": "Email", "title": "Introduction to your %s specialist" % offer["offer"]["to"][0]["cloud"],
             "preview": "%s, as discussed — your specialist has your asset volume and brand structure already." % first},
            {"when": "Within 48h", "channel": "Call", "title": "Specialist call",
             "preview": "Booked with the context from this contact. The customer does not repeat themselves."},
            {"when": "Day 10", "channel": "Email", "title": "Sizing and proposal",
             "preview": "Scoped to the volume captured on the support call."},
        ]
    elif offer["type"] == "Retention":
        steps = [
            {"when": "Now", "channel": "Email", "title": "Your plan has changed",
             "preview": "%s, you are now on %s. Nothing was lost — files, presets and history are all in place." % (first, to)},
            {"when": "Day 30", "channel": "Email", "title": "Is the plan the right fit?",
             "preview": "A one-question check-in. Win-back campaigns are suppressed for this account."},
        ]
    else:
        steps = [
            {"when": "Now", "channel": "Email", "title": ("Su plan se ha actualizado" if es else "Your plan is upgraded"),
             "preview": (("%s, %s ya está activo en su cuenta." % (first, to)) if es
                         else "%s, %s is active on your account from today." % (first, to))},
            {"when": "Day 2", "channel": "In-app", "title": ("Primeros pasos" if es else "Getting the most from it"),
             "preview": ("Guía rápida en español para su primer documento." if es
                         else "Tips chosen from how you actually use the product.")},
            {"when": "Day 30", "channel": "Email", "title": ("¿Todo bien?" if es else "Check-in"),
             "preview": ("Una pregunta para confirmar que el plan le encaja." if es
                         else "Headroom check — is the new tier the right size?")},
        ]
    return {"name": "%s onboarding" % to, "trigger": "commerce.offerAccepted", "steps": steps}


def plan(scenario_id, profile, ctx, treatment, outcome):
    """Everything that happens after wrap-up. Pure — writes nothing.

    outcome: {disposition, lead (summary dict or None), talk_seconds, signals, quality}"""
    pid = profile["_id"]
    first = profile["person"]["name"]["firstName"]
    now = datetime.now(timezone.utc)
    lead = outcome.get("lead")
    offer = treatment.get("offer") if lead else None
    disposition = outcome.get("disposition") or ("Upgrade accepted" if lead else "Issue resolved")
    recovery = treatment.get("segment") == "recovery"
    accepted = bool(lead) and disposition in ("Upgrade accepted", "Referred to sales", "Callback scheduled")
    channel = ctx.get("channel", "voice")
    contact_id = outcome.get("contact_id") or scenario_id

    events = [
        event_doc("contactCentre.treatmentDecided", pid, {
            "contactId": contact_id, "intent": ctx.get("intent"), "segment": treatment["segment"],
            "propensity": treatment["propensity"], "decision": treatment["decision"].upper(),
            "override": bool(treatment.get("override")), "modelVersion": treatment.get("model_version"),
            "queue": treatment["routing"]["queue"]}, channel=channel,
            timestamp=iso(now - timedelta(seconds=outcome.get("talk_seconds", 60) + 40))),
        event_doc("contactCentre.interaction", pid, {
            "contactId": contact_id, "intent": ctx.get("intent"), "outcome": disposition,
            "talkSeconds": outcome.get("talk_seconds"), "signalsDetected": outcome.get("signals", 0),
            "qualityScore": (outcome.get("quality") or {}).get("overall"),
            "language": ctx.get("language")}, channel=channel, timestamp=iso(now - timedelta(seconds=20))),
    ]
    changes = {TENANT + ".service.lastContactDays": 0}
    case = None

    if lead and offer:
        events.append(event_doc("commerce.offerPresented", pid, {
            "contactId": contact_id, "offer": offer["offer"]["to"][0]["product"], "type": offer["type"],
            "value": offer["value"], "crossesCloud": offer["offer"]["crosses_cloud"]},
            channel=channel, timestamp=iso(now - timedelta(seconds=12))))
        events.append(event_doc("leadOperation.newLead" if not accepted or offer["value"] >= 1000 else "commerce.offerAccepted",
                                pid, {"contactId": contact_id, "offer": offer["offer"]["to"][0]["product"],
                                      "value": offer["value"], "disposition": disposition},
                                channel=channel, timestamp=iso(now - timedelta(seconds=6))))
        changes[TENANT + ".commercial.lastOfferDate"] = iso(now)
        if disposition == "Offer declined":
            changes[TENANT + ".commercial.offersDeclined12m"] = \
                int(profile[TENANT]["commercial"].get("offersDeclined12m", 0)) + 1
        if offer["offer"]["crosses_cloud"] and offer["value"] >= 1000:
            case = {"system": "ServiceNow", "number": _ref("OPP", pid, "handoff"), "type": "Specialist referral",
                    "priority": "P3", "sla": "Contact within 48 hours",
                    "assigned_to": "%s specialist team" % offer["offer"]["to"][0]["cloud"],
                    "summary": "%s — %s" % (offer["offer"]["to"][0]["product"], offer["why"])}

    if recovery:
        until = now + timedelta(days=fe.RECOVERY_SUPPRESSION_DAYS)
        old = (profile[TENANT]["service"].get("openCases") or [None])[0]
        events.append(event_doc("case.resolved", pid, {
            "caseId": old or _ref("CASE", pid), "resolution": "Refund processed in-call", "contactId": contact_id},
            channel=channel, timestamp=iso(now - timedelta(seconds=8))))
        events.append(event_doc("commerce.holdApplied", pid, {
            "reason": "service_recovery", "until": iso(until), "days": fe.RECOVERY_SUPPRESSION_DAYS},
            timestamp=iso(now - timedelta(seconds=4))))
        changes.update({
            TENANT + ".commercial.suppressedUntil": iso(until),
            TENANT + ".service.openCases": [], TENANT + ".service.openCaseCount": 0,
            TENANT + ".service.duplicateChargeFlag": False, TENANT + ".service.repeatContact7d": False,
        })
        case = {"system": "ServiceNow", "number": old or _ref("CASE", pid), "type": "Duplicate charge",
                "priority": "P2", "sla": "Refund confirmed in 5 working days",
                "assigned_to": "Billing · Tier 2", "status": "Resolved — monitoring",
                "summary": "Refund processed in-call. Follow-up owed on day 3."}

    return {
        "events": events,
        "profile_changes": [{"path": k, "value": v} for k, v in changes.items()],
        "journey": _journey(offer, treatment, first, ctx.get("language")),
        "case": case,
        "changes": changes,
    }


def next_contact(profile, changes, ctx, model, threshold):
    """Score the same customer again, as they would be scored if they called tomorrow.
    This is the guardrails demonstrated rather than described: an offer made today means
    the cooldown blocks one tomorrow."""
    after = copy.deepcopy(profile)
    for path, value in changes.items():
        set_path(after, path, value)
    d = fe.decide(after, ctx, model, threshold)
    failed = [g for g in d["guardrails"] if not g["pass"]]
    return {
        "decision": d["decision"], "propensity": d["propensity"], "segment": d["segment"],
        "override": d["override"], "blocked_by": failed[0]["block"] if failed else None,
        "blocked_id": failed[0]["id"] if failed else None,
        "detail": failed[0]["detail"] if failed else (
            "An offer could be made" if d["decision"] == "sell"
            else "Not likely enough to buy — handled as a service call"),
        "guardrails": d["guardrails"],
    }
