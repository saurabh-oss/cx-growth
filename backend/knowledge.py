"""
KNOWLEDGE FABRIC — what the copilot is allowed to say, and where it says it from.

The Knowledge Fabric Data Agent grounds every recommendation in an approved article. A
copilot that recalls a price from a model's memory is a liability; one that cites
KB-1001 can be checked, corrected and audited.

Retrieval is BM25 over a small article set — a standard ranking function, implemented
here in forty lines so the demo has no search dependency. In the target architecture the
same call goes to the Knowledge Fabric over an MCP connector.

THE ARTICLES ARE ILLUSTRATIVE. They are written to be plausible for a consumer
subscription business. Before any real use they are replaced by Acme's approved
content — which is the point of the agent: the engine changes nothing, the knowledge does.
"""
import math, re

ARTICLES = [
    {"id": "KB-1001", "cat": "Plans", "title": "Photography plan storage tiers",
     "body": "The Photography plan is available with 20GB or 1TB of cloud storage. Both include LightVault and "
             "PhotoForge. Moving from 20GB to 1TB changes the price from $9.99 to $19.99 a month. The change "
             "takes effect immediately and keeps every photo, preset and catalogue.",
     "tags": "storage full upgrade photography 1tb 20gb lightvault sync"},
    {"id": "KB-1002", "cat": "Storage", "title": "What happens when cloud storage is full",
     "body": "When cloud storage reaches its limit, syncing pauses on every device. Nothing is deleted and "
             "originals already on the device stay there. Sync resumes automatically as soon as space is freed "
             "or the storage tier is increased.", "self_service": False,
     "tags": "storage full sync stopped paused quota limit phone photos"},
    {"id": "KB-1003", "cat": "Storage", "title": "Cloud storage add-on",
     "body": "Any paid Studio Cloud plan can add 1TB of cloud storage for $9.99 a month without changing plan. "
             "The add-on can be removed at the next billing date.",
     "tags": "storage add-on extra space 1tb more storage"},
    {"id": "KB-1010", "cat": "Generative AI", "title": "How generative credits work",
     "body": "Each plan includes a monthly allocation of generative credits. Credits reset on the billing date "
             "and do not roll over. When the allocation is used, generative features are limited until the "
             "reset. Higher plans include a larger allocation, and a credits add-on is available at $4.99 a month.",
     "tags": "generative credits glowfly fill exhausted run out reset allocation"},
    {"id": "KB-1011", "cat": "Plans", "title": "Studio Cloud All Apps — what is included",
     "body": "All Apps includes more than twenty apps, among them PhotoForge, VectorForge, PageForge, ClipForge Pro "
             "and MotionForge, with 100GB of storage and a higher generative credit allocation. It is $59.99 "
             "a month for an individual.",
     "tags": "all apps clipforge video upgrade plan include apps"},
    {"id": "KB-1020", "cat": "Licensing", "title": "Individual licence — device and user limits",
     "body": "An individual licence is for one person. It can be installed on more than one computer and signed "
             "in on two, but used on one at a time. A third sign-in signs out one of the others. Sharing a "
             "login between people is outside the licence terms.",
     "tags": "signed out another device concurrent sign-in sharing login individual licence limit colleague"},
    {"id": "KB-1021", "cat": "Licensing", "title": "Studio Cloud for teams — what changes",
     "body": "Studio Cloud for teams is licensed per seat at $89.99 a month. It adds the Admin Console for "
             "assigning and reassigning seats, 1TB of storage per user, shared libraries, and billing by "
             "company invoice or purchase order.",
     "tags": "teams business seats admin console invoice shared libraries studio company colleagues"},
    {"id": "KB-1022", "cat": "Licensing", "title": "Moving from an individual licence to teams",
     "body": "Assets, libraries and presets migrate from the individual account to the team organisation with "
             "no loss. The unused part of the individual term is credited against the first team invoice.",
     "tags": "migrate individual teams move assets credit prorated"},
    {"id": "KB-1030", "cat": "Billing", "title": "Cancelling a subscription",
     "body": "Cancellation terms depend on the plan commitment. Before processing, the agent must state clearly "
             "any charge that applies and the date access ends. Files remain available to download for 90 days.",
     "tags": "cancel cancellation subscription end terminate fee terms"},
    {"id": "KB-1031", "cat": "Billing", "title": "Changing plan instead of cancelling",
     "body": "A customer using only PhotoForge and LightVault can move from All Apps to the Photography plan. The "
             "Acme ID, files, presets and catalogue history are kept. The new price applies from the next "
             "billing date and no cancellation charge applies to a plan change.",
     "tags": "downgrade switch plan cheaper too expensive photography instead of cancel price"},
    {"id": "KB-1040", "cat": "Plans", "title": "Acme Express Premium — features",
     "body": "Express Premium unlocks background removal, premium templates, the full Acme Fonts library, brand "
             "kits and one-click resize. It is $9.99 a month.",
     "tags": "express premium feature background remove template fonts locked brand kit"},
    {"id": "KB-1041", "cat": "Plans", "title": "Express Premium free trial",
     "body": "Express Premium can be started on a 30-day free trial. No charge is taken if the trial is "
             "cancelled before it ends, and designs made during the trial are kept.",
     "tags": "trial free express try before paying worth it"},
    {"id": "KB-1050", "cat": "Billing", "title": "Duplicate charge — refund procedure",
     "body": "Confirm both charges on the account. A Tier 2 agent may process the refund directly rather than "
             "re-queueing it. Refunds return to the original payment method in five to seven working days. "
             "Send written confirmation with a reference number.",
     "tags": "charged twice duplicate double charge refund billing error money back"},
    {"id": "KB-1051", "cat": "Policy", "title": "Service recovery — commercial hold",
     "body": "No commercial offer is made on a contact with an unresolved billing failure or a broken commitment. "
             "A 14-day hold applies after the failure is resolved. The hold is set on the customer profile and "
             "enforced at routing.",
     "tags": "service recovery suppress offer complaint hold policy guardrail"},
    {"id": "KB-1052", "cat": "Policy", "title": "Offer policy — consent, frequency and fit",
     "body": "One offer per contact. No offer without marketing consent on record. No second offer inside 30 "
             "days of the last. Recommend the smallest plan that removes the customer's actual constraint.",
     "tags": "offer policy consent cooldown frequency fatigue one offer"},
    {"id": "KB-1060", "cat": "Account", "title": "Resetting a password",
     "body": "Select Forgot password on the sign-in page. A reset link is sent to the email address on the Acme "
             "ID. The link is valid for 30 minutes. If the email address has changed, update it first.",
     "self_service": True,
     "tags": "password reset forgot sign in log in cannot incorrect locked out"},
    {"id": "KB-1061", "cat": "Account", "title": "Changing the email address on an Acme ID",
     "body": "Sign in, open Account, then Change email. A confirmation is sent to the new address. If the old "
             "address can no longer be reached, an agent verifies identity and updates it.",
     "self_service": True,
     "tags": "change email address acme id update provider new email"},
    {"id": "KB-1062", "cat": "Billing", "title": "Updating a payment method",
     "body": "Sign in, open Account, then Plans and payment, then Manage payment. A new card takes effect from "
             "the next charge. A failed payment is retried automatically for ten days.",
     "self_service": True,
     "tags": "payment method card update expired change card billing details"},
    {"id": "KB-1063", "cat": "Billing", "title": "Downloading an invoice or receipt",
     "body": "Sign in, open Account, then Orders and invoices. Each invoice can be downloaded as a PDF. Team "
             "accounts can add a company name and tax number from the Admin Console.",
     "self_service": True,
     "tags": "invoice receipt download copy tax vat pdf accountant"},
    {"id": "KB-1064", "cat": "Technical", "title": "Install or update errors",
     "body": "Restart the Studio Cloud desktop app and retry. If the error persists, sign out and in again, "
             "then check available disk space. Error codes are listed in the desktop app under Help.",
     "self_service": True,
     "tags": "install error update failed download stuck studio cloud desktop code"},
    {"id": "KB-1065", "cat": "Technical", "title": "App crashes or runs slowly",
     "body": "Update to the latest version, then reset preferences by holding the modifier keys at launch. "
             "Turn off GPU acceleration to test whether the graphics driver is the cause.",
     "self_service": True,
     "tags": "crash crashes slow performance freeze hang lag"},
    {"id": "KB-1070", "cat": "Engage Cloud", "title": "ContentVault Assets — overview",
     "body": "ContentVault Assets is a governed asset library: one approved version of each asset, with "
             "versioning, approval workflow and a brand portal. It connects to Studio Cloud apps so designers "
             "work from the approved source. Pricing is by quote.",
     "tags": "assets versions approved out-of-date library governance brand dam asset management"},
    {"id": "KB-1071", "cat": "Engage Cloud", "title": "Acme Analytics — creative performance",
     "body": "Acme Analytics measures which creative, pages and campaigns drive outcomes. It is positioned "
             "after asset governance is in place, so that performance is measured against approved assets.",
     "tags": "analytics performance measure which images drive sales campaign"},
    {"id": "KB-1072", "cat": "Policy", "title": "Cross-cloud referral — warm handoff",
     "body": "Engage Cloud opportunities are handed to the specialist team, not quoted by the care agent. "
             "Capture asset volume, brand count and the customer's words, and book the specialist within 48 hours.",
     "tags": "handoff referral specialist engage cloud cross-sell warm transfer"},
    {"id": "KB-1080", "cat": "Docs Cloud", "title": "DocuForge Pro — editing and e-signatures",
     "body": "DocuForge Pro edits and converts PDFs and sends documents for legally binding e-signature, with "
             "tracking of who has signed. It is $19.99 a month and works alongside any Studio Cloud plan.",
     "tags": "docuforge pdf sign signature contract e-sign document firmar contrato"},
    {"id": "KB-1081", "cat": "Docs Cloud", "title": "Exporting a PDF from VectorForge",
     "body": "Use File, Save As, Acme PDF. The High Quality Print preset keeps vector artwork editable. An "
             "exported PDF cannot collect a signature without DocuForge.",
     "tags": "export pdf vectorforge save as preset"},
    {"id": "KB-1090", "cat": "Policy", "title": "Identity verification before account changes",
     "body": "Plan, billing and email changes need a verified identity. If the automated challenge fails, the "
             "agent verifies with two account facts before making any change.",
     "tags": "verify identity challenge authentication security"},
]

_STOP = set("a an and are as at be but by for from has have i if in is it its my of on or our so that the "
            "their there this to was we were what when which who will with you your me can do does how".split())
_BY_ID = {a["id"]: a for a in ARTICLES}


def _tok(text):
    out = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in _STOP or len(w) < 2:
            continue
        for suf in ("ing", "ed", "es", "s"):
            if len(w) > len(suf) + 3 and w.endswith(suf):
                w = w[:-len(suf)]
                break
        out.append(w)
    return out


class _Index:
    K1, B = 1.4, 0.75

    def __init__(self, articles):
        self.docs = []
        for a in articles:
            # Title and tags count for more than body text.
            toks = _tok(a["title"]) * 3 + _tok(a["tags"]) * 2 + _tok(a["body"])
            tf = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            self.docs.append((a, tf, len(toks)))
        self.avg = sum(d[2] for d in self.docs) / float(len(self.docs))
        df = {}
        for _, tf, _ in self.docs:
            for t in tf:
                df[t] = df.get(t, 0) + 1
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query, k=3):
        q = _tok(query)
        scored = []
        for a, tf, ln in self.docs:
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.K1 + 1) / (f + self.K1 * (1 - self.B + self.B * ln / self.avg))
            if s > 0:
                scored.append((s, a))
        scored.sort(key=lambda t: -t[0])
        return scored[:k]


_index = _Index(ARTICLES)


def _view(a, score=None):
    out = {"id": a["id"], "title": a["title"], "category": a["cat"], "body": a["body"],
           "self_service": bool(a.get("self_service"))}
    if score is not None:
        out["score"] = round(score, 2)
    return out


def search(query, k=3):
    return [_view(a, s) for s, a in _index.search(query, k)]


def get(article_id):
    a = _BY_ID.get(article_id)
    return _view(a) if a else None


# What the copilot cites for each kind of recommendation.
_FOR_OFFER = {
    "PHOTO_1TB": ["KB-1001", "KB-1002"], "STORAGE_ADDON": ["KB-1003", "KB-1002"],
    "CC_ALL_APPS": ["KB-1011", "KB-1010"], "CREDITS_ADDON": ["KB-1010"],
    "CC_TEAMS": ["KB-1021", "KB-1020", "KB-1022"], "EXPRESS_PREMIUM": ["KB-1040", "KB-1041"],
    "VAULT_ASSETS": ["KB-1070", "KB-1072", "KB-1071"], "DOCS_PRO": ["KB-1080", "KB-1081"],
    "PHOTO_20GB": ["KB-1001", "KB-1031"],
}
_FOR_INTENT = {
    "storage.limit": ["KB-1002", "KB-1001"], "credits.exhausted": ["KB-1010"],
    "account.concurrent": ["KB-1020"], "feature.gated": ["KB-1040"],
    "assets.versioning": ["KB-1070"], "documents.sign": ["KB-1081", "KB-1080"],
    "billing.cancel": ["KB-1030", "KB-1031"], "billing.dispute": ["KB-1050", "KB-1051"],
    "refund.status": ["KB-1050", "KB-1051"], "account.access": ["KB-1060", "KB-1090"],
    "account.profile": ["KB-1061"], "billing.payment": ["KB-1062"], "billing.invoice": ["KB-1063"],
    "install.error": ["KB-1064"], "app.crash": ["KB-1065"], "plan.compare": ["KB-1001", "KB-1011"],
}


def grounding(intent_id=None, offer=None, retention=False, limit=3):
    """The articles a recommendation rests on, most specific first."""
    ids = []
    if offer:
        for t in offer["offer"]["to"]:
            ids += _FOR_OFFER.get(t.get("code"), [])
        if retention:
            ids = ["KB-1031"] + ids
        ids.append("KB-1052")
    ids += _FOR_INTENT.get(intent_id, [])
    seen, out = set(), []
    for i in ids:
        if i not in seen and i in _BY_ID:
            seen.add(i)
            out.append(_view(_BY_ID[i]))
    return out[:limit]


# ══════════════════════════════════════════════════════════════════════════════
#  DIGITAL SELF-SERVICE — resolve what does not need an agent, hand over what does
# ══════════════════════════════════════════════════════════════════════════════
CONFIDENT = 5.0       # BM25 score above which the top article is treated as the answer


def self_service(question):
    """Answer from knowledge if the match is confident and the task is one a customer can
    complete alone. Otherwise escalate — and carry what was learned to the agent."""
    hits = _index.search(question, 3)
    if not hits:
        return {"resolved": False, "confidence": 0.0, "answer": None, "articles": [],
                "handoff": {"reason": "Nothing in the knowledge base matches this question",
                            "context": question, "suggested_intent": None}}
    top_score, top = hits[0]
    conf = round(min(0.99, top_score / (top_score + 4.0)), 2)
    intent_id = next((k for k, v in _FOR_INTENT.items() if top["id"] in v[:1]), None)
    resolved = bool(top.get("self_service")) and top_score >= CONFIDENT
    out = {"resolved": resolved, "confidence": conf, "articles": [_view(a, s) for s, a in hits],
           "suggested_intent": intent_id}
    if resolved:
        out["answer"] = top["body"]
        out["source"] = {"id": top["id"], "title": top["title"]}
        out["handoff"] = None
    else:
        out["answer"] = None
        why = ("This needs an agent — it involves the account, a charge or a plan decision"
               if top_score >= CONFIDENT else "The match is not confident enough to answer unattended")
        out["handoff"] = {"reason": why, "context": question, "suggested_intent": intent_id,
                          "carries": ["The customer's question, verbatim", "Articles already shown",
                                      "Captured intent" + (": " + intent_id if intent_id else "")]}
    return out


def deflectable_intents():
    """Intents whose first-choice article is one a customer can complete alone."""
    return sorted(k for k, v in _FOR_INTENT.items() if _BY_ID[v[0]].get("self_service"))
