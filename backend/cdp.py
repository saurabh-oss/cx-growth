"""
CUSTOMER PLATFORM — the customer data platform seat in the architecture.

The target architecture puts the vendor's own experience platform here. This prototype
has no sandbox for it, so it does the next most useful thing: it fixes the DATA CONTRACT
to the vendor's published data model, and makes the platform behind it swappable.

    ┌──────────────────────────────┐
    │  Growth Engine · Frontier    │   speaks the data model, and only that
    └──────────────┬───────────────┘
                   │  CustomerPlatform   (six operations)
       ┌───────────┼──────────────────────────┐
       ▼           ▼                          ▼
    LocalPlatform  UnomiPlatform              VendorPlatform
    SQLite,        Apache Unomi 3 (OSS CDP,   the vendor's platform
    in-process     OASIS reference impl.)     (needs a sandbox)

Three things carry the "works here, works there" argument:

1. PROFILES AND EVENTS FOLLOW THE DATA MODEL. identityMap, person.name, consents,
   eventType, timestamp. Everything specific to this demo sits under a tenant
   namespace, exactly as custom fields do on the vendor's platform.

2. AUDIENCES ARE DEFINED ONCE, in a small neutral condition tree, and rendered three
   ways: evaluated in Python, as a Unomi condition, and as the vendor's query language.

3. THE ENGINE NEVER NAMES THE PLATFORM. It calls get_profile / record_event /
   audiences_for. Which adapter answers is configuration: CUSTOMER_PLATFORM=local|unomi|vendor.

What this does NOT prove is stated on the Technology screen and in the README: identity
stitching, the vendor's own propensity models, governance labels and activation have no
equivalent here.
"""
import os, json, sqlite3, time, uuid, base64, threading
import urllib.request, urllib.error
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import brand

# The tenant namespace: where this demo's own fields live inside a profile or an event.
TENANT = "_cxdemo"
DB_PATH = Path(__file__).parent / "cx.db"
_NS = brand.vendor_api().get("channel_ns", "https://ns.example.com/channel-types")
VOICE = _NS + "/voice"
CHAT = _NS + "/chat"


def iso(dt=None):
    return (dt or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ago(days=0, hours=0, minutes=0):
    return iso(datetime.now(timezone.utc) - timedelta(days=days, hours=hours, minutes=minutes))


# ══════════════════════════════════════════════════════════════════════════════
#  DOCUMENT BUILDERS
# ══════════════════════════════════════════════════════════════════════════════
def profile_doc(pid, first, last, email, country="GB", language="en-GB", phone=None,
                customer_type="Consumer", marketing_consent=True,
                entitlement=None, usage=None, service=None, health=None, commercial=None):
    """A customer profile. Standard field groups at the root, this demo's own fields
    under the tenant namespace."""
    idmap = {
        "CRMID": [{"id": pid, "primary": True}],
        "Email": [{"id": email, "primary": False}],
    }
    if phone:
        idmap["Phone"] = [{"id": phone, "primary": False}]
    y = "y" if marketing_consent else "n"
    svc = dict(service or {})
    svc.setdefault("openCases", [])
    svc["openCaseCount"] = len(svc["openCases"])
    ent = dict(entitlement or {})
    ent.setdefault("cloudsOwned", ["Studio Cloud"])
    ent["experienceSuiteOwned"] = "Engage Cloud" in ent["cloudsOwned"]
    return {
        "_id": pid,
        "identityMap": idmap,
        "person": {"name": {"firstName": first, "lastName": last}},
        "personalEmail": {"address": email},
        "homeAddress": {"countryCode": country},
        "preferredLanguage": language,
        "consents": {
            "collect": {"val": "y"},
            "marketing": {"any": {"val": y}, "email": {"val": y}, "call": {"val": y}},
            "personalize": {"content": {"val": "y"}},
        },
        TENANT: {
            "customerType": customer_type,
            "entitlement": ent,
            "usage": dict(usage or {}),
            "service": svc,
            "health": dict(health or {}),
            "commercial": dict(commercial or {}),
        },
    }


def event_doc(event_type, profile_id, payload=None, timestamp=None, channel=None, eid=None, source="runtime"):
    """Something that happened: an interaction, a decision, an outcome."""
    ev = {
        "_id": eid or uuid.uuid4().hex,
        "eventType": event_type,
        "timestamp": timestamp or iso(),
        "identityMap": {"CRMID": [{"id": profile_id, "primary": True}]},
        TENANT: dict(payload or {}),
    }
    if channel:
        ev["channel"] = {"_type": VOICE if channel == "voice" else CHAT, "mediaType": channel}
    ev[TENANT]["source"] = source
    return ev


def full_name(profile):
    n = (profile.get("person") or {}).get("name") or {}
    return ("%s %s" % (n.get("firstName", ""), n.get("lastName", ""))).strip()


def get_path(doc, path, default=None):
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def set_path(doc, path, value):
    parts = path.split(".")
    cur = doc
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


# ══════════════════════════════════════════════════════════════════════════════
#  AUDIENCES — defined once, rendered three ways
#  A condition is {"all": [...]}, {"any": [...]}, or a leaf {"field", "op", "value"}.
# ══════════════════════════════════════════════════════════════════════════════
U, S, E = TENANT + ".usage.", TENANT + ".service.", TENANT + ".entitlement."

AUDIENCES = [
    {"id": "capacity-constrained", "name": "Capacity constrained",
     "description": "At a hard limit on storage or generative credits",
     "condition": {"any": [
         {"field": U + "storageUsedPct", "op": "gte", "value": 95},
         {"field": U + "creditsExhaustedMonths", "op": "gte", "value": 2}]}},
    {"id": "licence-outgrown", "name": "Licence outgrown",
     "description": "An individual licence in use by more than one person",
     "condition": {"all": [
         {"field": E + "licenceType", "op": "eq", "value": "INDIVIDUAL"},
         {"field": U + "distinctUsers30d", "op": "gte", "value": 2}]}},
    {"id": "free-tier-gated", "name": "Free tier, gated",
     "description": "Free plan repeatedly meeting premium feature gates",
     "condition": {"all": [
         {"field": E + "planCode", "op": "eq", "value": "EXPRESS_FREE"},
         {"field": U + "featureGateHits30d", "op": "gte", "value": 5}]}},
    {"id": "under-utilised-plan", "name": "Under-utilised plan",
     "description": "Paying for a broad plan, using a fraction of it",
     "condition": {"all": [
         {"field": U + "appsEntitled", "op": "gte", "value": 10},
         {"field": U + "appsUsed30d", "op": "lte", "value": 3}]}},
    {"id": "cross-cloud-ready", "name": "Cross-cloud ready",
     "description": "Asset volume across brands with no Engage Cloud product",
     "condition": {"all": [
         {"field": U + "assetsPerMonth", "op": "gte", "value": 150},
         {"field": U + "brandCount", "op": "gte", "value": 2},
         {"field": E + "experienceSuiteOwned", "op": "eq", "value": False}]}},
    {"id": "growth-ready", "name": "Growth ready",
     "description": "Healthy account with expanding usage",
     "condition": {"all": [
         {"field": TENANT + ".health.score", "op": "gte", "value": 75},
         {"field": U + "usageTrendPct", "op": "gte", "value": 20}]}},
    {"id": "service-recovery", "name": "Service recovery",
     "description": "Unresolved failure — commercial motion suppressed",
     "condition": {"any": [
         {"field": S + "duplicateChargeFlag", "op": "eq", "value": True},
         {"all": [
             {"field": S + "openCaseCount", "op": "gte", "value": 1},
             {"field": S + "repeatContact7d", "op": "eq", "value": True}]}]}},
    {"id": "marketing-opt-out", "name": "Marketing opt-out",
     "description": "No consent on record for offers",
     "condition": {"all": [
         {"field": "consents.marketing.any.val", "op": "eq", "value": "n"}]}},
]

_OPS = {
    "eq": lambda a, b: a == b, "ne": lambda a, b: a != b,
    "gte": lambda a, b: a is not None and a >= b, "lte": lambda a, b: a is not None and a <= b,
    "gt": lambda a, b: a is not None and a > b, "lt": lambda a, b: a is not None and a < b,
}


def evaluate(cond, profile):
    if "all" in cond:
        return all(evaluate(c, profile) for c in cond["all"])
    if "any" in cond:
        return any(evaluate(c, profile) for c in cond["any"])
    v = get_path(profile, cond["field"])
    if v is None and isinstance(cond["value"], bool):
        v = False
    try:
        return bool(_OPS[cond["op"]](v, cond["value"]))
    except TypeError:
        return False


_QUERY_OP = {"eq": "=", "ne": "!=", "gte": ">=", "lte": "<=", "gt": ">", "lt": "<"}


def to_query(cond, top=True):
    """The vendor's profile query language — what an audience definition holds there."""
    if "all" in cond or "any" in cond:
        key = "all" if "all" in cond else "any"
        s = (" and " if key == "all" else " or ").join(to_query(c, False) for c in cond[key])
        return s if top or len(cond[key]) == 1 else "(" + s + ")"
    v = cond["value"]
    lit = ("true" if v else "false") if isinstance(v, bool) else ('"%s"' % v if isinstance(v, str) else str(v))
    return "%s %s %s" % (cond["field"], _QUERY_OP[cond["op"]], lit)


_UNOMI_OP = {"eq": "equals", "ne": "notEquals", "gte": "greaterThanOrEqualTo",
             "lte": "lessThanOrEqualTo", "gt": "greaterThan", "lt": "lessThan"}


def unomi_field(path):
    """Profile path to Unomi property name. Unomi keeps profile data under `properties`, and
    Elasticsearch reserves leading-underscore names, so the tenant prefix loses its underscore."""
    return "properties." + path.replace(TENANT, TENANT.lstrip("_"))


def to_unomi(cond):
    """Apache Unomi condition tree."""
    if "all" in cond or "any" in cond:
        key = "all" if "all" in cond else "any"
        return {"type": "booleanCondition", "parameterValues": {
            "operator": "and" if key == "all" else "or",
            "subConditions": [to_unomi(c) for c in cond[key]]}}
    v = cond["value"]
    pv = {"propertyName": unomi_field(cond["field"]), "comparisonOperator": _UNOMI_OP[cond["op"]]}
    if isinstance(v, bool):
        pv["propertyValue"] = "true" if v else "false"
    elif isinstance(v, int):
        pv["propertyValueInteger"] = v
    elif isinstance(v, float):
        pv["propertyValueDouble"] = v
    else:
        pv["propertyValue"] = v
    return {"type": "profilePropertyCondition", "parameterValues": pv}


def audience_renderings():
    return [{"id": a["id"], "name": a["name"], "description": a["description"],
             "neutral": a["condition"], "query": to_query(a["condition"]),
             "unomi": to_unomi(a["condition"])} for a in AUDIENCES]


# ══════════════════════════════════════════════════════════════════════════════
#  THE INTERFACE — five operations. This is the whole surface the engine depends on.
# ══════════════════════════════════════════════════════════════════════════════
class CustomerPlatform:
    key = "abstract"
    label = "Customer platform"

    def info(self):                                  raise NotImplementedError
    def upsert_profile(self, profile):               raise NotImplementedError
    def get_profile(self, profile_id):               raise NotImplementedError
    def record_event(self, profile_id, event):       raise NotImplementedError
    def events_for(self, profile_id, limit=25):      raise NotImplementedError
    def audiences_for(self, profile_id):             raise NotImplementedError
    def reset_profile(self, profile, events=()):     raise NotImplementedError

    def patch_profile(self, profile_id, changes):
        """changes: {dotted.path: value}. Read, modify, write — every adapter can do that."""
        p = self.get_profile(profile_id)
        if not p:
            return None
        for path, value in changes.items():
            set_path(p, path, value)
        self.upsert_profile(p)
        return p


# ── 1 · LOCAL ─────────────────────────────────────────────────────────────────
class LocalPlatform(CustomerPlatform):
    """In-process SQLite store. Zero dependencies, so the demo always has a platform."""
    key = "local"
    label = "Built-in profile store"

    def __init__(self, path=DB_PATH):
        self.path = str(path)
        self._lock = threading.Lock()
        with closing(self._conn()) as c, c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS profiles (id TEXT PRIMARY KEY, doc TEXT, updated_at TEXT);
                CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, profile_id TEXT, ts TEXT,
                                                   event_type TEXT, doc TEXT);
                CREATE INDEX IF NOT EXISTS ix_events_profile ON events (profile_id, ts);
            """)

    def _conn(self):
        c = sqlite3.connect(self.path, timeout=5)
        c.row_factory = sqlite3.Row
        return c

    def info(self):
        with closing(self._conn()) as c, c:
            np = c.execute("SELECT COUNT(*) n FROM profiles").fetchone()["n"]
            ne = c.execute("SELECT COUNT(*) n FROM events").fetchone()["n"]
        return {"key": self.key, "label": self.label, "engine": "SQLite · in-process",
                "status": "connected", "profiles": np, "events": ne, "endpoint": "embedded"}

    def upsert_profile(self, profile):
        with self._lock, closing(self._conn()) as c, c:
            c.execute("INSERT INTO profiles (id, doc, updated_at) VALUES (?,?,?) "
                      "ON CONFLICT(id) DO UPDATE SET doc=excluded.doc, updated_at=excluded.updated_at",
                      (profile["_id"], json.dumps(profile), iso()))
        return profile["_id"]

    def get_profile(self, profile_id):
        with closing(self._conn()) as c, c:
            r = c.execute("SELECT doc FROM profiles WHERE id=?", (profile_id,)).fetchone()
        return json.loads(r["doc"]) if r else None

    def record_event(self, profile_id, event):
        with self._lock, closing(self._conn()) as c, c:
            c.execute("INSERT OR REPLACE INTO events (id, profile_id, ts, event_type, doc) VALUES (?,?,?,?,?)",
                      (event["_id"], profile_id, event["timestamp"], event["eventType"], json.dumps(event)))
        return event["_id"]

    def events_for(self, profile_id, limit=25):
        with closing(self._conn()) as c, c:
            rows = c.execute("SELECT doc FROM events WHERE profile_id=? ORDER BY ts DESC LIMIT ?",
                             (profile_id, limit)).fetchall()
        return [json.loads(r["doc"]) for r in rows]

    def audiences_for(self, profile_id):
        p = self.get_profile(profile_id)
        return [a["id"] for a in AUDIENCES if p and evaluate(a["condition"], p)]

    def reset_profile(self, profile, events=()):
        """Put a customer back exactly as given: this profile, these events, nothing else."""
        with self._lock, closing(self._conn()) as c, c:
            c.execute("DELETE FROM events WHERE profile_id=?", (profile["_id"],))
        self.upsert_profile(profile)
        for ev in events:
            self.record_event(profile["_id"], ev)

    def wipe(self):
        with self._lock, closing(self._conn()) as c, c:
            c.execute("DELETE FROM events")
            c.execute("DELETE FROM profiles")


# ── 2 · APACHE UNOMI ──────────────────────────────────────────────────────────
class UnomiPlatform(CustomerPlatform):
    """Apache Unomi 3 over REST. Open source (Apache 2.0) and the reference implementation
    of the OASIS Customer Data Platform specification. Start it with platform/docker-compose.yml."""
    key = "unomi"
    label = "Apache Unomi"
    EVENT_TYPE = "cxActivityEvent"
    SCOPE = "cx"

    def __init__(self, base=None, user=None, password=None, timeout=4.0):
        # 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 first and every call
        # waits two seconds for it to fail before falling back.
        self.base = (base or os.environ.get("UNOMI_URL", "http://127.0.0.1:8181")).rstrip("/")
        cred = "%s:%s" % (user or os.environ.get("UNOMI_USER", "karaf"),
                          password or os.environ.get("UNOMI_PASSWORD", "karaf"))
        self.auth = "Basic " + base64.b64encode(cred.encode()).decode()
        self.timeout = timeout
        self._ready = False
        self._prepared_at = 0.0

    # -- transport
    def _call(self, method, path, body=None, auth=True, headers=None, timeout=None):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        if auth:
            req.add_header("Authorization", self.auth)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
            raw = r.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else None

    def reachable(self):
        try:
            self._call("GET", "/cxs/cluster", timeout=1.5)
            return True
        except Exception:
            return False

    def prepare(self):
        """Idempotent one-time setup: scope, event schema, audience definitions."""
        if self._ready:
            return
        self._call("POST", "/cxs/scopes", {"itemId": self.SCOPE, "itemType": "scope",
                                           "metadata": {"id": self.SCOPE, "name": "CX contact centre"}})
        self._call("POST", "/cxs/jsonSchema", {
            "$id": "https://unomi.apache.org/schemas/json/events/%s/1-0-0" % self.EVENT_TYPE,
            "$schema": "https://json-schema.org/draft/2019-09/schema",
            "self": {"vendor": "com.cx.growth", "target": "events", "name": self.EVENT_TYPE,
                     "format": "jsonschema", "version": "1-0-0"},
            "title": "An experience event carried on a Unomi event", "type": "object",
            "allOf": [{"$ref": "https://unomi.apache.org/schemas/json/event/1-0-0"}],
            "properties": {"properties": {"type": "object", "properties": {
                "docEventType": {"type": "string"}, "docId": {"type": "string"},
                "docTimestamp": {"type": "string"}, "doc": {"type": "string"}},
                "required": ["docEventType", "doc"]}},
            "unevaluatedProperties": False})
        for a in AUDIENCES:
            self._call("POST", "/cxs/segments", {
                "metadata": {"id": a["id"], "name": a["name"], "scope": "systemscope",
                             "description": a["description"], "enabled": True},
                "condition": to_unomi(a["condition"])})
        self._ready = True
        self._prepared_at = time.time()

    # -- mapping
    @staticmethod
    def _to_unomi_profile(profile):
        t = TENANT.lstrip("_")
        n = profile.get("person", {}).get("name", {})
        return {"itemId": profile["_id"], "itemType": "profile", "properties": {
            "firstName": n.get("firstName"), "lastName": n.get("lastName"),
            "email": profile.get("personalEmail", {}).get("address"),
            "countryCode": profile.get("homeAddress", {}).get("countryCode"),
            "preferredLanguage": profile.get("preferredLanguage"),
            "consents": profile.get("consents"),
            t: profile.get(TENANT),
            # The document rides along verbatim, so a read returns exactly what was written.
            "doc": json.dumps(profile)}}

    def info(self):
        try:
            self._call("GET", "/cxs/cluster", timeout=1.5)
            n = self._call("POST", "/cxs/profiles/search", {"offset": 0, "limit": 1, "condition": {
                "type": "profilePropertyCondition", "parameterValues": {
                    "propertyName": "properties.doc", "comparisonOperator": "exists"}}})
            return {"key": self.key, "label": self.label, "engine": "Apache Unomi · Elasticsearch",
                    "status": "connected", "profiles": (n or {}).get("totalSize", 0), "events": None,
                    "endpoint": self.base}
        except Exception as ex:
            return {"key": self.key, "label": self.label, "engine": "Apache Unomi · Elasticsearch",
                    "status": "unreachable", "error": str(ex), "endpoint": self.base}

    def upsert_profile(self, profile):
        self.prepare()
        self._call("POST", "/cxs/profiles", self._to_unomi_profile(profile))
        return profile["_id"]

    def get_profile(self, profile_id):
        try:
            r = self._call("GET", "/cxs/profiles/" + profile_id)
        except urllib.error.HTTPError as ex:
            if ex.code in (204, 404):
                return None
            raise
        if not r or "properties" not in r or "doc" not in r["properties"]:
            return None
        return json.loads(r["properties"]["doc"])

    def _context(self, profile_id, events=None, session=None):
        body = {"source": {"itemId": "growth-engine", "itemType": "contactCentre", "scope": self.SCOPE},
                "requireSegments": True}
        if events:
            body["events"] = events
        return self._call("POST", "/cxs/context.json?sessionId=" + (session or "cx-" + profile_id), body,
                          auth=False, headers={"Cookie": "context-profile-id=" + profile_id})

    def record_event(self, profile_id, event):
        self.prepare()
        payload = [{
            "eventType": self.EVENT_TYPE, "scope": self.SCOPE,
            "properties": {"docEventType": event["eventType"], "docId": event["_id"],
                           "docTimestamp": event["timestamp"], "doc": json.dumps(event)}}]
        while True:
            r = self._context(profile_id, payload)
            if r and r.get("processedEvents", 0) >= 1:
                return event["_id"]
            # A schema registered a moment ago is not in force until Unomi next refreshes
            # its schemas. Only the first events after a first start ever wait here.
            if time.time() - self._prepared_at > 12:
                raise RuntimeError("Unomi rejected the event — schema validation failed")
            time.sleep(1.0)

    def events_for(self, profile_id, limit=25):
        r = self._call("POST", "/cxs/events/search", {"offset": 0, "limit": 200, "condition": {
            "type": "booleanCondition", "parameterValues": {"operator": "and", "subConditions": [
                {"type": "eventTypeCondition", "parameterValues": {"eventTypeId": self.EVENT_TYPE}},
                {"type": "eventPropertyCondition", "parameterValues": {
                    "propertyName": "profileId", "comparisonOperator": "equals",
                    "propertyValue": profile_id}}]}}})
        out = [json.loads(e["properties"]["doc"]) for e in (r or {}).get("list", [])
               if e.get("properties", {}).get("doc")]
        out.sort(key=lambda e: e["timestamp"], reverse=True)
        return out[:limit]

    def audiences_for(self, profile_id):
        r = self._context(profile_id)
        return sorted((r or {}).get("profileSegments") or [])

    def reset_profile(self, profile, events=()):
        try:
            # The privacy endpoint is the one that removes the profile's events and sessions
            # with it. DELETE /cxs/profiles/{id}?withData=true leaves the events behind.
            self._call("DELETE", "/cxs/privacy/profiles/%s?withData=true" % profile["_id"])
        except urllib.error.HTTPError as ex:
            if ex.code not in (204, 404):
                raise
        self.upsert_profile(profile)
        for ev in events:
            self.record_event(profile["_id"], ev)


# ── 3 · THE VENDOR'S PLATFORM ─────────────────────────────────────────────────
class VendorPlatform(CustomerPlatform):
    """The vendor's own experience platform. Written against a published API reference and
    NOT exercised — this prototype has no sandbox. It exists to show that the mapping is
    mechanical: the same six operations, the same documents, different URLs.

    Where the platform lives and what it calls things come from the brand pack
    (`vendor_api`); the shipped values are placeholders. Credentials come from the
    environment:

    Requires: XP_ORG_ID, XP_CLIENT_ID (API key), XP_ACCESS_TOKEN, XP_SANDBOX,
              XP_INLET_ID (streaming connection), XP_PROFILE_SCHEMA, XP_EVENT_SCHEMA,
              XP_PROFILE_DATASET, XP_EVENT_DATASET."""
    key = "vendor"
    REQUIRED = ["XP_ORG_ID", "XP_CLIENT_ID", "XP_ACCESS_TOKEN", "XP_SANDBOX", "XP_INLET_ID",
                "XP_PROFILE_SCHEMA", "XP_EVENT_SCHEMA", "XP_PROFILE_DATASET", "XP_EVENT_DATASET"]
    DEFAULTS = {
        "label": "Vendor experience platform",
        "api": "https://platform.example.com", "ingest": "https://ingest.example.com",
        "access_path": "/profile/entities", "audience_path": "/audience/definitions",
        "content_type": "application/json",
        "org_header": "x-org-id", "sandbox_header": "x-sandbox-name",
        "org_field": "orgId", "meta_field": "meta", "entity_field": "entity",
        "profile_schema": "profile", "event_schema": "activityevent",
        "membership_field": "audienceMembership", "membership_group": "default",
        "query_type": "QL", "query_format": "ql/text",
        "ingest_api": "Streaming ingestion API", "access_api": "Profile access API",
        "audience_api": "Audience definition API",
        "gap_identity": "The platform's identity graph",
        "gap_models": "The platform's own models, or this one hosted there",
        "gap_governance": "Usage labels and a policy service",
        "gap_activation": "Destinations and journey orchestration",
    }

    def __init__(self, env=None):
        self.env = env if env is not None else os.environ
        self.missing = [k for k in self.REQUIRED if not self.env.get(k)]
        self.cfg = {**self.DEFAULTS, **brand.vendor_api()}
        self.label = self.cfg["label"]

    def _headers(self):
        c = self.cfg
        return {"Authorization": "Bearer " + self.env.get("XP_ACCESS_TOKEN", ""),
                "x-api-key": self.env.get("XP_CLIENT_ID", ""),
                c["org_header"]: self.env.get("XP_ORG_ID", ""),
                c["sandbox_header"]: self.env.get("XP_SANDBOX", "prod"),
                "Content-Type": "application/json"}

    def _envelope(self, entity, schema, dataset):
        c = self.cfg
        ref = {"id": schema, "contentType": c["content_type"]}
        return {"header": {"schemaRef": ref, c["org_field"]: self.env.get("XP_ORG_ID", "{ORG_ID}"),
                           "datasetId": dataset, "source": {"name": "CX Growth Engine"}},
                "body": {c["meta_field"]: {"schemaRef": ref}, c["entity_field"]: entity}}

    def request_for(self, op, profile_id="{profileId}", doc=None):
        """The HTTP request each operation makes. Used by the Technology screen and the
        conformance notes — and by _send, so what is shown is what would be sent."""
        e, c = self.env, self.cfg
        access = c["api"] + c["access_path"]
        if op == "upsert_profile":
            return {"method": "POST", "url": "%s/collection/%s" % (c["ingest"], e.get("XP_INLET_ID", "{INLET_ID}")),
                    "body": self._envelope(doc or {"_id": profile_id}, e.get("XP_PROFILE_SCHEMA", "{PROFILE_SCHEMA_ID}"),
                                           e.get("XP_PROFILE_DATASET", "{PROFILE_DATASET_ID}"))}
        if op == "record_event":
            return {"method": "POST", "url": "%s/collection/%s" % (c["ingest"], e.get("XP_INLET_ID", "{INLET_ID}")),
                    "body": self._envelope(doc or {"eventType": "{eventType}"}, e.get("XP_EVENT_SCHEMA", "{EVENT_SCHEMA_ID}"),
                                           e.get("XP_EVENT_DATASET", "{EVENT_DATASET_ID}"))}
        if op == "get_profile":
            return {"method": "GET", "url": "%s?schema.name=%s&entityId=%s&entityIdNS=CRMID" % (
                access, c["profile_schema"], profile_id)}
        if op == "events_for":
            return {"method": "GET", "url": "%s?schema.name=%s&relatedSchema.name=%s&relatedEntityId=%s"
                                            "&relatedEntityIdNS=CRMID&orderby=-timestamp" % (
                access, c["event_schema"], c["profile_schema"], profile_id)}
        if op == "audiences_for":
            return {"method": "GET", "url": "%s?schema.name=%s&entityId=%s&entityIdNS=CRMID&fields=%s" % (
                access, c["profile_schema"], profile_id, c["membership_field"])}
        if op == "define_audience":
            return {"method": "POST", "url": c["api"] + c["audience_path"],
                    "body": {"name": (doc or {}).get("name", "{name}"),
                             "schema": {"name": c["profile_schema"]},
                             "expression": {"type": c["query_type"], "format": c["query_format"],
                                            "value": (doc or {}).get("query", "{QUERY}")}}}
        raise KeyError(op)

    def _send(self, op, profile_id=None, doc=None):
        if self.missing:
            raise RuntimeError("The vendor platform is not configured — missing " + ", ".join(self.missing))
        r = self.request_for(op, profile_id, doc)
        req = urllib.request.Request(r["url"], method=r["method"],
                                     data=json.dumps(r["body"]).encode() if "body" in r else None)
        for k, v in self._headers().items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else None

    def info(self):
        return {"key": self.key, "label": self.label, "engine": self.label,
                "status": "not configured" if self.missing else "configured", "missing": self.missing,
                "endpoint": self.cfg["api"]}

    def upsert_profile(self, profile):
        self._send("upsert_profile", profile["_id"], profile)
        return profile["_id"]

    def record_event(self, profile_id, event):
        self._send("record_event", profile_id, event)
        return event["_id"]

    def get_profile(self, profile_id):
        r = self._send("get_profile", profile_id) or {}
        for v in r.values():
            if isinstance(v, dict) and "entity" in v:
                return v["entity"]
        return None

    def events_for(self, profile_id, limit=25):
        r = self._send("events_for", profile_id) or {}
        return [c["entity"] for c in r.get("children", []) if "entity" in c][:limit]

    def audiences_for(self, profile_id):
        r = self._send("audiences_for", profile_id) or {}
        c = self.cfg
        for v in r.values():
            if isinstance(v, dict) and "entity" in v:
                m = (v["entity"].get(c["membership_field"]) or {}).get(c["membership_group"], {})
                return sorted(k for k, s in m.items() if s.get("status") in ("realized", "existing"))
        return []

    def reset_profile(self, profile, events=()):
        # There is no per-profile reset short of a privacy job. Write forward only.
        self.upsert_profile(profile)
        for ev in events:
            self.record_event(profile["_id"], ev)


# ══════════════════════════════════════════════════════════════════════════════
#  PORTABILITY — the same operation on each platform, side by side
# ══════════════════════════════════════════════════════════════════════════════
def portability():
    vendor = VendorPlatform(env={})
    c = vendor.cfg
    def a(op):
        r = vendor.request_for(op)
        return "%s %s" % (r["method"], r["url"].replace("https://", ""))
    return {
        "vendor_label": vendor.label,
        "operations": [
            {"op": "upsert_profile", "does": "Write or update a customer profile",
             "local": "INSERT … ON CONFLICT (SQLite)", "unomi": "POST /cxs/profiles",
             "vendor": a("upsert_profile"), "vendor_api": c["ingest_api"], "parity": "equivalent"},
            {"op": "get_profile", "does": "Read the profile at contact start",
             "local": "SELECT (SQLite)", "unomi": "GET /cxs/profiles/{id}",
             "vendor": a("get_profile"), "vendor_api": c["access_api"], "parity": "equivalent"},
            {"op": "record_event", "does": "Write an interaction, decision or outcome",
             "local": "INSERT (SQLite)", "unomi": "POST /cxs/context.json",
             "vendor": a("record_event"), "vendor_api": c["ingest_api"], "parity": "equivalent"},
            {"op": "events_for", "does": "Recent history for the agent's timeline",
             "local": "SELECT … ORDER BY ts", "unomi": "POST /cxs/events/search",
             "vendor": a("events_for"), "vendor_api": c["access_api"], "parity": "equivalent"},
            {"op": "audiences_for", "does": "Audience membership at decision time",
             "local": "Condition tree evaluated in-process", "unomi": "profileSegments on /cxs/context.json",
             "vendor": a("audiences_for"), "vendor_api": c["access_api"] + " · " + c["membership_field"], "parity": "equivalent"},
            {"op": "define_audience", "does": "Create an audience definition",
             "local": "Condition tree (JSON)", "unomi": "POST /cxs/segments",
             "vendor": a("define_audience"), "vendor_api": c["audience_api"] + " · " + c["query_type"], "parity": "equivalent"},
        ],
        "gaps": [
            {"capability": "Identity stitching across devices and channels",
             "here": "One identity per profile, merged by key", "vendor": c["gap_identity"], "parity": "weaker"},
            {"capability": "Propensity modelling",
             "here": "The Frontier's own logistic model", "vendor": c["gap_models"], "parity": "different"},
            {"capability": "Data governance labels and policy enforcement",
             "here": "Consent checked in the engine's guardrails", "vendor": c["gap_governance"], "parity": "not covered"},
            {"capability": "Activation to destinations",
             "here": "Journey and case stand-ins, in-process", "vendor": c["gap_activation"], "parity": "not covered"},
        ],
        "sources": [s for s in [brand.pack().get("schema_source"),
                                {"name": "Apache Unomi", "url": "https://unomi.apache.org", "licence": "Apache 2.0"}] if s],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  SELECTION
# ══════════════════════════════════════════════════════════════════════════════
_platform = None


def get_platform():
    """CUSTOMER_PLATFORM = local (default) | unomi | auto | vendor.
    `auto` uses Unomi when it answers and the built-in store when it does not, so a
    stopped container can never take the demo down."""
    global _platform
    if _platform is not None:
        return _platform
    want = os.environ.get("CUSTOMER_PLATFORM", "local").lower()
    if want in ("unomi", "auto"):
        u = UnomiPlatform()
        if u.reachable():
            try:
                u.prepare()
                _platform = u
                return _platform
            except Exception as ex:
                print("  [cdp] Unomi answered but setup failed: %s — using the built-in store" % ex)
        elif want == "unomi":
            print("  [cdp] Unomi not reachable at %s — using the built-in store" % u.base)
    if want == "vendor":
        v = VendorPlatform()
        if not v.missing:
            _platform = v
            return _platform
        print("  [cdp] %s not configured (missing %s) — using the built-in store" % (v.label, ", ".join(v.missing)))
    _platform = LocalPlatform()
    return _platform
