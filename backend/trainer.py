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
import random, re, uuid

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
                              r"(let me|i'?ll) (get|put) (that|this|it) (sorted|fixed|right)", r"(send|give|email|text) you (a|the|your) reference",
                              r"(here'?s|your) reference( number)? is", r"(written )?confirmation", r"put (it|this|that) right",
                              r"(refer|hand|pass) (you|this|that) (over|on|to)", r"put you in touch", r"(arrange|book|set up|organi[sz]e) (a |the )?call ?back",
                              r"(call|ring|phone) you back", r"(get|ask) (the|our|a) \w+ (team|specialist|colleague)s? to"],
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
#  WHO THE CUSTOMER IS — voice, and the facts they would know
# ══════════════════════════════════════════════════════════════════════════════
# Each persona is written as a woman or a man in its script, so the voice is declared
# here, not guessed from a name. A customer without an entry gets a neutral default.
# pitch and rate are small offsets, so two customers sharing a system voice still differ.
VOICE = {
    "aisha-storage-full":          {"gender": "female", "pitch": 1.04, "rate": 1.03},
    "tom-cancel-save":             {"gender": "male",   "pitch": 0.96, "rate": 1.0},
    "nina-express-premium":        {"gender": "female", "pitch": 1.08, "rate": 1.06},
    "marcus-generative-credits":   {"gender": "male",   "pitch": 1.0,  "rate": 1.05},
    "robert-signin":               {"gender": "male",   "pitch": 0.9,  "rate": 0.95},
    "elena-double-charge":         {"gender": "female", "pitch": 0.97, "rate": 1.02},
    "priya-individual-to-teams":   {"gender": "female", "pitch": 1.0,  "rate": 1.04},
    "ravi-creative-to-experience": {"gender": "male",   "pitch": 0.94, "rate": 1.0},
    "lucia-sign-contracts":        {"gender": "female", "pitch": 1.06, "rate": 1.0},
}
DEFAULT_VOICE = {"gender": None, "pitch": 1.0, "rate": 1.0}

# What a customer knows about their own situation, so a question gets a real answer.
# Fictional, and consistent with each customer's script.
FACTS = {
    "aisha-storage-full": {
        "postcode": "M14 6HR", "dob": "the 3rd of May, 1994",
        "when": "It stopped syncing on Tuesday, I think. I only noticed yesterday.",
        "apps": "LightVault mostly, and PhotoForge when I want to do proper edits.",
        "people": "Just me.", "volume": "A wedding is two or three thousand raw files, easily.",
        "work": "Weddings for friends at weekends, mostly. It's turning into a proper side business.",
        "deadline": "Saturday. The wedding's on Saturday.", "device": "My phone, and a laptop at home.",
        "budget": "I'd rather not pay a fortune, but I need it working."},
    "tom-cancel-save": {
        "postcode": "BS6 5QT", "dob": "the 19th of November, 1988",
        "when": "I've been thinking about it for a couple of months. The renewal email was the last straw.",
        "apps": "PhotoForge and LightVault. That's it.", "people": "Just me.",
        "volume": "A few edits a week. Nothing huge.", "work": "Photos. It's a hobby that pays for itself now and then.",
        "budget": "I'm paying about {monthly} a month, and I use two apps.", "deadline": "Before it renews, ideally.",
        "device": "Just my desktop."},
    "nina-express-premium": {
        "postcode": "LS6 2DT", "dob": "the 8th of August, 1997",
        "when": "Every time I try to remove a background, basically. It's been weeks.",
        "apps": "Just Express. The free version.", "people": "Just me. It's my shop.",
        "volume": "Thirty-odd listings a month. More before Christmas.",
        "work": "I run a small shop on Etsy, and I make all my own listing images.",
        "deadline": "I've got new stock to list this week.", "device": "Mostly my laptop, sometimes my phone.",
        "budget": "If it's sensible, I'd pay. I just don't want stuff I won't use."},
    "marcus-generative-credits": {
        "postcode": "E8 3RL", "dob": "the 27th of January, 1991",
        "when": "Third month running. I run out about a week before they reset.",
        "apps": "PhotoForge mostly, and the generative fill all the time.", "people": "Just me.",
        "volume": "Dozens of variations a day when I'm making thumbnails.",
        "work": "Thumbnails and stills for my YouTube channel. It's how I earn a living.",
        "budget": "I already pay for a separate video tool, so I'm not against paying.",
        "deadline": "I've got an upload on Friday.", "device": "My PC."},
    "robert-signin": {
        "postcode": "SE15 4NB", "dob": "the 12th of June, 1975",
        "email": "It should be robert.nkemelu@example.com. Although I did change my email provider recently.",
        "when": "Since Monday. It just keeps saying my password's wrong.",
        "apps": "Just the photography plan. LightVault, mainly.", "people": "Just me.",
        "work": "It's for my own photos. Nothing professional.", "device": "My laptop.",
        "budget": "I don't want to buy anything, I just want to get in."},
    "elena-double-charge": {
        "postcode": "N16 0AS", "dob": "the 14th of February, 1983",
        "when": "Both charges came out on the 2nd. I rang last week, on the Tuesday.",
        "amount": "Sixty pounds. Twice.", "reference": "Nobody gave me a reference last time. That's half the problem.",
        "apps": "All of them, really. VectorForge and PageForge most days.", "people": "Just me.",
        "work": "I'm a designer. These are my working tools.",
        "budget": "I'm not buying anything until I've had my money back.",
        "deadline": "I just want it sorted this week.", "device": "My Mac."},
    "priya-individual-to-teams": {
        "postcode": "BN1 4GH", "dob": "the 30th of September, 1986",
        "when": "It's been getting worse since we took on our second designer. A couple of months.",
        "apps": "VectorForge, PhotoForge and PageForge, mostly.", "people": "Three of us now. Me and two designers.",
        "volume": "About a dozen clients on the go at any time.",
        "work": "We're a small design studio. Branding and packaging, mostly.",
        "budget": "If it's set up properly and I get a proper invoice, I'm happy to pay.",
        "deadline": "Today, ideally. Someone keeps getting kicked out mid-job.", "device": "Three laptops, two offices."},
    "ravi-creative-to-experience": {
        "postcode": "B1 1RS", "dob": "the 5th of March, 1980",
        "when": "It's been building for a year. Last month's campaign was the wake-up call.",
        "apps": "Studio Cloud for teams, eight seats. Express for the social stuff.",
        "people": "Eight on the creative side, more in marketing.",
        "volume": "About two hundred and forty product images a month, across four brands.",
        "work": "E-commerce. Four brands, all selling online.",
        "budget": "If it stops us publishing the wrong packaging, it's worth paying for.",
        "deadline": "Before our next seasonal launch. About six weeks.", "device": "All sorts. It's a whole team."},
    "lucia-sign-contracts": {
        "postcode": "28004. I'm in Madrid", "dob": "the 21st of July, 1990",
        "when": "It's been like this since I started freelancing, really.",
        "apps": "VectorForge. Just that one app.", "people": "Just me. I'm freelance.",
        "volume": "About fifteen contracts a month now.", "work": "I'm a freelance designer. Illustration, mostly.",
        "budget": "I already pay for a signature service I hardly use, so it would replace that.",
        "deadline": "I've got two contracts waiting right now.", "device": "My iPad and a laptop."},
}

# What the agent is asking about. Order matters: the first match leads the answer.
TOPICS = [
    ("hear", r"can you hear me|are you (still )?there|still with me"),
    ("name", r"(your|the) (full )?name\b|who am i (speaking|talking) (to|with)|who i'?m (speaking|talking) (to|with)"),
    ("dob", r"date of birth|\bdob\b|when were you born|birthday"),
    ("postcode", r"post ?code|zip ?code|first line of (your|the) address|your address"),
    # Asking for the address, not asking about it: "have you changed your email?" is not this.
    ("email", r"(what'?s|what is|confirm|take|have|give me|tell me|grab|read out|spell) (me )?(your|the) (e-?mail|email address)|"
              r"(e-?mail|email address) (on|for|we have on|registered to) (the|your) (account|file)"),
    ("reference", r"reference( number)?|case number|ticket number"),
    ("amount", r"how much (was|were) (it|the charges?|you charged)|what (was|is) the amount|how much did (it|they|we) (charge|take)"),
    ("when", r"when did (this|it|that|the problem|you first)|how long has (this|it|that) been|since when|when (was|did) (that|this|it) (start|happen)|when did you (notice|first)|"
             r"\bwhen\b.{0,30}\b(start(ed)?|happen(ed)?|notice(d)?|charged|c[oa]me out|go(ne)? out|went out|beg[au]n|first|appear(ed)?|taken)\b|what date"),
    ("apps", r"which (apps|products|tools|programs)|what (apps|products|tools|programs)|what do you (mainly |mostly |actually )?use\b(?! (it|them|that|this) for)|apps (do|are) you (use|using|need)"),
    ("people", r"how many (people|of you|users|staff|colleagues|designers|employees)|who (else )?(uses|is using)|just you\b|on your own|anyone else (use|using|on)"),
    ("volume", r"how many (images|photos|pictures|listings|contracts|assets|videos|files|clients|thumbnails|products|shoots)|how often|roughly how (many|much)|how much do you (use|shoot|make|create|sell)"),
    ("work", r"what do you (do|use (it|them|that) for)|what('?s| is) it for|what kind of (work|business)|what (line of )?(work|business)|is (this|it) for (work|business)"),
    ("deadline", r"when do you need|deadline|by when|how (soon|urgent)"),
    ("budget", r"budget|how much (are you|do you) (pay|paying)|what are you paying|price range|afford"),
    ("device", r"which device|what device|(phone|laptop|mac|pc|computer|tablet) or (your )?(phone|laptop|mac|pc|computer|tablet)|on (your|a) (phone|laptop|mac|pc|computer)"),
    ("tenure", r"how long have you been (with us|a customer)|been a customer for|how long (have you|you'?ve) (had|been using)"),
    ("plan", r"which plan|what plan|plan are you on"),
    ("check", r"does that make sense|is that (ok|okay|alright|all right)|sounds? (good|ok|okay)|happy with that|with me so far|does that help"),
]
_TOPICS = [(k, re.compile(p, re.I)) for k, p in TOPICS]
IDENTITY = {"name", "dob", "postcode", "email"}
# A story line already answers a question when it says these things.
COVERS = {
    "apps": r"forge|vault|express|apps?\b|just (that|the)", "people": r"\b(of us|just me|two|three|four|eight|team|designers|colleague)\b",
    "volume": r"\b(\d+|ten|fifteen|twenty|thirty|forty|fifty|hundred|thousand|thousands|dozen)\b", "when": r"\b(last week|last month|weeks? ago|days? ago|months? ago|since|yesterday|on (monday|tuesday|wednesday|thursday|friday|the \d+\w*))\b",
    "work": r"\b(shop|studio|business|channel|weddings?|freelanc|designer|clients|brands|youtube|etsy|photos)\b",
    "email": r"e-?mail|@", "deadline": r"\b(saturday|friday|today|tomorrow|this week|deadline)\b",
    "budget": r"\b(pay|paying|cost|money|price|expensive|cheaper)\b", "amount": r"\b(pounds?|dollars?|sixty|\$|£)\b",
}
_COVERS = {k: re.compile(v, re.I) for k, v in COVERS.items()}

_AGENT_NAME = re.compile(r"(?:my name(?:'s| is)|this is|speaking (?:to|with)|you'?re (?:speaking|through) (?:to|with))\s+([A-Z][a-z]{1,15})\b")
_NOT_NAMES = {"Acme", "Customer", "Care", "Support", "The", "Your", "A", "An", "Just", "Here", "Me"}
_INTERJECTION = re.compile(r"^(ah|yes|yeah|thank|thanks|that|exactly|oh|ok|okay|right|hmm|fine|please|both|constantly|honestly|well|sure|no|so|hang|hold|wait|um|look|hi|hello)\b", re.I)
_REFERRAL = re.compile(r"refer|hand (you |this )?(over|on)|specialist|(our|the) \w+ team|put you in touch|call(ing)? you back|callback|get someone", re.I)
_HOLD_ONLY = re.compile(r"bear with me|(one|a|just a) (moment|second|sec|minute|mo)\b|(hold|hang) on|let me (just )?(check|look|have a look|pull|bring)", re.I)


_ASKING = re.compile(r"^\s*(can|could|may|would|will) (i|you|we) |^\s*(what|which|how|when|who|where|why|do|does|did|are|is|have|has)\b|"
                     r"^\s*(please )?(confirm|tell me|give me|let me (have|take|get))\b|\b(can|could|may) i (take|have|get|grab|confirm|check|ask)\b",
                     re.I)


_REPLY_LEAD = re.compile(r"^(both,? actually|exactly( that)?|constantly|honestly(, \w+)?|about \w+)[.,!]?\s+", re.I)
_ACK_LEAD = re.compile(r"^(ah|oh|yes|yeah|right|that would explain it|that makes sense)[.,!]?\s+", re.I)


def ask_topics(text):
    """What the agent is asking about. A topic mentioned in a statement ("I'll send you a
    reference") is not a question, so only questions and requests count."""
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+|\s+[—–-]\s+", text or ""):
        if "?" not in sentence and not _ASKING.search(sentence):
            continue
        for k, rx in _TOPICS:
            if k not in out and rx.search(sentence):
                out.append(k)
    return out


def voice_for(scenario_id):
    return dict(VOICE.get(scenario_id, DEFAULT_VOICE))


# ══════════════════════════════════════════════════════════════════════════════
#  THE PERSONA — a customer, built from a demo contact
# ══════════════════════════════════════════════════════════════════════════════
class Persona:
    def __init__(self, scenario_id, treatment, difficulty="steady", seed=None, agent_first=False):
        sc = SCENARIO_BY_ID[scenario_id]
        self.sid = scenario_id
        self.sc, self.t = sc, treatment
        self.profile = dp.PROFILES[scenario_id]
        self.ctx = dp.CONTEXTS[scenario_id]
        self.first = (self.profile.get("person", {}).get("name", {}).get("firstName")) or "there"
        self.email = (self.profile.get("personalEmail") or {}).get("address") or ""
        self.difficulty = DIFF.get(difficulty, DIFF["steady"])
        self.rng = random.Random(seed if seed is not None else scenario_id + difficulty)
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
        # Distinctive phrases of the matched product: its name, and its last two words.
        self.offer_phrases = set()
        generic = {"studio", "cloud", "for", "all", "apps", "plan", "photography", "pro", "teams", "assets"}
        for p in (offer.get("offer") or {}).get("to", []):
            name = re.sub(r"^acme ", "", (p.get("product") or "").lower())
            name = re.sub(r"\s*[×x]\s*\d+\s*$", "", name).strip()     # "for teams × 3" is still "for teams"
            if not name:
                continue
            self.offer_phrases.add(name)
            tail = " ".join(name.split()[-2:])
            if len(tail) > 5:
                self.offer_phrases.add(tail)
            for w in name.split():
                if w not in generic and len(w) > 2:
                    self.offer_phrases.add(w)
            if "1tb" in name:                    # as it is said out loud
                self.offer_phrases.update({"terabyte", "1 tb", "one tb"})
        ent = self.profile[cdp.TENANT]["entitlement"]
        self.facts = {"name": cdp.full_name(self.profile), "email": self.email,
                      "tenure": "About %s now." % sc["customer"]["tenure"], "plan": "I'm on %s." % sc["customer"]["tier"],
                      "monthly": "${:,.2f}".format((ent.get("annualValue") or 0) / 12.0)}
        self.facts.update(FACTS.get(scenario_id, {}))
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
        self.opened = not agent_first   # has the customer said why they are calling?
        self.flags = []             # things worth remembering for the debrief
        self.turns = 0
        self.agent_name = None
        self.fact_streak = 0
        self.interruptions = 0
        self.nudges = 0
        self.floor_hits = 0
        self.last_ack = None
        self.wrap_turns = 0
        self.last_text = None

    # -- small helpers
    def _bump(self, d):
        self.mood = max(0.05, min(0.95, self.mood + d))
        if d < 0 and self.mood <= 0.08:
            self.floor_hits += 1

    def _flag(self, f):
        if f not in self.flags:
            self.flags.append(f)

    def _pick(self, options):
        return options[self.rng.randrange(len(options))]

    def opening(self):
        return self.beats[0]["say"] if self.beats else "Hello?"

    def state(self):
        return {"mood": round(self.mood, 2), "mood_label": mood_label(self.mood), "beat": self.beat,
                "beats": len(self.beats), "verified": self.verified, "accepted": self.accepted,
                "resolved": self.resolved, "ended": self.ended, "opened": self.opened, "flags": list(self.flags)}

    def answer(self, topics, text=""):
        """The customer's own answer to what was asked, or None."""
        out = []
        idn = [t for t in topics if t in IDENTITY]
        if idn:
            self.verified = True
            parts = []
            for t in idn:
                v = self.facts.get(t)
                if not v:
                    continue
                if t == "email" and "." in v and " " in v:   # a full sentence of its own
                    parts.append(v)
                elif t == "name":
                    parts.append("It's %s." % v)
                elif t == "email":
                    parts.append("The email's %s." % v)
                elif t == "dob":
                    parts.append("Date of birth is %s." % v)
                elif t == "postcode":
                    parts.append("Postcode %s." % v)
            out += parts or ["Sure."]
        for t in topics:
            if t in IDENTITY:
                continue
            if t == "hear":
                out.append("Yes, I'm here.")
            elif t == "check":
                out.append(self._pick(["Yes, that makes sense.", "Yeah, OK.", "Right, yes."]) if self.mood >= 0.4
                           else self._pick(["I suppose so.", "Fine."]))
            elif self.facts.get(t):
                out.append(self.facts[t].format(**self.facts) if "{" in self.facts[t] else self.facts[t])
            if len(out) >= 2:
                break
        return " ".join(out) if out else None

    def _fit(self, line, m, text, topics):
        """A story line, trimmed of reactions to things the trainee did not say."""
        asked = ("?" in (text or "") or bool(_ASKING.search(text or ""))) and not (topics and set(topics) <= IDENTITY)
        out = line
        for _ in range(3):
            if not asked and _REPLY_LEAD.match(out):
                out = _REPLY_LEAD.sub("", out, 1)
            elif not (asked or m & {"explain", "reflect", "fix"}) and _ACK_LEAD.match(out):
                out = _ACK_LEAD.sub("", out, 1)
            else:
                break
        if out is not line:
            out = re.sub(r"^(and|so|but)\s+", "", out, flags=re.I)
        return out[:1].upper() + out[1:] if out else line

    def named_offer(self, text, m):
        """Naming the product the engine matched, and what it does or costs, is an offer."""
        low = (text or "").lower()
        if not self.offer_phrases or not any(p in low for p in self.offer_phrases):
            return False
        return "price" in m or bool(re.search(r"\b(gives?|get|gets|includes?|lets|would|could|option|move|switch|set (you )?up|built for)\b", low))

    def _ack(self, m, line):
        """A short reaction to what the agent just did, the way people talk. Not every turn."""
        if not line or _INTERJECTION.match(line.strip()) or self.rng.random() > 0.6:
            return ""
        upset = self.mood < 0.4
        if "fix" in m:
            opts = ["Right.", "OK."] if upset else ["OK, good.", "Right. Thank you.", "Great, thanks."]
        elif "explain" in m or "reflect" in m:
            opts = ["Right."] if upset else ["Oh, I see.", "Ah, right.", "Right, OK."]
        elif "empathy" in m:
            opts = ["Well, thank you for saying that."] if upset else ["Thanks."]
        else:
            opts = ["OK.", "Mm.", "Right."]
        opts = [o for o in opts if o != self.last_ack] or opts
        a = self._pick(opts)
        self.last_ack = a
        return a + " "

    # -- the customer's turn
    def respond(self, text, agent_moves=None, interrupted=False):
        """What the customer says back, and why. Returns {text, mood, mood_label, ended, why}."""
        m = set(agent_moves if agent_moves is not None else moves(text))
        self.turns += 1
        if not self.agent_name:
            n = _AGENT_NAME.search(text or "")
            if n and n.group(1) not in _NOT_NAMES:
                self.agent_name = n.group(1)
        lead = ""
        if interrupted:
            self.interruptions += 1
            if self.interruptions >= 2:
                self._flag("interrupted")
            if self.mood < 0.4:
                self._bump(-0.06)
                lead = self._pick(["Can I just finish? ", "Let me finish, please. "])
        r = self._respond(text, m)
        if lead and r["why"] not in ("hung_up", "closed"):
            r = {**r, "text": lead + r["text"]}
        # Pushed past breaking point on the harder settings, the customer hangs up.
        if not self.ended and self.floor_hits >= 2 and self.difficulty["id"] != "steady":
            self.ended = True
            self._flag("customer_hung_up")
            r = self._say("No. I've had enough of this. I'll take it up another way. Goodbye.", "hung_up")
        return r

    def _respond(self, text, m):
        upset = self.mood < 0.4
        words = len((text or "").split())
        if self.ended:
            return self._say("Thanks again. Bye now.", "ended")
        topics = ask_topics(text)

        # The agent speaks first on a real call. The customer then says why they called.
        if not self.opened:
            self.opened = True
            if not (m & {"greet", "empathy"}) and words < 3:
                self._bump(-0.03)
            opening = self.opening()
            hi = "" if re.match(r"^(hi|hello)\b", opening, re.I) else \
                "Yes, hi. " if self.first.lower() in (text or "").lower() else self._pick(["Hi. ", "Hello, yes. ", "Hi there. "])
            idn = self.answer([t for t in topics if t in IDENTITY]) if set(topics) & IDENTITY else None
            return self._say(hi + (idn + " " if idn else "") + opening, "opened")

        if words < 2 and not topics:
            self._bump(-0.03)
            return self._say(self._pick(["Hello? Are you still there?", "Sorry?", "Hello?"]), "silence")
        if topics == ["hear"]:
            return self._say("Yes, I'm here. I can hear you.", "answered")

        if "pressure" in m:
            self._flag("pressure")
            self._bump(-0.25)
            return self._say("Please don't pressure me. I'm not deciding anything on the spot. I just want this sorted.", "pressure")

        # "Bear with me while I check" — the customer waits, as people do.
        if _HOLD_ONLY.search(text or "") and words <= 12 and "?" not in text and not (m & {"fix", "explain", "empathy", "offer"}):
            self._flag("hold_asked")
            return self._say(self._pick(["Fine."] if upset else ["Sure.", "OK, no problem.", "Sure, go ahead."]), "holding")

        prefix = ""
        if "verify" in m and not self.verified and not (set(topics) & IDENTITY):
            self.verified = True
            # "That's you verified" means the details were already given; a question means they were asked for.
            if not re.search(r"\bverified\b|that'?s you\b", text, re.I):
                prefix = "Sure. It's %s, and the email is %s. " % (cdp.full_name(self.profile), self.email or "the one on the account")
        # A greeting is not a goodbye, whatever words it borrows.
        if self.turns <= 2 or "greet" in m:
            m = m - {"close"}

        # An offer, and whether this was the moment for one.
        if "offer" not in m and self.sell and self.named_offer(text, m):
            m = m | {"offer"}
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
                return self._say(prefix + "Hold on. Before anything else, can we sort out what I actually called about?", "pitched_early")
            if self.accepted:
                return self._say(prefix + self._pick(["Yes, we've agreed that. Is there anything I need to do my end?",
                                                      "Yes. Let's just get that set up.", "We've covered that, yes."]), "already_accepted")
            # An offer that names nothing draws a question first — one of the harder customer's objections.
            if self.objections_left > 0 and self.offer_words and not any(w in text.lower() for w in self.offer_words) and "price" not in m:
                self.objections_left -= 1
                self._flag("vague_offer")
                self._flag("objection")
                return self._say(prefix + "What is it exactly? I don't want to be paying for things I won't use.", "objection")
            if self.objections_left > 0:
                self.objections_left -= 1
                objections = ["How much more is that a month?", "Will I lose anything I've already got?", "Can that be done today, or is there a wait?"]
                if "price" in m:          # already told the price: ask the next thing instead
                    objections = objections[1:]
                self._flag("objection")
                return self._say(prefix + objections[(self.difficulty["objections"] - self.objections_left - 1) % len(objections)], "objection")
            self.accepted = True
            self.resolved = True
            self._bump(0.2)
            self._flag("accepted")
            return self._say(prefix + (self._pick(["That sounds like exactly what I need. Yes, let's do that.",
                                                   "OK, yes. That makes sense. Let's do it."]) if not upset
                                       else "Fine. If that stops it happening again, let's do it."), "accepted")

        # Answering an objection counts: the customer asked, the agent replied.
        if self.flags and self.flags[-1] == "objection" and (m & {"price", "explain", "fix", "diagnose", "reflect"} or words >= 4):
            if self.objections_left > 0:
                self.objections_left -= 1
                return self._say(prefix + "And will I lose anything I've already got?", "objection")
            self.accepted = True
            self.resolved = True
            self._bump(0.2)
            self._flag("accepted")
            return self._say(prefix + "OK. That's fair. Let's go ahead with it.", "accepted")

        if "close" in m:
            if self.resolved or self.accepted or (self.beat >= len(self.beats) - 1 and ("fix" in m or "fixed" in self.flags)):
                self.ended = True
                self.resolved = True
                self._flag("closed_properly")
                self._bump(0.1)
                name = (", " + self.agent_name) if self.agent_name and self.mood >= 0.5 else ""
                return self._say(prefix + ("No, that's everything. Thank you%s, you've been really helpful. Bye." % name if self.mood >= 0.5
                                           else "No. That's it. Thanks. Bye."), "closed")
            self._flag("closed_early")
            self._bump(-0.1)
            return self._say(prefix + "Wait. We haven't actually sorted my problem yet.", "closed_early")

        if self.resolved:
            return self._wrapping(text, m, topics, prefix)

        # A question about the customer's own situation gets a straight answer.
        answer = self.answer(topics, text) if topics else None
        only_asking = bool(answer) and not (m & {"explain", "fix", "empathy", "reflect", "offer"})

        # Progress through the story.
        want = set(self.beats[self.beat]["expect"]) if self.beat < len(self.beats) else set()
        substantive = words >= 6
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

        nxt = self.beats[self.beat + 1]["say"] if self.beat + 1 < len(self.beats) else None
        non_id = [t for t in topics if t not in IDENTITY and t not in ("check", "hear")]
        covered = bool(nxt) and bool(non_id) and all(t in _COVERS and _COVERS[t].search(nxt) for t in non_id)

        # Just asking: answer, and wait for the agent to do something with it — unless the
        # next thing the customer would have said is the answer anyway.
        if only_asking and not covered:
            self.stalls = 0
            self._bump(0.02)
            if non_id:
                self.fact_streak += 1
            if self.fact_streak >= 3:
                self.fact_streak = 0
                return self._say(prefix + answer + " " + self._pick(["But can we get back to why I called?",
                                                                    "Anyway. What about my problem?"]), "answered_pulling_back")
            return self._say(prefix + answer, "answered")

        if progress or self.stalls >= 2:
            self.stalls = 0
            self.fact_streak = 0
            self.beat += 1
            lead = "" if (covered or not answer) else answer + " "
            if self.beat < len(self.beats):
                line = self._fit(self.beats[self.beat]["say"], m, text, topics)
                return self._say(prefix + lead + (self._ack(m, line) if not lead else "") + line, "advanced")
            self.resolved = True
            if self.sell and not self.accepted:
                return self._say(prefix + lead + "So, is there anything that would stop this happening again?", "inviting_offer")
            return self._say(prefix + lead + (self._pick(["OK. Thank you. So that's all sorted, then?", "Right, great. So that's it done?"])
                                              if self.mood >= 0.45 else "Right. So it's dealt with? I won't have to call again?"),
                             "waiting_to_close")

        self.stalls += 1
        self._bump(-0.08)
        self._flag("stalled")
        nudges = (["I've already explained that. Can you actually look at my account?",
                   "With respect, I don't need platitudes. I need this fixed.",
                   "Are you going to do something about it, or not?"] if upset else
                  ["Right. So what can you do about it?",
                   "OK. Can you have a look at my account?",
                   "Sorry, I'm not sure that answers it. What happens next?"])
        return self._say(prefix + nudges[(self.stalls - 1) % len(nudges)], "stalled")

    def nudge(self):
        """The agent has gone quiet. The customer fills the silence, then gives up."""
        if self.ended:
            return self._say("", "ended")
        if not self.opened:
            self.opened = True
            self._bump(-0.05)
            self._flag("slow_greeting")
            return self._say("Hello? Hi, is that customer services? " + self.opening(), "opened_unprompted")
        self.nudges += 1
        self._flag("dead_air")
        self._bump(-0.1 if self.mood < 0.4 else -0.05)
        if self.nudges >= 3 and (self.mood < 0.35 or self.difficulty["id"] == "tough"):
            self.ended = True
            self._flag("customer_hung_up")
            return self._say("I'll call back when someone's actually there. Bye.", "hung_up")
        lines = ["Hello? Are you still there?", "Hello? Can you hear me?", "Hello? I'm still waiting."]
        return self._say(lines[min(self.nudges, len(lines)) - 1], "nudge")

    def _wrapping(self, text, m, topics, prefix):
        """The customer has said everything they called to say. What they do now depends on
        what the agent does — and a customer who is kept talking ends the call themselves."""
        self.wrap_turns += 1
        upset = self.mood < 0.4
        answer = self.answer(topics, text) if topics else None
        if self.sell and not self.accepted:
            # An offer is handled above; a referral to the right people is as good as one.
            if "fix" in m and _REFERRAL.search(text or ""):
                self.accepted = True
                self._flag("referred")
                self._bump(0.15)
                return self._say(prefix + self._pick(["That would be really useful, yes. Please do.", "Yes, please. That sounds like the right people to talk to."]), "accepted")
            if answer:
                return self._say(prefix + answer, "answered")
            if "?" in (text or ""):          # a yes-or-no question about the situation
                return self._say(prefix + self._pick(["Yes, pretty much.", "More or less, yes.", "Yes, that's right."]), "answered")
            if self.wrap_turns >= 4:
                self.ended = True
                self._flag("offer_missed")
                return self._say(prefix + "OK. Well, I'll leave it there and have a think. Thanks for your time. Bye.", "customer_closed")
            # The first invitation was made when the story ran out; these follow it.
            invites = ["Is there something we should be on, for this kind of thing?",
                       "I'd be interested if there's a better way of doing this, honestly.",
                       "So — is there anything you can suggest?"]
            return self._say(prefix + invites[min(self.wrap_turns - 1, len(invites) - 1)], "inviting_offer")
        if answer:
            return self._say(prefix + answer, "answered")
        if m & {"fix", "explain", "reflect"}:
            self._bump(0.03)
            return self._say(prefix + self._pick(["OK, great.", "Perfect, thank you.", "That's good to know, thanks."] if not upset else ["Right.", "OK."]), "acknowledged")
        if "?" in (text or "") or "diagnose" in m:
            return self._say(prefix + self._pick(["No, I think that's everything.", "Not that I can think of, no.", "No, that's all."]), "answered")
        if self.wrap_turns >= 3:
            self.ended = True
            self._flag("customer_closed")
            return self._say(prefix + ("OK. Well, I think that's everything from my side. Thanks for your help. Bye." if not upset
                                       else "Right. I think we're done here. Bye."), "customer_closed")
        return self._say(prefix + self._pick(["OK.", "Right.", "Sure."]), "acknowledged")

    def _say(self, text, why):
        # Never the same words twice running.
        if text and text == self.last_text and why not in ("ended",):
            text = self._pick(["Sorry — as I said, " + text[0].lower() + text[1:], text + " As I said."])
        self.last_text = text
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
        items.append({"id": "close", "label": "Close with next steps", "done": "closed_properly" in self.flags,
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
                       "turns": sum(1 for m in sc["conversation"] if m["role"] == "customer"),
                       "first_name": sc["customer"]["name"].split()[0], "voice": voice_for(sc["id"]),
                       "opening": next((m.get("text_en") or m["text"] for m in sc["conversation"] if m["role"] == "customer"), "")})
    return {"customers": people, "difficulties": DIFFICULTY}


def start(scenario_id, difficulty, model, threshold, agent_first=True):
    t = fd.treatment_for(scenario_id, model, threshold)
    p = Persona(scenario_id, t, difficulty, seed=uuid.uuid4().hex, agent_first=agent_first)
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
    noticed = []
    if "customer_hung_up" in p.flags:
        noticed.append("The customer hung up. Keep them talking to you: acknowledge, then act. Never leave them in silence or under pressure.")
    if "dead_air" in p.flags:
        noticed.append("Avoid long silences. If you need time, say so: \"bear with me while I check that.\"")
    if "interrupted" in p.flags:
        noticed.append("Let the customer finish before you speak. Interrupting an upset customer costs you their goodwill.")
    if "slow_greeting" in p.flags:
        noticed.append("Answer straight away. The customer had to say hello first.")
    if "customer_closed" in p.flags:
        noticed.append("The customer had to end the call. Once it is sorted, close it yourself: say what happens next and ask if there is anything else.")
    if "offer_missed" in p.flags:
        noticed.append("The customer left the door open three times and nothing was offered. The engine had found the fit — say it once, plainly.")
    tips = (noticed + [o["tip"] for o in bad + [o for o in missed if not o.get("bad")]])[:3]
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
