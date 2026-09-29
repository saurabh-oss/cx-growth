"""
GUIDED TOUR — the presentation flow.

The POC has eight screens. Walked cold, that is a feature tour and it loses the room.
This is the narrative that turns it into a sixteen-minute argument:

    volume ─▶ restraint ─▶ two live cases ─▶ unscripted ─▶ the platform ─▶ the fit ─▶ the ask

Four deliberate choices in the ordering:

1. RESTRAINT COMES BEFORE REVENUE. The second thing an executive sees is the engine
   declining to sell. Permission has to be earned before the upside is shown, because
   the first objection is always "won't this make my agents pushy?".

2. TWO CASES THAT ARE DIFFERENT IN KIND, not just in value. Case 1 expands a licence
   model inside Studio Cloud. Case 2 crosses into Engage Cloud — a recommendation
   a product-line-organised sales team would never make off a support call. One case
   looks like a lucky example; the contrast is the argument.

3. THE UNSCRIPTED CONTACT COMES AFTER THE SCRIPTED ONES. By then the room has a question
   it is too polite to ask: is any of this real? Handing someone the customer's part
   answers it without being asked.

4. NO STATS INTERLUDE. The commercial model is one click away on the Business Case screen
   if it is asked for, but it is not narrated.

Every step speaks to two people:

    takeaway   for the AUDIENCE. One plain sentence, always on screen. No jargon.
    say/point  for the PRESENTER. Hidden until Notes is switched on (press N).
    focus      the thing on screen to look at. The app draws the eye to it.

Tokens in braces are filled by main.py from what the engine computed, so the script
cannot drift from the screen: {pct.elena} is Elena's likelihood to buy, as a percentage.
"""

STORY = [
    {
        "n": 1,
        "act": "The volume",
        "title": "{contacts} conversations a day",
        "takeaway": "Every one costs about six dollars to handle and returns nothing. Not because there is "
                    "no opportunity in them — because nobody is listening for it.",
        "say": "Every one of these costs about six dollars to handle and returns nothing. "
               "Not because there's no opportunity in them — because nobody is listening for it.",
        "point": "The contacts arriving on the left, each already decided. Then the funnel: "
                 "{contacts} in at the top, {converted} sales at the bottom.",
        "page": "frontdoor",
        "tab": "overview",
        "focus": "funnel",
        "duration": "1 min",
        "beat": "The traffic is simulated and says so. The decisions are not — every row ran through the engine.",
    },
    {
        "n": 2,
        "act": "Restraint",
        "title": "It knows when not to sell",
        "takeaway": "Elena was charged twice. She looks {pct.elena}% likely to buy — and the engine still says no. "
                    "An upset customer is never a sales opportunity.",
        "say": "Elena has been charged twice and it's her second call about it. On paper she looks {pct.elena}% "
               "likely to buy — above the line. The service-recovery rule overrode it anyway.",
        "point": "The bar sitting past the line, and the red box beneath it: held back.",
        "page": "frontdoor",
        "tab": "treatment",
        "contact": "elena-double-charge",
        "scroll": "fd-treatment",
        "focus": "decision",
        "duration": "2 min",
        "beat": "Then flip \"Failure resolved\" under What if. Same customer, and now she is a SELL. "
                "Nothing here is a lookup.",
    },
    {
        "n": 3,
        "act": "Opportunity",
        "title": "Same engine, opposite call",
        "takeaway": "Priya rang about a sign-in problem. Three people are sharing one licence — "
                    "a business that has outgrown its plan.",
        "say": "Priya is calling because a colleague keeps getting signed out. Three devices, two "
               "locations, one individual licence. The engine reads that as a business outgrowing its plan.",
        "point": "What we already knew — three people on one licence counts most, before a word was spoken.",
        "page": "frontdoor",
        "tab": "treatment",
        "contact": "priya-individual-to-teams",
        "scroll": "fd-treatment",
        "focus": "evidence",
        "duration": "1 min",
    },
    {
        "n": 4,
        "act": "The agent",
        "title": "The agent sees it before saying hello",
        "takeaway": "Every waiting customer already carries a decision: solve, or sell.",
        "say": "This is an Amazon Connect agent desktop, not a dashboard. Every waiting contact already "
               "carries its segment, its treatment and its score — decided in the IVR.",
        "point": "The labels on each customer card. Elena's says SOLVE — held back — before anyone picks up.",
        "page": "workspace",
        "focus": "queue",
        "duration": "1 min",
    },

    # ── CASE 1: licence-model expansion inside Studio Cloud ───────────────
    {
        "n": 5,
        "act": "Story 1 · A bigger plan",
        "title": "Watch it work — a sign-in complaint",
        "takeaway": "The AI listens alongside the agent, hears what matters, and suggests what to say next.",
        "say": "This starts as a fault report. Three of them have been sharing one login for two years "
               "because nobody ever told her there was another way.",
        "point": "The guidance on the right correcting the framing first — it's a licence mismatch, not a "
                 "defect — and the knowledge article it cites for saying so.",
        "page": "workspace",
        "scenario": "priya-individual-to-teams",
        "focus": "assist",
        "duration": "2 min",
        "beat": "Pace it with the 1× / 2× control in the header. Narrate — silence loses the room.",
    },
    {
        "n": 6,
        "act": "Story 1 · A bigger plan",
        "title": "One seat becomes three",
        "takeaway": "A sign-in complaint became $2,520 a year. And if she calls tomorrow, nobody tries to sell to her again.",
        "say": "Individual to Studio Cloud for teams — Admin Console, per-seat licences, shared "
               "libraries and a company invoice. Two and a half thousand dollars, from a sign-in complaint.",
        "point": "The offer, then the lower half: the call scored for quality, the outcome saved to her "
                 "record, and what happens if she calls again tomorrow.",
        "page": "workspace",
        "focus": "next-contact",
        "duration": "1 min",
        "beat": "\"If she calls tomorrow\" reads SOLVE. The 30-day pause is enforced, not promised.",
    },

    # ── CASE 2: the engine crosses out of Studio Cloud ────────────────────
    {
        "n": 7,
        "act": "Story 2 · Across the portfolio",
        "title": "A customer with no problem to fix",
        "takeaway": "Ravi is happy and growing. The opportunity is the thing he has not thought to ask for.",
        "say": "Ravi is healthy, expanding, and not complaining. He asks a small question about version "
               "control in Express. Watch where the engine goes with it.",
        "point": "He is tagged Growth Ready — no blocker, just momentum. {pct.ravi}% likely to buy anyway.",
        "page": "workspace",
        "scenario": "ravi-creative-to-experience",
        "focus": "signals",
        "duration": "2 min",
        "beat": "Nothing is broken here. This is the opportunity that never reaches a sales team today.",
    },
    {
        "n": 8,
        "act": "Story 2 · Across the portfolio",
        "title": "Studio Cloud in, Engage Cloud out",
        "takeaway": "A Studio Cloud customer, an Engage Cloud answer — from a support call about photo versions.",
        "say": "The recommendation is ContentVault Assets, with Analytics behind it. A Studio Cloud "
               "customer, an Engage Cloud answer — off a support call about photo versions.",
        "point": "The offer crossing from one cloud to another, and the referral raised for the specialist team.",
        "page": "workspace",
        "focus": "outcome",
        "duration": "1 min",
        "beat": "A sales team organised by product line never makes this call. The engine is not organised by product line.",
    },

    # ── Proof it is not a recording ─────────────────────────────────────────
    {
        "n": 9,
        "act": "Your turn",
        "title": "Now you be the customer",
        "takeaway": "Those two were rehearsed. This one is not. Say anything.",
        "say": "Those two were rehearsed. This one isn't. Pick a customer, pick why they're calling, "
               "and say whatever you like — the engine has not seen it before.",
        "point": "Hand over the keyboard. Signals, score and guidance move on what is actually typed.",
        "page": "workspace",
        "live": True,
        "duration": "2 min",
        "beat": "Try to make it sell to someone angry. Say you've been charged twice. It stands down.",
        "optional": True,
    },

    # ── Platform, fit, then the ask ─────────────────────────────────────────
    {
        "n": 10,
        "act": "The foundation",
        "title": "Built on Acme's own data model",
        "takeaway": "Customer data is already held in Acme's format. Moving to Acme Experience Platform "
                    "is a configuration change, not a rebuild.",
        "say": "Every profile and event you've seen is in Acme's own Open Data Model. The platform "
               "holding them today is {platform}. Swapping it for Experience Platform is configuration, "
               "not a rebuild.",
        "point": "The table — the same six operations, three platforms. Then the gaps, stated plainly.",
        "page": "technology",
        "tab": "platform",
        "focus": "platform-ops",
        "duration": "1 min",
        "beat": "Name the gaps before they do. Identity stitching and governance are AXP's, not ours.",
    },
    {
        "n": 11,
        "act": "The fit",
        "title": "Your target architecture, running",
        "takeaway": "This is the architecture you approved. A good part of it is already working.",
        "say": "This is your target state, running. {built} components built, {partial} partial, {planned} on the "
               "roadmap. {agents_built} of the Magnificent 7 agents are built, and the other {agents_partial} partly.",
        "point": "Press Trace a contact — one component lights at a time, all the way through.",
        "page": "architecture",
        "trace": True,
        "duration": "1 min",
    },
    {
        "n": 12,
        "act": "The ask",
        "title": "Two weeks, not two quarters",
        "takeaway": "Everything here runs on assumptions. Two weeks of Value Discovery replaces them with your numbers.",
        "say": "Everything you've seen is modelled on industry assumptions and synthetic traffic. A Value "
               "Discovery replaces them with your contact mix, your queues, your margins.",
        "point": "Getting there with Globex. Phase 0 is marked Start here.",
        "page": "executive",
        "scroll": "exec-roadmap",
        "focus": "roadmap",
        "duration": "1 min",
        "beat": "Stop talking here. The next thing said should come from them.",
    },
]

ACTS = ["The volume", "Restraint", "Opportunity", "The agent",
        "Story 1 · A bigger plan", "Story 2 · Across the portfolio", "Your turn",
        "The foundation", "The fit", "The ask"]

TOTAL_MINUTES = 16
