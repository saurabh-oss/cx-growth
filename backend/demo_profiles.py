"""
The nine demo customers as ODM profiles, with the history that led to today's contact.

scenarios.py holds the conversation. This holds the customer. The Frontier scores the
profile defined here, so the segment, propensity and offer on screen are computed from
these attributes — edit one and the decision moves.

Event timestamps are relative to start-up, so the timeline always reads as recent.
"""
from cdp import profile_doc, event_doc, ago


def _p(**kw):
    return profile_doc(**kw)


PROFILES = {
    "aisha-storage-full": _p(
        pid="aisha-kapoor", first="Aisha", last="Kapoor", email="aisha.kapoor@example.com", phone="+44 7700 900141",
        entitlement={"planCode": "PHOTO_20GB", "planName": "Photography 20GB", "licenceType": "INDIVIDUAL",
                     "seats": 1, "billingCycle": "Monthly", "annualValue": 119.88, "renewalDate": "12 Sep",
                     "tenureMonths": 36, "products": ["LightVault", "PhotoForge"]},
        usage={"storageUsedPct": 100, "storageQuotaGb": 20, "appsUsed30d": 2, "appsEntitled": 2,
               "generativeCreditsUsedPct": 41, "creditsExhaustedMonths": 0, "featureGateHits30d": 0,
               "contentCreated30d": 1840, "concurrentDevices": 2, "distinctLocations": 1, "distinctUsers30d": 1,
               "usageTrendPct": 62},
        service={"lastContactDays": 412, "contacts90d": 0},
        health={"score": 88, "nps": 9},
        commercial={"offersDeclined12m": 0}),

    "tom-cancel-save": _p(
        pid="tom-whitfield", first="Tom", last="Whitfield", email="tom.whitfield@example.com", phone="+44 7700 900187",
        entitlement={"planCode": "CC_ALL_APPS", "planName": "Studio Cloud All Apps", "licenceType": "INDIVIDUAL",
                     "seats": 1, "billingCycle": "Monthly", "annualValue": 719.88, "renewalDate": "04 Sep",
                     "tenureMonths": 14, "products": ["PhotoForge", "LightVault", "+ 18 unused apps"]},
        usage={"storageUsedPct": 22, "storageQuotaGb": 100, "appsUsed30d": 2, "appsEntitled": 20,
               "generativeCreditsUsedPct": 12, "creditsExhaustedMonths": 0, "featureGateHits30d": 0,
               "contentCreated30d": 64, "concurrentDevices": 1, "distinctLocations": 1, "distinctUsers30d": 1,
               "usageTrendPct": 4},
        service={"lastContactDays": 203, "contacts90d": 0},
        health={"score": 54, "nps": 6},
        commercial={"offersDeclined12m": 0}),

    "nina-express-premium": _p(
        pid="nina-alvarez", first="Nina", last="Alvarez", email="nina.alvarez@example.com",
        entitlement={"planCode": "EXPRESS_FREE", "planName": "Acme Express (Free)", "licenceType": "INDIVIDUAL",
                     "seats": 1, "billingCycle": "—", "annualValue": 0.0, "renewalDate": "—",
                     "tenureMonths": 5, "products": ["Acme Express Free"]},
        usage={"storageUsedPct": 48, "storageQuotaGb": 5, "appsUsed30d": 1, "appsEntitled": 1,
               "generativeCreditsUsedPct": 60, "creditsExhaustedMonths": 0, "featureGateHits30d": 17,
               "contentCreated30d": 34, "concurrentDevices": 1, "distinctLocations": 1, "distinctUsers30d": 1,
               "usageTrendPct": 30},
        service={"lastContactDays": 999, "contacts90d": 0},
        health={"score": 71, "nps": 8},
        commercial={"offersDeclined12m": 0, "commercialUse": "Marketplace seller"}),

    "marcus-generative-credits": _p(
        pid="marcus-bell", first="Marcus", last="Bell", email="marcus.bell@example.com", phone="+44 7700 900112",
        entitlement={"planCode": "PHOTO_1TB", "planName": "Photography 1TB", "licenceType": "INDIVIDUAL",
                     "seats": 1, "billingCycle": "Monthly", "annualValue": 239.88, "renewalDate": "21 Sep",
                     "tenureMonths": 24, "products": ["PhotoForge", "LightVault"]},
        usage={"storageUsedPct": 46, "storageQuotaGb": 1000, "appsUsed30d": 2, "appsEntitled": 2,
               "generativeCreditsUsedPct": 100, "creditsExhaustedMonths": 3, "featureGateHits30d": 3,
               "contentCreated30d": 310, "concurrentDevices": 2, "distinctLocations": 1, "distinctUsers30d": 1,
               "usageTrendPct": 38},
        service={"lastContactDays": 61, "contacts90d": 1},
        health={"score": 82, "nps": 8},
        commercial={"offersDeclined12m": 2, "commercialUse": "Monetised channel",
                    "thirdPartySpend": "Separate video subscription"}),

    "priya-individual-to-teams": _p(
        pid="priya-raman", first="Priya", last="Raman", email="priya@ramanstudio.example", phone="+44 7700 900163",
        customer_type="Small Business",
        entitlement={"planCode": "CC_ALL_APPS", "planName": "All Apps · Individual", "licenceType": "INDIVIDUAL",
                     "seats": 1, "billingCycle": "Annual", "annualValue": 719.88, "renewalDate": "18 Oct",
                     "tenureMonths": 48, "products": ["PhotoForge", "VectorForge", "PageForge"]},
        usage={"storageUsedPct": 71, "storageQuotaGb": 100, "appsUsed30d": 6, "appsEntitled": 20,
               "generativeCreditsUsedPct": 55, "creditsExhaustedMonths": 0, "featureGateHits30d": 0,
               "contentCreated30d": 420, "concurrentDevices": 3, "distinctLocations": 2, "distinctUsers30d": 3,
               "usageTrendPct": 25},
        service={"lastContactDays": 340, "contacts90d": 0},
        health={"score": 81, "nps": 8},
        commercial={"offersDeclined12m": 0, "commercialUse": "Design studio", "invoiceRequested": True}),

    "ravi-creative-to-experience": _p(
        pid="ravi-deshpande", first="Ravi", last="Deshpande", email="ravi@fourbrands.example", phone="+44 7700 900155",
        customer_type="Small Business",
        entitlement={"planCode": "CC_TEAMS", "planName": "Studio Cloud for teams · 8 seats", "licenceType": "TEAMS",
                     "seats": 8, "billingCycle": "Annual", "annualValue": 8639.04, "renewalDate": "30 Jan",
                     "tenureMonths": 24, "products": ["PhotoForge", "VectorForge", "Acme Express", "ClipForge Pro"]},
        usage={"storageUsedPct": 58, "storageQuotaGb": 8000, "appsUsed30d": 7, "appsEntitled": 20,
               "generativeCreditsUsedPct": 47, "creditsExhaustedMonths": 0, "featureGateHits30d": 0,
               "contentCreated30d": 240, "assetsPerMonth": 240, "brandCount": 4,
               "concurrentDevices": 8, "distinctLocations": 2, "distinctUsers30d": 8, "usageTrendPct": 18},
        service={"lastContactDays": 120, "contacts90d": 0},
        health={"score": 86, "nps": 9},
        commercial={"offersDeclined12m": 0, "commercialUse": "E-commerce, four brands"}),

    "lucia-sign-contracts": _p(
        pid="lucia-fernandez", first="Lucía", last="Fernández", email="lucia.fernandez@example.es",
        phone="+34 600 900 174", country="ES", language="es-ES",
        entitlement={"planCode": "SINGLE_APP", "planName": "VectorForge · Single App", "licenceType": "INDIVIDUAL",
                     "seats": 1, "billingCycle": "Monthly", "annualValue": 275.88, "renewalDate": "09 Oct",
                     "tenureMonths": 18, "products": ["VectorForge"]},
        usage={"storageUsedPct": 34, "storageQuotaGb": 100, "appsUsed30d": 1, "appsEntitled": 1,
               "generativeCreditsUsedPct": 38, "creditsExhaustedMonths": 0, "featureGateHits30d": 2,
               "contentCreated30d": 96, "concurrentDevices": 1, "distinctLocations": 1, "distinctUsers30d": 1,
               "usageTrendPct": 28},
        service={"lastContactDays": 290, "contacts90d": 0},
        health={"score": 84, "nps": 8},
        commercial={"offersDeclined12m": 0, "commercialUse": "Freelance designer"}),

    "robert-signin": _p(
        pid="robert-nkemelu", first="Robert", last="Nkemelu", email="robert.nkemelu@example.com", phone="+44 7700 900129",
        entitlement={"planCode": "PHOTO_1TB", "planName": "Photography 1TB", "licenceType": "INDIVIDUAL",
                     "seats": 1, "billingCycle": "Annual", "annualValue": 239.88, "renewalDate": "14 Mar",
                     "tenureMonths": 60, "products": ["LightVault", "PhotoForge"]},
        usage={"storageUsedPct": 38, "storageQuotaGb": 1000, "appsUsed30d": 2, "appsEntitled": 2,
               "generativeCreditsUsedPct": 9, "creditsExhaustedMonths": 0, "featureGateHits30d": 0,
               "contentCreated30d": 140, "concurrentDevices": 1, "distinctLocations": 1, "distinctUsers30d": 1,
               "usageTrendPct": 0, "signInFailures24h": 6},
        service={"lastContactDays": 480, "contacts90d": 0},
        health={"score": 90, "nps": 9},
        commercial={"offersDeclined12m": 2}),

    "elena-double-charge": _p(
        pid="elena-marsh", first="Elena", last="Marsh", email="elena.marsh@example.com", phone="+44 7700 900176",
        entitlement={"planCode": "CC_ALL_APPS", "planName": "Studio Cloud All Apps", "licenceType": "INDIVIDUAL",
                     "seats": 1, "billingCycle": "Annual", "annualValue": 719.88, "renewalDate": "30 Nov",
                     "tenureMonths": 72, "products": ["PhotoForge", "VectorForge", "PageForge"]},
        usage={"storageUsedPct": 100, "storageQuotaGb": 100, "appsUsed30d": 9, "appsEntitled": 20,
               "generativeCreditsUsedPct": 100, "creditsExhaustedMonths": 2, "featureGateHits30d": 0,
               "contentCreated30d": 510, "concurrentDevices": 2, "distinctLocations": 1, "distinctUsers30d": 1,
               "usageTrendPct": 48},
        service={"openCases": ["CASE-40217"], "repeatContact7d": True, "duplicateChargeFlag": True,
                 "lastContactDays": 7, "contacts90d": 1},
        health={"score": 41, "nps": 3},
        commercial={"offersDeclined12m": 0, "commercialUse": "Professional designer"}),
}

PROFILE_ID = {sid: p["_id"] for sid, p in PROFILES.items()}


# What the IVR captured on each contact — the context the Frontier scores alongside the profile.
CONTEXTS = {
    "aisha-storage-full":          {"intent": "storage.limit",      "auth": "VERIFIED", "channel": "voice", "language": "en-GB",
                                    "identity": "Authenticated — registered number", "duration": "0:22"},
    "tom-cancel-save":             {"intent": "billing.cancel",     "auth": "VERIFIED", "channel": "voice", "language": "en-GB",
                                    "identity": "Authenticated — registered number", "duration": "0:31"},
    "nina-express-premium":        {"intent": "feature.gated",      "auth": "VERIFIED", "channel": "chat",  "language": "en-GB",
                                    "identity": "Authenticated — signed-in session", "duration": "0:14"},
    "marcus-generative-credits":   {"intent": "credits.exhausted",  "auth": "VERIFIED", "channel": "voice", "language": "en-GB",
                                    "identity": "Authenticated — registered number", "duration": "0:19"},
    "priya-individual-to-teams":   {"intent": "account.concurrent", "auth": "VERIFIED", "channel": "voice", "language": "en-GB",
                                    "identity": "Authenticated — registered number", "duration": "0:29"},
    "ravi-creative-to-experience": {"intent": "assets.versioning",  "auth": "VERIFIED", "channel": "voice", "language": "en-GB",
                                    "identity": "Authenticated — registered number", "duration": "0:17"},
    "lucia-sign-contracts":          {"intent": "documents.sign",     "auth": "VERIFIED", "channel": "voice", "language": "es-ES",
                                    "identity": "Authenticated — registered number", "duration": "0:24"},
    "robert-signin":               {"intent": "account.access",     "auth": "CHALLENGE_FAILED", "channel": "voice", "language": "en-GB",
                                    "identity": "Challenge failed — verified by agent", "duration": "0:48"},
    "elena-double-charge":         {"intent": "billing.dispute",    "auth": "VERIFIED", "channel": "voice", "language": "en-GB",
                                    "identity": "Authenticated — registered number", "duration": "0:26"},
}


def _e(sid, event_type, payload, **when):
    return event_doc(event_type, PROFILE_ID[sid], payload, timestamp=ago(**when), source="history")


def history(sid):
    """The events on the profile before today's contact. Rebuilt on each call so the
    timestamps stay relative to now."""
    H = {
        "aisha-storage-full": [
            ("productUsage.syncFailed",        {"reason": "quota_exceeded", "device": "iPhone 15", "app": "LightVault"}, dict(minutes=26)),
            ("productUsage.storageThreshold",  {"storageUsedPct": 100, "quotaGb": 20}, dict(hours=3)),
            ("productUsage.storageThreshold",  {"storageUsedPct": 95, "quotaGb": 20}, dict(days=5)),
            ("productUsage.storageThreshold",  {"storageUsedPct": 80, "quotaGb": 20}, dict(days=21)),
            ("productUsage.monthlySummary",    {"photosAdded": 1840, "trendPct": 62}, dict(days=27)),
            ("contactCentre.interaction",      {"intent": "install.error", "outcome": "Resolved", "channel": "voice"}, dict(days=412)),
        ],
        "tom-cancel-save": [
            ("web.webinteraction.linkClicks",  {"link": "Cancel plan", "page": "/account/plans"}, dict(minutes=41)),
            ("web.webpagedetails.pageViews",   {"page": "/account/plans/cancel"}, dict(minutes=43)),
            ("web.webpagedetails.pageViews",   {"page": "/studiocloud/plans", "section": "Photography"}, dict(days=2)),
            ("productUsage.monthlySummary",    {"appsUsed": 2, "appsEntitled": 20, "apps": ["PhotoForge", "LightVault"]}, dict(days=6)),
            ("billing.chargePosted",           {"amount": 59.99, "currency": "GBP", "plan": "CC_ALL_APPS"}, dict(days=24)),
        ],
        "nina-express-premium": [
            ("productUsage.featureGateHit",    {"feature": "Remove background", "app": "Acme Express"}, dict(minutes=9)),
            ("productUsage.featureGateHit",    {"feature": "Premium template", "app": "Acme Express"}, dict(days=1)),
            ("productUsage.featureGateHit",    {"feature": "Acme Fonts", "app": "Acme Express"}, dict(days=4)),
            ("productUsage.monthlySummary",    {"designsCreated": 34, "gateHits": 17}, dict(days=5)),
            ("web.webpagedetails.pageViews",   {"page": "/express/pricing"}, dict(days=9)),
        ],
        "marcus-generative-credits": [
            ("productUsage.creditsExhausted",  {"month": "this month", "allocation": "standard"}, dict(hours=2)),
            ("productUsage.exportTarget",      {"target": "Third-party video editor", "exports": 22}, dict(days=8)),
            ("productUsage.creditsExhausted",  {"month": "last month", "allocation": "standard"}, dict(days=33)),
            ("commerce.offerDeclined",         {"offer": "Acme Stock add-on", "channel": "email"}, dict(days=58)),
            ("contactCentre.interaction",      {"intent": "credits.exhausted", "outcome": "Reset date explained", "channel": "chat"}, dict(days=61)),
            ("productUsage.creditsExhausted",  {"month": "two months ago", "allocation": "standard"}, dict(days=64)),
        ],
        "priya-individual-to-teams": [
            ("productUsage.concurrentSignInBlocked", {"devices": 3, "locations": 2, "app": "VectorForge"}, dict(minutes=34)),
            ("productUsage.concurrentSignInBlocked", {"devices": 3, "locations": 2, "app": "PageForge"}, dict(days=3)),
            ("productUsage.concurrentSignInBlocked", {"devices": 2, "locations": 2, "app": "PhotoForge"}, dict(days=6)),
            ("billing.invoiceRequested",       {"type": "Company invoice", "requestedBy": "Accountant"}, dict(days=12)),
            ("productUsage.monthlySummary",    {"distinctUsers": 3, "devices": 3}, dict(days=14)),
        ],
        "ravi-creative-to-experience": [
            ("productUsage.libraryVersionConflict", {"library": "Spring campaign", "staleAssetsUsed": 6}, dict(days=8)),
            ("productUsage.monthlySummary",    {"assetsCreated": 240, "brands": 4, "seatsActive": 8}, dict(days=11)),
            ("web.webpagedetails.pageViews",   {"page": "/express/brand-kits"}, dict(days=15)),
            ("commerce.purchases",             {"plan": "CC_TEAMS", "seats": 8, "type": "Renewal"}, dict(days=160)),
        ],
        "lucia-sign-contracts": [
            ("web.webpagedetails.pageViews",   {"page": "/es/docuforge/online/sign-pdf"}, dict(days=1)),
            ("productUsage.exportPdf",         {"app": "VectorForge", "exports30d": 14}, dict(days=3)),
            ("productUsage.monthlySummary",    {"documentsCreated": 96, "trendPct": 28}, dict(days=10)),
        ],
        "robert-signin": [
            ("application.loginFailed",        {"attempts24h": 6, "reason": "invalid_credentials"}, dict(minutes=18)),
            ("commerce.offerDeclined",         {"offer": "All Apps upgrade", "channel": "in-app"}, dict(days=95)),
            ("commerce.offerDeclined",         {"offer": "Acme Stock add-on", "channel": "email"}, dict(days=210)),
            ("commerce.purchases",             {"plan": "PHOTO_1TB", "type": "Renewal"}, dict(days=198)),
        ],
        "elena-double-charge": [
            ("case.slaBreached",               {"caseId": "CASE-40217", "promised": "Refund in 5 days", "elapsedDays": 7}, dict(days=2)),
            ("contactCentre.interaction",      {"intent": "billing.dispute", "outcome": "Refund promised — 5 days",
                                                "caseId": "CASE-40217", "channel": "voice"}, dict(days=7)),
            ("case.opened",                    {"caseId": "CASE-40217", "type": "Duplicate charge", "priority": "P3"}, dict(days=7)),
            ("billing.chargePosted",           {"amount": 59.99, "currency": "GBP", "duplicate": True}, dict(days=9)),
            ("billing.chargePosted",           {"amount": 59.99, "currency": "GBP", "plan": "CC_ALL_APPS"}, dict(days=9)),
        ],
    }
    return [_e(sid, t, payload, **when) for t, payload, when in H.get(sid, [])]


def seed(platform, only=None):
    """Write the demo customers and their history. Called at start-up, and per customer
    when a contact is routed, so a replay always starts from the same state."""
    ids = [only] if only else list(PROFILES)
    for sid in ids:
        platform.reset_profile(PROFILES[sid], history(sid))
