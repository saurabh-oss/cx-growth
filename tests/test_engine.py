"""
Engine tests — the claims the demo makes, checked.

    python -m unittest discover -s tests -v

No server, no network, no API key. Runs in a few seconds.
"""
import copy, os, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import brand

brand.install()                  # before any other module from backend/

import catalogue as cat
import cdp
import demo_profiles as dp
import frontdoor as fd
import frontier_engine as fe
import journey as jn
import knowledge as kb
import learning
import nlu
import quality as qa
import simulation as sim
from scenarios import SCENARIOS, SCALE_MODEL

T = cdp.TENANT
SC = {s["id"]: s for s in SCENARIOS}


def decide(sid, **changes):
    p = copy.deepcopy(dp.PROFILES[sid])
    ctx = dict(dp.CONTEXTS[sid])
    for path, value in changes.items():
        if path == "intent":
            ctx["intent"] = value
        else:
            cdp.set_path(p, path.replace("__", "."), value)
    return fe.decide(p, ctx)


class DemoContacts(unittest.TestCase):
    """The guided demo depends on these nine decisions. If a weight change moves one,
    this fails before a presenter finds out in front of an audience."""

    def test_every_contact_gets_the_decision_the_script_expects(self):
        for sid, note in fd.NOTES.items():
            with self.subTest(contact=sid):
                self.assertEqual(fe.decide(dp.PROFILES[sid], dp.CONTEXTS[sid])["decision"], note["expect"])

    def test_every_scenario_has_a_profile_a_context_and_a_note(self):
        for s in SCENARIOS:
            with self.subTest(contact=s["id"]):
                self.assertIn(s["id"], dp.PROFILES)
                self.assertIn(s["id"], dp.CONTEXTS)
                self.assertIn(s["id"], fd.NOTES)

    def test_computed_offer_value_matches_the_scripted_lead(self):
        for s in SCENARIOS:
            lead = s["ai_analysis"].get("lead_summary")
            if not lead:
                continue
            with self.subTest(contact=s["id"]):
                d = fe.decide(dp.PROFILES[s["id"]], dp.CONTEXTS[s["id"]])
                self.assertIsNotNone(d["offer"], "engine matched no offer")
                self.assertEqual(d["offer"]["estimated_value"], lead["estimated_value"])
                self.assertEqual(d["offer"]["type"], lead["type"])

    def test_elena_clears_the_threshold_and_is_overridden(self):
        d = decide("elena-double-charge")
        self.assertGreaterEqual(d["propensity_raw"], fe.THRESHOLD)
        self.assertEqual(d["segment"], "recovery")
        self.assertEqual(d["decision"], "solve")
        self.assertIsNotNone(d["override"])
        self.assertIsNone(d["offer"])

    def test_robert_is_nowhere_near_the_threshold(self):
        self.assertLess(decide("robert-signin")["propensity_raw"], 0.15)

    def test_cross_cloud_offers_cross_clouds(self):
        self.assertTrue(decide("ravi-creative-to-experience")["offer"]["offer"]["crosses_cloud"])
        self.assertTrue(decide("lucia-sign-contracts")["offer"]["offer"]["crosses_cloud"])
        self.assertFalse(decide("priya-individual-to-teams")["offer"]["offer"]["crosses_cloud"])


class Guardrails(unittest.TestCase):
    """Guardrails are code. Each one must turn a SELL into a SOLVE on its own."""

    def test_baseline_is_sell(self):
        self.assertEqual(decide("aisha-storage-full")["decision"], "sell")

    def test_no_marketing_consent(self):
        d = decide("aisha-storage-full", **{"consents__marketing__any__val": "n"})
        self.assertEqual(d["decision"], "solve")
        self.assertEqual(d["held_by"], "consent")

    def test_offer_cooldown(self):
        recent = cdp.iso(datetime.now(timezone.utc) - timedelta(days=10))
        d = decide("aisha-storage-full", **{T + "__commercial__lastOfferDate": recent})
        self.assertEqual(d["decision"], "solve")
        self.assertEqual(d["held_by"], "cooldown")

    def test_cooldown_expires(self):
        old = cdp.iso(datetime.now(timezone.utc) - timedelta(days=fe.OFFER_COOLDOWN_DAYS + 1))
        self.assertEqual(decide("aisha-storage-full", **{T + "__commercial__lastOfferDate": old})["decision"], "sell")

    def test_commercial_hold(self):
        until = cdp.iso(datetime.now(timezone.utc) + timedelta(days=5))
        self.assertEqual(decide("aisha-storage-full", **{T + "__commercial__suppressedUntil": until})["decision"], "solve")

    def test_a_brand_pack_changes_names_and_nothing_else(self):
        self.assertEqual(brand.apply("no placeholder in this sentence"), "no placeholder in this sentence")
        for k, v in (brand.pack().get("names") or {}).items():
            with self.subTest(name=k):
                self.assertEqual(brand.apply(k), v)
                self.assertEqual(brand.apply("x" + k + "y"), "x" + k + "y", "must match whole words only")

    def test_open_case_on_a_repeat_contact_is_service_recovery(self):
        d = decide("aisha-storage-full", **{T + "__service__openCaseCount": 1, T + "__service__repeatContact7d": True})
        self.assertEqual((d["segment"], d["decision"]), ("recovery", "solve"))

    def test_transactional_intent_is_never_sold_to(self):
        d = decide("priya-individual-to-teams", intent="account.access")
        self.assertEqual((d["segment"], d["decision"]), ("access", "solve"))

    def test_resolving_the_failure_lifts_the_override(self):
        d = decide("elena-double-charge", intent="plan.compare", **{
            T + "__service__openCaseCount": 0, T + "__service__openCases": [],
            T + "__service__repeatContact7d": False, T + "__service__duplicateChargeFlag": False})
        self.assertEqual(d["decision"], "sell")

    def test_no_offer_is_ever_made_into_service_recovery_across_a_whole_day(self):
        s = sim.summarise(learning.day(0), fe.BASELINE, fe.THRESHOLD)
        self.assertGreater(s["guardrails"]["recovery_contacts"], 100)
        self.assertEqual(s["guardrails"]["recovery_offers_made"], 0)


class Model(unittest.TestCase):
    def test_contributions_explain_the_score(self):
        xs, reads = fe.extract(dp.PROFILES["aisha-storage-full"], dp.CONTEXTS["aisha-storage-full"])
        z = fe.BASELINE["bias"] + sum(fe.BASELINE["weights"][k] * xs[k] for k in fe.FEATURE_IDS)
        self.assertAlmostEqual(fe.sigmoid(z), fe.propensity(xs, fe.BASELINE), places=9)
        self.assertAlmostEqual(sum(c["weight"] for c in fe.contributions(xs, reads, fe.BASELINE, top=99)), 1.0, delta=0.06)

    def test_raising_the_threshold_routes_fewer_and_more_precisely(self):
        rows = sim.sweep(learning.day(0), fe.BASELINE, thresholds=[0.4, 0.55, 0.7, 0.85])
        self.assertEqual([r["sell_treated"] for r in rows], sorted((r["sell_treated"] for r in rows), reverse=True))
        self.assertEqual([r["precision"] for r in rows], sorted(r["precision"] for r in rows))

    def test_simulation_lands_near_the_business_case(self):
        r = sim.summarise(learning.day(0), fe.BASELINE, fe.THRESHOLD, SCALE_MODEL)["rates"]
        self.assertAlmostEqual(r["triage"], SCALE_MODEL["triage_rate"], delta=0.03)
        self.assertAlmostEqual(r["capture"], SCALE_MODEL["capture_rate"], delta=0.05)
        self.assertAlmostEqual(r["conversion"], SCALE_MODEL["conversion_rate"], delta=0.05)
        self.assertAlmostEqual(r["avg_value"], SCALE_MODEL["avg_value"], delta=40)

    def test_simulation_is_reproducible(self):
        a = sim.summarise(sim.Day(daily_contacts=1500), fe.BASELINE, 0.55)["funnel"]
        b = sim.summarise(sim.Day(daily_contacts=1500), fe.BASELINE, 0.55)["funnel"]
        self.assertEqual(a, b)

    def test_challenger_beats_champion_on_unseen_traffic(self):
        learning.reset()
        c = learning.train()
        ev = c["evaluation"]
        self.assertGreater(ev["challenger"]["auc"], ev["champion"]["auc"])
        self.assertLessEqual(ev["challenger"]["brier"], ev["champion"]["brier"])
        self.assertGreater(c["verdict"]["extra_opportunities"], 0)
        # It found what was planted: third-party spend is worth more than the champion thinks.
        self.assertGreater(c["weights"]["thirdparty"], fe.BASELINE["weights"]["thirdparty"] + 0.5)

    def test_promotion_is_explicit_and_reversible(self):
        learning.reset()
        self.assertEqual(learning.champion()["version"], "v1")
        learning.train()
        self.assertEqual(learning.champion()["version"], "v1", "training must not change the champion")
        learning.promote()
        self.assertEqual(learning.champion()["version"], "v2")
        learning.reset()
        self.assertEqual(learning.champion()["weights"], fe.BASELINE["weights"])


class Platform(unittest.TestCase):
    """The conformance suite. Any adapter that passes it can stand behind the engine.
    Runs against the built-in store always, and against Apache Unomi when it is up."""

    def adapters(self):
        out = [cdp.LocalPlatform(os.path.join(tempfile.mkdtemp(), "t.db"))]
        u = cdp.UnomiPlatform()
        if u.reachable():
            out.append(u)
        return out

    def test_conformance(self):
        for p in self.adapters():
            with self.subTest(adapter=p.key):
                prof = copy.deepcopy(dp.PROFILES["priya-individual-to-teams"])
                prof["_id"] = "conformance-" + p.key
                prof["identityMap"]["CRMID"][0]["id"] = prof["_id"]
                p.upsert_profile(prof)
                got = p.get_profile(prof["_id"])
                self.assertEqual(got[T]["usage"]["distinctUsers30d"], 3, "profile did not round-trip")
                self.assertEqual(got["identityMap"]["CRMID"][0]["id"], prof["_id"])

                ev = cdp.event_doc("contactCentre.treatmentDecided", prof["_id"],
                                   {"decision": "SELL", "propensity": 0.9}, channel="voice")
                p.record_event(prof["_id"], ev)
                if p.key == "unomi":
                    import time
                    time.sleep(1.5)                    # Elasticsearch refresh interval
                events = p.events_for(prof["_id"])
                self.assertIn(ev["_id"], [e["_id"] for e in events])
                self.assertEqual(events[0]["eventType"], "contactCentre.treatmentDecided")

                self.assertIn("licence-outgrown", p.audiences_for(prof["_id"]))
                self.assertNotIn("service-recovery", p.audiences_for(prof["_id"]))

                p.patch_profile(prof["_id"], {T + ".commercial.lastOfferDate": cdp.iso()})
                self.assertTrue(p.get_profile(prof["_id"])[T]["commercial"]["lastOfferDate"])

    def test_the_engine_gets_the_same_answer_from_a_stored_profile(self):
        for p in self.adapters():
            with self.subTest(adapter=p.key):
                dp.seed(p, "elena-double-charge")
                stored = p.get_profile(dp.PROFILE_ID["elena-double-charge"])
                a = fe.decide(stored, dp.CONTEXTS["elena-double-charge"])
                b = fe.decide(dp.PROFILES["elena-double-charge"], dp.CONTEXTS["elena-double-charge"])
                self.assertEqual((a["decision"], a["segment"], a["propensity"]), (b["decision"], b["segment"], b["propensity"]))

    def test_one_audience_definition_renders_three_ways(self):
        for a in cdp.AUDIENCES:
            with self.subTest(audience=a["id"]):
                self.assertTrue(cdp.to_query(a["condition"]))
                self.assertIn(cdp.to_unomi(a["condition"])["type"], ("booleanCondition", "profilePropertyCondition"))
        lic = next(a for a in cdp.AUDIENCES if a["id"] == "licence-outgrown")
        self.assertEqual(cdp.to_query(lic["condition"]),
                         '%s.entitlement.licenceType = "INDIVIDUAL" and %s.usage.distinctUsers30d >= 2' % (T, T))
        self.assertTrue(cdp.evaluate(lic["condition"], dp.PROFILES["priya-individual-to-teams"]))
        self.assertFalse(cdp.evaluate(lic["condition"], dp.PROFILES["aisha-storage-full"]))

    def test_vendor_requests_carry_the_same_document(self):
        vendor = cdp.VendorPlatform(env={})
        prof = dp.PROFILES["aisha-storage-full"]
        r = vendor.request_for("upsert_profile", prof["_id"], prof)
        self.assertEqual(r["body"]["body"][vendor.cfg["entity_field"]], prof)
        self.assertIn("/collection/", r["url"])
        self.assertTrue(vendor.missing, "an unconfigured adapter must say so")
        with self.assertRaises(RuntimeError):
            vendor.get_profile("x")


class Conversation(unittest.TestCase):
    def test_rules_engine_agrees_with_the_curated_outcome_on_every_scripted_contact(self):
        ts = {sid: fd.treatment_for(sid) for sid in dp.PROFILES}
        ev = nlu.evaluation(SCENARIOS, ts)
        self.assertEqual(ev["outcome_agreement"], ev["contacts"], [r for r in ev["rows"] if not r["agree"]])
        self.assertGreaterEqual(ev["recall"], 0.85)

    def test_a_failure_raised_in_conversation_stands_the_engine_down(self):
        t = fd.treatment_for("marcus-generative-credits")
        a = nlu.analyse([{"role": "customer", "text": "I've been charged twice. I rang last week and nothing has "
                                                       "happened. I want a refund."}], t)
        self.assertFalse(a["routed"])
        self.assertEqual(a["stage"], "suppressed")
        self.assertFalse(a["qualified"])

    def test_small_talk_does_not_qualify_a_lead(self):
        t = fd.treatment_for("aisha-storage-full")
        a = nlu.analyse([{"role": "customer", "text": "Hello, how are you today?"}], t)
        self.assertFalse(a["qualified"])
        self.assertEqual(a["signals"], [])

    def test_a_contact_treated_solve_never_qualifies(self):
        t = fd.treatment_for("robert-signin")
        a = nlu.analyse([{"role": "customer", "text": "My storage is full, I shoot weddings, whatever it takes, "
                                                       "how much would it cost to upgrade before Saturday?"}], t)
        self.assertFalse(a["qualified"])


class Agents(unittest.TestCase):
    def conv(self, sid):
        return [{"role": m["role"], "text": m.get("text_en") or m["text"]} for m in SC[sid]["conversation"]]

    def test_quality_scores_every_scripted_contact_without_a_breach(self):
        for s in SCENARIOS:
            with self.subTest(contact=s["id"]):
                t = fd.treatment_for(s["id"])
                q = qa.score(self.conv(s["id"]), t, s["ai_analysis"]["sentiment_progression"],
                             lead_captured=t["decision"] == "sell", auth=dp.CONTEXTS[s["id"]]["auth"])
                self.assertEqual(q["compliance"], "pass")
                self.assertGreaterEqual(q["overall"], 70)

    def test_quality_catches_an_offer_made_into_service_recovery(self):
        conv = self.conv("elena-double-charge") + [
            {"role": "agent", "text": "While I have you — there's an option that gives you more storage. Shall I upgrade you?"}]
        q = qa.score(conv, fd.treatment_for("elena-double-charge"), [0.12, 0.2], auth="VERIFIED")
        self.assertEqual(q["compliance"], "breach")
        self.assertLess(q["overall"], 50)

    def test_quality_catches_pressure_language(self):
        conv = self.conv("aisha-storage-full") + [
            {"role": "agent", "text": "This is a limited time price, you need to decide today only."}]
        q = qa.score(conv, fd.treatment_for("aisha-storage-full"), [0.4], lead_captured=True)
        self.assertEqual(q["compliance"], "breach")

    def test_knowledge_retrieves_the_right_article(self):
        for q, want in [("my colleague keeps getting signed out", "KB-1020"),
                        ("storage is full and photos stopped syncing", "KB-1002"),
                        ("I was charged twice and want a refund", "KB-1050"),
                        ("clients need to sign the contract", "KB-1080")]:
            with self.subTest(query=q):
                self.assertEqual(kb.search(q, 1)[0]["id"], want)

    def test_self_service_answers_what_it_can_and_hands_over_what_it_cannot(self):
        self.assertTrue(kb.self_service("I forgot my password and can't sign in")["resolved"])
        r = kb.self_service("I have been charged twice this month")
        self.assertFalse(r["resolved"])
        self.assertEqual(r["handoff"]["suggested_intent"], "billing.dispute")
        self.assertFalse(kb.self_service("zxqv plorp")["resolved"])

    def test_the_outcome_changes_the_next_decision(self):
        sid = "priya-individual-to-teams"
        t = fd.treatment_for(sid)
        plan = jn.plan(sid, dp.PROFILES[sid], dp.CONTEXTS[sid], t,
                       {"disposition": "Upgrade accepted", "lead": SC[sid]["ai_analysis"]["lead_summary"], "talk_seconds": 90})
        self.assertIn("leadOperation.newLead", [e["eventType"] for e in plan["events"]])
        nxt = jn.next_contact(dp.PROFILES[sid], plan["changes"], dp.CONTEXTS[sid], fe.BASELINE, fe.THRESHOLD)
        self.assertEqual(nxt["decision"], "solve")
        self.assertEqual(nxt["blocked_id"], "cooldown")

    def test_service_recovery_places_a_hold_and_raises_a_case(self):
        sid = "elena-double-charge"
        plan = jn.plan(sid, dp.PROFILES[sid], dp.CONTEXTS[sid], fd.treatment_for(sid),
                       {"disposition": "Issue resolved", "lead": None, "talk_seconds": 80})
        self.assertEqual(plan["case"]["number"], "CASE-40217")
        self.assertIn("commerce.holdApplied", [e["eventType"] for e in plan["events"]])
        nxt = jn.next_contact(dp.PROFILES[sid], plan["changes"], {**dp.CONTEXTS[sid], "intent": "plan.compare"},
                              fe.BASELINE, fe.THRESHOLD)
        self.assertEqual(nxt["decision"], "solve")
        self.assertEqual(nxt["blocked_id"], "suppression")

    def test_offers_are_arithmetic_on_the_price_list(self):
        self.assertEqual(round(cat.annual("PHOTO_1TB") - cat.annual("PHOTO_20GB")), 120)
        self.assertEqual(round(cat.annual("CC_TEAMS", 3) - cat.annual("CC_ALL_APPS")), 2520)
        self.assertEqual(round(cat.annual("CC_ALL_APPS") - cat.annual("PHOTO_1TB")), 480)


if __name__ == "__main__":
    unittest.main(verbosity=2)
