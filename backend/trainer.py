"""
TRAINING MODE — the agent practises; the engine plays the customer.

In the demo, someone in the room plays the customer and the engine advises the agent. In
training it is the other way round: a human agent takes a mock call, speaks, and a
customer PERSONA answers — in character, in audio, and with everything the live
workspace does (signals, score, guidance) happening in real time behind it.

    agent speaks ─▶ what did they just do? ─▶ persona reacts ─▶ engine analyses ─▶ debrief

The persona is built from a demo contact. Its narrative is the customer's side of the
scripted conversation; what unlocks each line is what the scripted agent did at that
point — classified by the same detector the trainee's words go through. So a trainee who
does what a good agent does moves the call forward, and one who does not gets a customer
who stalls, pushes back, or — if sold to in the middle of a complaint — gets angry.

This is a rules engine, like the conversation engine it sits beside: no key, no network,
works in any room. With ANTHROPIC_API_KEY set, Claude can voice the persona's lines so
they answer the agent's exact words; the rules still decide what the customer does.
"""
import re, uuid

import cdp
import demo_profiles as dp
import frontdoor as fd
import nlu
import quality
from scenarios import SCENARIOS

SCENARIO_BY_ID = {s["id"]: s for s in SCENARIOS}

# ══════════════════════════════════════════════════════════════════════════════
#  WHAT THE AGENT JUST DID — the moves a service agent makes, as patterns
# ══════════════════════════════════════════════════════════════════════════════
MOVES = {
    "greet": [r"\b(hi|hello|hey|good (morning|afternoon|evening))\b", r"thanks? for (calling|getting in touch|holding|waiting)",
              r"how can i help", r"you'?re (speaking|through) (to|with)", r"my name'?s? (is )?\w+", r"\bspeaking\b"],
    "empathy": quality.EMPATHY + [r"i (appreciate|can imagine|hear you|do understand)", r"i apologi[sz]e", r"apologies",
                                  r"that('s| is| must be| sounds) (really |very )?(frustrating|annoying|not good|not right|awful|a pain)",
                                  r"shouldn'?t (have )?(happened|be happening|still be)", r"not acceptable", r"let'?s get (this|that|it) (sorted|fixed|put right)"],
    "verify": quality.VERIFY + [r"for security", r"(can|could|may) (i|you) (just )?(take|confirm|have|check) (your|the) (email|e-mail|date of birth|postcode|phone|account|name|address)",
                                r"(confirm|check) (the )?(email|e-mail|address|date of birth|postcode) (on|we have on) (the|your) account", r"security question"],
    "diagnose": quality.DIAGNOSE + [r"\?", r"(can|could|may) i (just )?(ask|check|take a look|have a look|look)",
                                    r"let me (just )?(check|look|see|take a look|pull up|bring up|have a look)", r"i'?m (just )?(looking|checking|seeing|pulling)",
                                    r"tell me (a bit |a little )?more", r"(looking|checking) (at|on|into) (your|the) account",
                                    r"\b(how many|how often|how long|how much|which|when did|what (do|are|happens?|kind))\b"],
    "explain": [r"\bbecause\b", r"(that'?s|that is|which is|this is|here'?s) (why|what'?s (happening|causing|going on))",
                r"what'?s (happening|going on) (here|is)", r"the reason", r"it means", r"(so|which|that) (means|explains)",
                r"that explains", r"the (problem|issue|cause) (is|here)", r"you'?ve (hit|reached|run out|filled|used)",
                r"licen[cs]e (covers|is for|allows|only|is meant)", r"(covers|is for) one (person|user|machine)", r"(is|are) (full|at the limit|at 100)",
                r"not a (fault|glitch|bug)", r"(it'?s|that'?s) (actually )?(a )?(limit|ceiling|licen[cs]e|plan) (issue|thing|matter|question)"],
    "fix": quality.RESOLVE + [r"i'?(ve|ll|m going to|m) (process|refund|reset|apply|send|sort|fix|escalat|rais|put|set|arrang|activat|restor|updat|credit|waiv|clear|enabl|unlock|extend)\w*",
                              r"(processing|refunding|resetting|escalating|raising|arranging|applying|activating) (that|this|the|it|a|your)",
                              r"(that'?s|that is|it'?s|it is) (now )?(done|sorted|processed|applied|fixed|through|on its way|back on)",
                              r"(you'?ll|you will|you should) (get|have|receive|see|be able)", r"(within|in) (the next )?(\d+|a few|two|three|five|ten|twenty|24|48) (minutes?|hours?|days?)",
                              r"straight back (in|on)", r"i'?ve (just )?(done|processed|refunded|reset|sent|applied|raised|cleared|unlocked)",
                              r"(let me|i'?ll) (get|put) (that|this|it) (sorted|fixed|right)", r"\breference\b", r"(written )?confirmation", r"put (it|this|that) right"],
    # Naming a product is not an offer. Proposing one is.
    "offer": quality.OFFER + [r"\bupgrad(e|ing)\b", r"there'?s (an? )?(option|plan|version|tier|package)", r"(move|moving|switch|switching) (you )?(over )?(to|onto|up to)",
                              r"(add|adding) (on )?(storage|credits|seats|licen[cs]es|a licen[cs]e)",
                              r"(start|set up|activate|try) (a |the )?(free )?trial", r"(i can|we can|i could|we could) (set|get) (you|that) (up|on|onto)",
                              r"(would|might) (suit|work for|be worth) you", r"\brecommend", r"(an|the|another|one) option (that|would|which|is)",
                              r"(bigger|larger|higher|different) (plan|tier|package)", r"(shall|should|can) i (upgrade|move|switch|set) you"],
    "price": [r"\$ ?\d", r"£ ?\d", r"\d+ ?(dollars|pounds|quid)", r"(a|per) (month|year|seat|user)\b", r"\bmonthly\b", r"\bannually\b", r"(costs?|price|priced) ", r"more a month"],
    "pressure": quality.PRESSURE + [r"(only|just) (today|this week|for the next)", r"if you don'?t (upgrade|buy|decide|act|take)",
                                    r"(strongly|really) (recommend|urge|suggest) you (to )?(buy|upgrade|take|go for)", r"you (really )?(need|have|ought) to (buy|upgrade|take|get)",
                                    r"(before|or) (the|this) (price|offer|deal) (goes up|ends|expires)", r"\bdiscount\b", r"\b\d+ ?% off\b"],
    "close": [r"anything else", r"(have a|enjoy your) (good|great|lovely|nice|wonderful) (day|evening|weekend|afternoon|shoot|rest)",
              r"thanks? for your (time|patience|call)", r"\b(goodbye|bye|take care|cheers)\b", r"all (sorted|done|set)( then)?",
              r"(is|was) there anything (else|more)", r"glad (i|we) could help", r"that'?s everything"],
    # Active listening: playing back what the customer said. Progress in its own right.
    "reflect": [r"\bso (this|that|it|you|the)\b", r"sounds like", r"in other words", r"what you'?re (saying|describing|telling me)",
                r"if i'?ve (got|understood) (that|this) right", r"that explains"],
    "hold": [r"bear with me", r"\b(one|a|just a) (moment|second|sec|minute|mo)\b", r"(hold|hang) on", r"(pop|put) you on hold"],
}
_MOVES = {k: [re.compile(p, re.I) for p in v] for k, v in MOVES.items()}

# A move is also progress when the scripted agent made it at this point. These are
# progress on their own merits: they take the call somewhere.
PROGRESS = {"diagnose", "explain", "fix", "reflect"}
MOOD_LABEL = [(0.3, "upset"), (0.45, "wary"), (0.6, "neutral"), (0.75, "warming"), (1.01, "pleased")]

DIFFICULTY = [
    {"id": "steady", "label": "Steady", "objections": 0,
     "blurb": "A cooperative customer. Say the right things and the call flows."},
    {"id": "testing", "label": "Testing", "objections": 1,
     "blurb": "Asks one hard question before agreeing to anything, and notices when you stall."},
    {"id": "tough", "label": "Tough", "objections": 2,
     "blurb": "Two objections, a shorter fuse, and no credit for vague answers."},
]
DIFF = {d["id"]: d for d in DIFFICULTY}


_GREETING_QUESTION = re.compile(r"how (can|may) i help|what can i do for you|how are you", re.I)


def moves(text):
    """The set of moves in one agent utterance."""
    t = " " + (text or "").strip() + " "
    out = {k for k, pats in _MOVES.items() if any(p.search(t) for p in pats)}
    # "How can I help?" is a greeting with a question mark, not a diagnosis: unless some
    # other diagnostic phrase is present, or a second question is asked, it does not count.
    if "diagnose" in out and _GREETING_QUESTION.search(t) and t.count("?") <= 1 \
            and not any(p.search(t) for p in _MOVES["diagnose"] if p.pattern != r"\?"):
        out.discard("diagnose")
    return out


def mood_label(m):
    return next(l for lim, l in MOOD_LABEL if m < lim)


def focus_for(sc, t):
    """What this persona is for — the one thing it teaches."""
    if t.get("override") or t.get("segment") == "recovery":
        return "Service recovery — make no offer, however likely the sale looks"
    if t["decision"] == "solve":
        return "A fast, clean fix — and verify identity before changing anything" if dp.CONTEXTS[sc["id"]]["auth"] != "VERIFIED" \
            else "A fast, clean fix — nothing to sell here"
    kind = (t.get("offer") or {}).get("type", "")
    if kind == "Retention":
        return "Save the customer without a discount — find the plan that fits"
    if (t.get("offer") or {}).get("offer", {}).get("crosses_cloud"):
        return "Hear a need outside the customer's suite, and refer it — do not quote"
    if sc.get("translation"):
        return "Solve, then offer — the persona speaks English here; the demo call is translated"
    return "Solve first, then offer the one thing that fits"


# ══════════════════════════════════════════════════════════════════════════════
#  THE PERSONA — a customer, built from a demo contact
# ══════════════════════════════════════════════════════════════════════════════
class Persona:
    def __init__(self, scenario_id, treatment, difficulty="steady"):
        sc = SCENARIO_BY_ID[scenario_id]
        self.sc, self.t = sc, treatment
        self.profile = dp.PROFILES[scenario_id]
        self.ctx = dp.CONTEXTS[scenario_id]
        self.first = (self.profile.get("person", {}).get("name", {}).get("firstName")) or "there"
        self.email = (self.profile.get("personalEmail") or {}).get("address") or ""
        self.difficulty = DIFF.get(difficulty, DIFF["steady"])
        conv = sc["conversation"]
        self.beats = []
        for i, m in enumerate(conv):
            if m["role"] != "customer":
                continue
            nxt = next((x for x in conv[i + 1:] if x["role"] == "agent"), None)
            self.beats.append({"say": m.get("text_en") or m["text"],
                               "expect": sorted(moves(nxt["text"]) - {"greet", "hold", "price"}) if nxt else []})
        self.model_answer = [m["text"] for m in conv if m["role"] == "agent"]
        # The point in the script where an offer became appropriate.
        self.offer_beat = next((i for i, b in enumerate(self.beats) if "offer" in b["expect"]), len(self.beats))
        self.sell = treatment["decision"] == "sell" and not treatment.get("override")
        self.recovery = bool(treatment.get("override")) or treatment.get("segment") == "recovery"
        offer = treatment.get("offer") or {}
        words = []
        for p in (offer.get("offer") or {}).get("to", []):
            words += re.findall(r"[A-Za-z0-9]+", p.get("product", ""))
        self.offer_words = {w.lower() for w in words if len(w) > 2 and w.lower() not in ("for", "the", "and", "with", "plan", "cloud")}
        prog = sc.get("ai_analysis", {}).get("sentiment_progression") or [0.5]
        self.mood = float(prog[0])
        self.moods = [round(self.mood, 2)]
        self.beat = 0
        self.stalls = 0
        self.objections_left = self.difficulty["objections"]
        self.verified = self.ctx["auth"] == "VERIFIED"
        self.accepted = False
        self.resolved = False       # the customer has said everything they called to say
        self.ended = False
        self.flags = []             # things worth remembering for the debrief
        self.turns = 0

    # -- small helpers
    def _bump(self, d):
        self.mood = max(0.05, min(0.95, self.mood + d))

    def _flag(self, f):
        if f not in self.flags:
            self.flags.append(f)

    def opening(self):
        return self.beats[0]["say"] if self.beats else "Hello?"

    def state(self):
        return {"mood": round(self.mood, 2), "mood_label": mood_label(self.mood), "beat": self.beat,
                "beats": len(self.beats), "verified": self.verified, "accepted": self.accepted,
                "resolved": self.resolved, "ended": self.ended, "flags": list(self.flags)}

    # -- the customer's turn
    def respond(self, text, agent_moves=None):
        """What the customer says back, and why. Returns {text, mood, mood_label, ended, why}."""
        m = agent_moves if agent_moves is not None else moves(text)
        self.turns += 1
        upset = self.mood < 0.4
        out = None
        why = ""

        if self.ended:
            return self._say("Thanks again. Bye now.", "ended")
        if len((text or "").split()) < 2:
            self._bump(-0.03)
            return self._say("Hello? Are you still there?", "silence")

        if "pressure" in m:
            self._flag("pressure")
            self._bump(-0.25)
            return self._say("Please don't pressure me. I'm not deciding anything on the spot — I just want this sorted.", "pressure")

        prefix = ""
        if "verify" in m and not self.verified:
            self.verified = True
            # "That's you verified" means the details were already given; a question means they were asked for.
            if not re.search(r"\bverified\b|that'?s you\b", text, re.I):
                prefix = "Sure — it's %s, and the email is %s. " % (cdp.full_name(self.profile), self.email or "the one on the account")
        # A greeting is not a goodbye, whatever words it borrows.
        if self.turns == 1 or "greet" in m:
            m = m - {"close"}

        # An offer, and whether this was the moment for one.
        if "offer" in m:
            if self.recovery or not self.sell:
                self._flag("pitched_on_recovery" if self.recovery else "pitched_on_solve")
                self._bump(-0.3)
                line = ("Hang on. I've been charged twice, I've called twice, and you want to sell me something? "
                        "Absolutely not. Put it right first." if self.recovery else
                        "I didn't call to buy anything. Can we just fix what I rang about?")
                return self._say(prefix + line, "pitched_when_not_selling")
            if self.beat < self.offer_beat and not self.resolved:
                self._flag("pitched_early")
                self._bump(-0.15)
                return self._say(prefix + "Hold on — before anything else, can we sort out what I actually called about?", "pitched_early")
            if self.accepted:
                return self._say(prefix + "Yes, we've agreed that. Is there anything I need to do my end?", "already_accepted")
            # An offer that names nothing draws a question first — one of the harder customer's objections.
            if self.objections_left > 0 and self.offer_words and not any(w in text.lower() for w in self.offer_words) and "price" not in m:
                self.objections_left -= 1
                self._flag("vague_offer")
                self._flag("objection")
                return self._say(prefix + "What is it exactly? I don't want to be paying for things I won't use.", "objection")
            if self.objections_left > 0:
                self.objections_left -= 1
                objections = ["How much more is that a month?", "Will I lose anything I've already got?", "Can that be done today, or is there a wait?"]
                self._flag("objection")
                return self._say(prefix + objections[(self.difficulty["objections"] - self.objections_left - 1) % len(objections)], "objection")
            self.accepted = True
            self.resolved = True
            self._bump(0.2)
            self._flag("accepted")
            return self._say(prefix + ("That sounds like exactly what I need. Yes — let's do that." if not upset
                                       else "Fine. If that stops it happening again, let's do it."), "accepted")

        # Answering an objection counts: the customer asked, the agent replied.
        if self.flags and self.flags[-1] == "objection" and (m & {"price", "explain", "fix", "diagnose", "reflect"} or len(text.split()) >= 4):
            if self.objections_left > 0:
                self.objections_left -= 1
                return self._say(prefix + "And will I lose anything I've already got?", "objection")
            self.accepted = True
            self.resolved = True
            self._bump(0.2)
            self._flag("accepted")
            return self._say(prefix + "OK. That's fair — let's go ahead with it.", "accepted")

        if "close" in m:
            if self.resolved or self.accepted or (self.beat >= len(self.beats) - 1 and ("fix" in m or "fixed" in self.flags)):
                self.ended = True
                self.resolved = True
                self._bump(0.1)
                return self._say(prefix + ("Thank you, you've been really helpful. Bye." if self.mood >= 0.5 else "Right. Thanks. Bye."), "closed")
            self._flag("closed_early")
            self._bump(-0.1)
            return self._say(prefix + "Wait — we haven't actually sorted my problem yet.", "closed_early")

        # Progress through the story.
        want = set(self.beats[self.beat]["expect"]) if self.beat < len(self.beats) else set()
        substantive = len(text.split()) >= 6
        # Where the scripted agent made no detectable move — a reflective sentence — any
        # real sentence will do. Elsewhere the trainee has to do something the call needs.
        progress = bool(m & (want | PROGRESS)) or (not want and substantive) or (self.beat == 0 and "empathy" in m and upset)
        if "empathy" in m and "empathy" not in self.flags:
            self._flag("empathy")
            self._bump(0.08)
        if "explain" in m:
            self._bump(0.08)
        if "fix" in m:
            self._bump(0.12)
            self._flag("fixed")
        if progress or self.stalls >= 2:
            self.stalls = 0
            self.beat += 1
            if self.beat < len(self.beats):
                return self._say(prefix + self.beats[self.beat]["say"], "advanced")
            self.resolved = True
            if self.sell and not self.accepted:
                return self._say(prefix + "So… is there anything that would stop this happening again?", "inviting_offer")
            return self._say(prefix + ("OK. Thank you. So that's all sorted then?" if self.mood >= 0.45 else
                                       "Right. So it's dealt with — I won't have to call again?"), "waiting_to_close")

        self.stalls += 1
        self._bump(-0.08)
        self._flag("stalled")
        nudges = (["I've already explained that. Can you actually look at my account?",
                   "With respect, I don't need platitudes — I need this fixed.",
                   "Are you going to do something about it, or not?"] if upset else
                  ["Right — so what can you do about it?",
                   "OK. Can you have a look at my account?",
                   "Sorry, I'm not sure that answers it. What happens next?"])
        return self._say(prefix + nudges[(self.stalls - 1) % len(nudges)], "stalled")

    def _say(self, text, why):
        self.moods.append(round(self.mood, 2))
        return {"text": text, "mood": round(self.mood, 2), "mood_label": mood_label(self.mood), "ended": self.ended, "why": why}

    # -- what the trainee is being asked to do, and how they are doing
    def objectives(self, conversation):
        agent = [moves(m["text"]) for m in conversation if m["role"] == "agent"]
        first = agent[0] if agent else set()
        all_moves = set().union(*agent) if agent else set()
        negative_open = (self.sc.get("ai_analysis", {}).get("sentiment_progression") or [0.5])[0] < 0.4
        items = [{"id": "open", "label": "Open by acknowledging the customer", "done": bool(first & {"greet", "empathy"}),
                  "tip": "Use their name and show you heard the problem before anything else."}]
        if negative_open:
            items.append({"id": "empathy", "label": "Show you understand how they feel", "done": "empathy" in all_moves,
                          "tip": "One honest sentence — \"you're right, that shouldn't have happened\" — before any fixing."})
        if self.ctx["auth"] != "VERIFIED":
            items.append({"id": "verify", "label": "Verify identity before changing anything", "done": self.verified,
                          "tip": "The IVR challenge failed. Confirm their details before you touch the account."})
        items.append({"id": "diagnose", "label": "Find out what is really going on", "done": bool(all_moves & {"diagnose", "explain"}),
                      "tip": "Look at the account or ask a question. The customer's own words tell you what to offer, if anything."})
        items.append({"id": "fix", "label": "Put it right, or say exactly what happens next", "done": "fix" in all_moves,
                      "tip": "Say what you are doing — \"I'm processing that now, you'll have an email in five minutes.\""})
        if self.sell:
            items.append({"id": "offer", "label": "Offer the one thing that fits — after solving", "done": self.accepted,
                          "bad": "pitched_early" in self.flags,
                          "tip": "The engine found the fit: %s. Introduce it once the problem is understood, not before." % (
                              ((self.t.get("offer") or {}).get("offer") or {}).get("to", [{}])[0].get("product", "the recommended plan"))})
            items.append({"id": "pressure", "label": "No pressure, no discounting", "done": "pressure" not in self.flags, "bad": "pressure" in self.flags,
                          "tip": "If it fits, it sells itself. Urgency you manufacture costs trust."})
        else:
            items.append({"id": "hold", "label": "Make no offer on this call", "done": not any(f.startswith("pitched_on") for f in self.flags),
                          "bad": any(f.startswith("pitched_on") for f in self.flags),
                          "tip": "The engine decided this was not a selling moment. Honour it — the customer will remember."})
        items.append({"id": "close", "label": "Close with next steps", "done": self.ended and "closed_early" not in self.flags[-1:],
                      "tip": "Tell them what they will receive and when, then ask if there is anything else."})
        return items


# ══════════════════════════════════════════════════════════════════════════════
#  SESSIONS
# ══════════════════════════════════════════════════════════════════════════════
def options(model, threshold):
    people = []
    for sc in SCENARIOS:
        t = fd.treatment_for(sc["id"], model, threshold)
        people.append({"id": sc["id"], "name": sc["customer"]["name"], "role": sc["customer"]["role"],
                       "about": sc["description"], "intent": t["intent_label"], "segment": t["segment"],
                       "segment_name": t["segment_detail"]["name"], "tone": t["segment_detail"]["tone"],
                       "decision": t["decision"], "held": bool(t.get("override")), "focus": focus_for(sc, t),
                       "opening_mood": mood_label((sc.get("ai_analysis", {}).get("sentiment_progression") or [0.5])[0]),
                       "turns": sum(1 for m in sc["conversation"] if m["role"] == "customer")})
    return {"customers": people, "difficulties": DIFFICULTY}


def start(scenario_id, difficulty, model, threshold):
    t = fd.treatment_for(scenario_id, model, threshold)
    p = Persona(scenario_id, t, difficulty)
    return {"id": "train-" + uuid.uuid4().hex[:10], "persona": p, "treatment": t, "conversation": [], "hints": 0}


def debrief(session, hints_used=0, ended_by="agent"):
    p, t, conv = session["persona"], session["treatment"], session["conversation"]
    sentiments = nlu.analyse(conv, t, p.profile, p.ctx["intent"])["sentiments"] if conv else []
    q = quality.score(conv, t, sentiments=sentiments, lead_captured=p.accepted, auth=p.ctx["auth"])
    # The persona heard things the transcript patterns may not: an offer made into a complaint.
    pitched = any(f.startswith("pitched_on") for f in p.flags)
    if pitched and q["compliance"] == "pass":
        q["compliance"] = "breach"
        q["overall"] = min(q["overall"], 49)
        q["band"] = "Review"
        for sec in q["sections"]:
            if sec["id"] == "compliance":
                sec["status"] = "breach"
                sec["criteria"].append({"name": "No offer on a contact treated SOLVE", "pass": False, "weight": 3, "turn": None,
                                        "evidence": "The customer heard an offer and said so", "why": "The Frontier decided this contact was not a selling opportunity."})
        q["coaching_note"] = "Compliance breach: an offer was made on a contact the engine had held back."
    objectives = p.objectives(conv)
    missed = [o for o in objectives if not o["done"]]
    bad = [o for o in objectives if o.get("bad")]
    tips = [o["tip"] for o in bad + [o for o in missed if not o.get("bad")]][:3]
    if not tips:
        tips = ["Nothing to correct on this one. Try the same customer on a harder setting, or a different customer."]
    start_mood, end_mood = p.moods[0], p.moods[-1]
    verdict = ("The customer ended the call happier than they started it." if end_mood - start_mood >= 0.15 else
               "The customer felt about the same at the end as at the start." if abs(end_mood - start_mood) < 0.15 else
               "The customer ended the call less happy than they started it.")
    agent_turns = sum(1 for m in conv if m["role"] == "agent")
    return {
        "quality": q,
        "objectives": objectives,
        "done": sum(1 for o in objectives if o["done"]),
        "customer": {"name": p.sc["customer"]["name"], "mood_start": start_mood, "mood_end": end_mood, "moods": p.moods,
                     "label": mood_label(end_mood), "verdict": verdict, "accepted": p.accepted, "ended_by": ended_by},
        "flags": p.flags,
        "tips": tips,
        "turns": agent_turns,
        "hints_used": hints_used,
        "difficulty": p.difficulty,
        "focus": focus_for(p.sc, t),
        "model_answer": [{"role": m["role"], "text": m.get("text_en") or m["text"]} for m in p.sc["conversation"]],
        "engine": {"decision": t["decision"], "segment": t["segment_detail"]["name"], "propensity": t["propensity"],
                   "offer": (t.get("offer") or {}).get("recommended_action"), "override": t.get("override")},
    }
