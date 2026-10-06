"""
Demo scenarios — Acme Studio Cloud consumer contact centre.

These are ordinary consumer support calls: storage full, wants to cancel, can't sign in.
Individual values are small ($99–$480 of annual recurring revenue) — the business case
comes from volume, not deal size. See SCALE_MODEL below.

Every call runs through the same pipeline:

    INPUT  ─▶  AGENTIC ENGINE                                  ─▶  OUTCOME
    voice/chat   triage → signals → offer match → copilot          lead captured
    + account                │                                     or resolved normally
      context                └── below threshold / suppressed ────▶ standard resolution

The triage stage is the part worth demonstrating. Most calls are NOT sales opportunities,
and an engine that knows when to stay out of the way is what makes this safe to put in
front of real customers. Two scenarios here deliberately route away from sales:
  • robert-signin      — no commercial intent at all
  • elena-double-charge — commercial adjacency exists, but suppressed for service recovery
"""

# Modelled volume assumptions used by the Analytics scale panel. These are ASSUMPTIONS
# for the business case, not measured results — the UI labels them as such.
SCALE_MODEL = {
    "daily_calls": 9200,
    "triage_rate": 0.17,        # share of calls routed to the growth engine
    "capture_rate": 0.32,       # share of routed calls that produce a qualified lead
    "conversion_rate": 0.29,    # share of leads that convert
    "avg_value": 237,           # average incremental ARR per conversion, USD
}

TRIAGE_THRESHOLD = 0.55


SCENARIOS = [
    # ══════════════════════════════════════════════════════════════════════════
    #  ROUTED TO GROWTH ENGINE
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "aisha-storage-full",
        "title": "LightVault Storage Full",
        "description": "A keen photographer has run out of storage, with a wedding to shoot on Saturday.",
        "type": "Upsell",
        "icon": "📸",
        "customer": {
            "name": "Aisha Kapoor",
            "role": "Individual · Photography plan",
            "company": "Consumer",
            "tier": "Photography 20GB",
            "account_value": "$119.88/yr",
            "products": ["LightVault", "PhotoForge"],
            "tenure": "3 years",
            "health_score": 88,
            "usage_trend": "↑ 62% photos YoY",
            "contract_renewal": "Monthly · renews 12 Sep",
            "team_size": 1,
            "nps": 9
        },
        "triage": {
            "decision": "growth_engine",
            "propensity": 0.86,
            "reason": "Her storage is full, she uses the product more every year, and there is a bigger plan ready for her.",
            "suppression": None,
            "turn": 1
        },
        "conversation": [
            {"role": "customer", "text": "Hi, LightVault keeps telling me my cloud storage is full and my phone has stopped syncing photos altogether.", "delay": 0},
            {"role": "agent", "text": "Hi Aisha, thanks for calling. Let me check your storage — I can see you're on the Photography plan with 20GB, and you're currently at 20GB of 20GB.", "delay": 3},
            {"role": "customer", "text": "That would explain it. I've been shooting a lot more this year — I've started doing friends' weddings at weekends and the raw files are enormous. I've got one this Saturday and I can't afford for it to stop working.", "delay": 7},
            {"role": "agent", "text": "That makes sense — raw files from a wedding shoot will fill 20GB very quickly. Let me look at what would give you room to work.", "delay": 11},
            {"role": "customer", "text": "Please. I don't want to be deleting things off my phone at a wedding. Whatever gets it working properly, I just need it sorted before Saturday.", "delay": 15},
            {"role": "agent", "text": "Understood. There's a straightforward option that keeps everything you have and moves you to 1TB of cloud storage — let me walk you through it.", "delay": 19},
        ],
        "ai_analysis": {
            "signals": [
                {"turn": 0, "type": "expansion", "category": "Upsell", "signal": "Storage ceiling reached — sync has stopped working", "keywords": ["storage is full", "stopped syncing"], "confidence": 0.84, "timestamp": 2},
                {"turn": 2, "type": "expansion", "category": "Upsell", "signal": "Usage growing — shooting weddings, large raw files", "keywords": ["shooting a lot more", "weddings", "raw files are enormous"], "confidence": 0.89, "timestamp": 8},
                {"turn": 4, "type": "upsell", "category": "Upsell", "signal": "Deadline pressure and explicit willingness to resolve with a paid fix", "keywords": ["before Saturday", "whatever gets it working"], "confidence": 0.94, "timestamp": 16},
            ],
            "lead_score_progression": [42, 58, 74, 81, 91, 93],
            "sentiment_progression": [0.4, 0.5, 0.45, 0.6, 0.55, 0.8],
            "coaching_suggestions": [
                {"turn": 0, "suggestion": "Storage is at 100%. Confirm the ceiling first — resolve the anxiety before discussing any change of plan.", "type": "service", "priority": "medium"},
                {"turn": 2, "suggestion": "Usage is growing and the need is real, not speculative. Introduce the Photography plan with 1TB — 50x the storage for $10 more a month.", "type": "product", "priority": "high"},
                {"turn": 4, "suggestion": "She has a hard deadline on Saturday and has told you cost is not the obstacle. Offer the 1TB upgrade with immediate activation so syncing resumes today. Do not oversell — this is a one-step fix.", "type": "closing", "priority": "high"},
            ],
            "lead_summary": {
                "type": "Upsell",
                "estimated_value": "$120",
                "value_note": "more, every year",
                "confidence": 0.93,
                "recommended_action": "Upgrade to Photography plan with 1TB storage — $19.99/mo, activates immediately and restores sync today.",
                "urgency": "High — customer has a paid shoot on Saturday and sync is currently broken",
                "next_steps": [
                    "Apply the 1TB upgrade in-call and confirm sync resumes",
                    "Send storage-management tips for large raw catalogues",
                    "Flag for a 30-day check-in on storage headroom"
                ]
            }
        }
    },

    {
        "id": "tom-cancel-save",
        "title": "Cancellation — Save Opportunity",
        "description": "He is calling to cancel — too expensive. He uses two of the twenty apps he pays for.",
        "type": "Retention",
        "icon": "🛟",
        "customer": {
            "name": "Tom Whitfield",
            "role": "Individual · All Apps",
            "company": "Consumer",
            "tier": "Studio Cloud All Apps",
            "account_value": "$719.88/yr",
            "products": ["PhotoForge", "LightVault", "+ 18 unused apps"],
            "tenure": "14 months",
            "health_score": 54,
            "usage_trend": "2 of 20 apps used",
            "contract_renewal": "Monthly · renews 04 Sep",
            "team_size": 1,
            "nps": 6
        },
        "triage": {
            "decision": "growth_engine",
            "propensity": 0.79,
            "reason": "He wants to cancel, but he uses two of the apps every week. The problem is the price, not the product — a smaller plan could keep him.",
            "suppression": None,
            "turn": 1
        },
        "conversation": [
            {"role": "customer", "text": "Hi. I'd like to cancel my subscription please. It's sixty pounds a month and I just can't justify it any more.", "delay": 0},
            {"role": "agent", "text": "I'm sorry to hear that Tom, and of course I can help. Before I process anything — can I ask which apps you're actually using day to day?", "delay": 3},
            {"role": "customer", "text": "Honestly just PhotoForge and LightVault. I edit photos, that's it. I signed up for the full thing thinking I'd learn video editing and I never touched it. I'm paying for about eighteen apps I've never opened.", "delay": 7},
            {"role": "agent", "text": "That's really useful to know — and you're right, that's what the usage shows. So the issue is the price of what you're not using, rather than the tools themselves.", "delay": 11},
            {"role": "customer", "text": "Exactly. I do like PhotoForge and LightVault, I use them most weeks. It's just that sixty a month for two apps is ridiculous. If it were a sensible price for what I actually use I'd stay.", "delay": 15},
            {"role": "agent", "text": "Then let me show you something before we go any further — there's a plan built for exactly the way you're using this, and it's a fraction of what you're paying now.", "delay": 19},
        ],
        "ai_analysis": {
            "signals": [
                {"turn": 0, "type": "cross_sell", "category": "Retention", "signal": "Active cancellation intent — price objection, not product dissatisfaction", "keywords": ["like to cancel", "can't justify it"], "confidence": 0.81, "timestamp": 2},
                {"turn": 2, "type": "cross_sell", "category": "Retention", "signal": "Plan mismatch — 2 of 20 apps used, paying for unused capability", "keywords": ["just PhotoForge and LightVault", "eighteen apps I've never opened"], "confidence": 0.92, "timestamp": 8},
                {"turn": 4, "type": "cross_sell", "category": "Retention", "signal": "Explicit save condition stated — will stay at the right price point", "keywords": ["I do like", "use them most weeks", "I'd stay"], "confidence": 0.95, "timestamp": 16},
            ],
            "lead_score_progression": [38, 55, 72, 84, 92, 94],
            "sentiment_progression": [0.25, 0.35, 0.4, 0.5, 0.55, 0.75],
            "coaching_suggestions": [
                {"turn": 0, "suggestion": "Do not lead with a retention offer. Ask what they actually use first — the answer determines whether there is a genuine save here or whether cancelling is right for them.", "type": "service", "priority": "high"},
                {"turn": 2, "suggestion": "Usage is 2 of 20 apps. This is a plan mismatch, not a churn risk. The Photography plan covers both apps he uses at $19.99/mo.", "type": "product", "priority": "high"},
                {"turn": 4, "suggestion": "He has told you the save condition outright. Offer the Photography plan with 1TB — same two apps, $40/mo less. Frame it as fixing the mismatch, not as a discount to keep him.", "type": "closing", "priority": "critical"},
            ],
            "lead_summary": {
                "type": "Retention",
                "estimated_value": "$240",
                "value_note": "kept, every year",
                "confidence": 0.94,
                "recommended_action": "Switch from All Apps to Photography plan with 1TB — retains both apps he uses at $19.99/mo instead of losing the account entirely.",
                "urgency": "Immediate — cancellation is in progress on this call",
                "next_steps": [
                    "Process the plan change in-call, before cancellation completes",
                    "Confirm no loss of files, presets or catalogue history",
                    "Suppress win-back campaigns — account is now correctly matched"
                ]
            }
        }
    },

    {
        "id": "nina-express-premium",
        "title": "Express Feature Gate",
        "description": "She runs a small online shop on the free plan, and keeps running into features that need a paid one.",
        "type": "New Sale",
        "icon": "🛍️",
        "customer": {
            "name": "Nina Alvarez",
            "role": "Individual · Free tier",
            "company": "Consumer",
            "tier": "Acme Express (Free)",
            "account_value": "$0/yr",
            "products": ["Acme Express Free"],
            "tenure": "5 months",
            "health_score": 71,
            "usage_trend": "↑ 34 designs this month",
            "contract_renewal": "—",
            "team_size": 1,
            "nps": 8
        },
        "triage": {
            "decision": "growth_engine",
            "propensity": 0.74,
            "reason": "She keeps running into paid features while making designs for her shop. A natural moment to try the paid plan.",
            "suppression": None,
            "turn": 1
        },
        "conversation": [
            {"role": "customer", "text": "Hello — I'm trying to remove the background from a product photo in Express and it keeps telling me it's a premium feature. Is that a glitch?", "delay": 0},
            {"role": "agent", "text": "Hi Nina, not a glitch — background removal is one of the premium tools. Let me look at what you've been working on so I can point you the right way.", "delay": 3},
            {"role": "customer", "text": "Ah, that's frustrating. I run a small shop on Etsy and I'm making listing images — I've done about thirty this month. I keep running into locked templates and locked fonts too, it's slowing me right down.", "delay": 7},
            {"role": "agent", "text": "Thirty listings a month is a real volume — and it sounds like you're hitting the same handful of gates over and over rather than just once.", "delay": 11},
            {"role": "customer", "text": "Constantly. And honestly the listings that look better do sell better, so it matters. I just didn't know if it was worth paying for or whether I'd be paying for stuff I don't need.", "delay": 15},
            {"role": "agent", "text": "That's a fair question, and the answer is fairly clear given what you're doing. Let me show you exactly which of those blocks it removes.", "delay": 19},
        ],
        "ai_analysis": {
            "signals": [
                {"turn": 0, "type": "new_product", "category": "New Sale", "signal": "Premium feature gate hit — background removal blocked", "keywords": ["premium feature", "remove the background"], "confidence": 0.72, "timestamp": 2},
                {"turn": 2, "type": "new_product", "category": "New Sale", "signal": "Commercial use at volume — 30 listings/month, repeated gating", "keywords": ["shop on Etsy", "thirty this month", "locked templates"], "confidence": 0.88, "timestamp": 8},
                {"turn": 4, "type": "new_product", "category": "New Sale", "signal": "Value link stated by customer; only barrier is uncertainty about fit", "keywords": ["look better do sell better", "worth paying for"], "confidence": 0.91, "timestamp": 16},
            ],
            "lead_score_progression": [34, 49, 68, 79, 88, 90],
            "sentiment_progression": [0.35, 0.45, 0.4, 0.55, 0.6, 0.78],
            "coaching_suggestions": [
                {"turn": 0, "suggestion": "Answer the question honestly first — it is a premium feature, not a bug. Credibility here earns the rest of the conversation.", "type": "service", "priority": "medium"},
                {"turn": 2, "suggestion": "She is hitting the same three gates repeatedly at commercial volume. Introduce Express Premium and name the specific blocks it removes: background removal, premium templates, Acme Fonts.", "type": "product", "priority": "high"},
                {"turn": 4, "suggestion": "Her hesitation is fit, not price. Address it directly — list only the features she has actually hit, and mention the free trial so she can validate before paying.", "type": "closing", "priority": "high"},
            ],
            "lead_summary": {
                "type": "New Sale",
                "estimated_value": "$120",
                "value_note": "new, every year",
                "confidence": 0.90,
                "recommended_action": "Acme Express Premium at $9.99/mo — unlocks background removal, premium templates and Acme Fonts. Start on the free trial to de-risk the decision.",
                "urgency": "Medium — actively blocked today, but no hard deadline",
                "next_steps": [
                    "Start the Express Premium trial in-call and unblock the current listing",
                    "Send the three-step background removal walkthrough",
                    "Follow up at day 12 of trial to confirm conversion"
                ]
            }
        }
    },

    {
        "id": "marcus-generative-credits",
        "title": "Generative Credits Exhausted",
        "description": "He makes videos for a living and has run out of AI credits for the third month running.",
        "type": "Upsell",
        "icon": "✨",
        "customer": {
            "name": "Marcus Bell",
            "role": "Individual · Photography plan",
            "company": "Consumer",
            "tier": "Photography 1TB",
            "account_value": "$239.88/yr",
            "products": ["PhotoForge", "LightVault"],
            "tenure": "2 years",
            "health_score": 82,
            "usage_trend": "↑ credits exhausted 3 months running",
            "contract_renewal": "Monthly · renews 21 Sep",
            "team_size": 1,
            "nps": 8
        },
        "triage": {
            "decision": "growth_engine",
            "propensity": 0.81,
            "reason": "He runs out of credits every month, and his work earns him money. There is a bigger plan that fits.",
            "suppression": None,
            "turn": 1
        },
        "conversation": [
            {"role": "customer", "text": "Hey — Generative Fill has stopped working for me. It says I'm out of generative credits again. This is the third month running.", "delay": 0},
            {"role": "agent", "text": "Hi Marcus, thanks for calling. I can see that — your credits reset on the 21st, and you've used your full monthly allocation for the third consecutive month.", "delay": 3},
            {"role": "customer", "text": "Yeah. I make thumbnails and stills for a YouTube channel, so I'm generating variations constantly — I'll do fifteen versions of a thumbnail to see what tests best. It's how I earn, so when it stops I lose a day.", "delay": 7},
            {"role": "agent", "text": "So this isn't occasional retouching — it's core to your production process, and running out costs you real output.", "delay": 11},
            {"role": "customer", "text": "Exactly. And I've started doing short-form video too, which means I'm exporting out of PhotoForge and into something else that I'm also paying for separately. It's getting messy.", "delay": 15},
            {"role": "agent", "text": "That's worth looking at together — there's an option that raises your credit allocation and covers the video side in the same subscription. Let me lay it out.", "delay": 19},
        ],
        "ai_analysis": {
            "signals": [
                {"turn": 0, "type": "expansion", "category": "Upsell", "signal": "Generative credits exhausted three consecutive months", "keywords": ["out of generative credits", "third month running"], "confidence": 0.85, "timestamp": 2},
                {"turn": 2, "type": "expansion", "category": "Upsell", "signal": "Monetising account — downtime has direct income impact", "keywords": ["YouTube channel", "fifteen versions", "it's how I earn"], "confidence": 0.90, "timestamp": 8},
                {"turn": 4, "type": "upsell", "category": "Upsell", "signal": "Paying a competitor for video — consolidation opportunity", "keywords": ["short-form video", "paying for separately", "getting messy"], "confidence": 0.93, "timestamp": 16},
            ],
            "lead_score_progression": [40, 56, 73, 82, 90, 92],
            "sentiment_progression": [0.3, 0.45, 0.4, 0.55, 0.5, 0.75],
            "coaching_suggestions": [
                {"turn": 0, "suggestion": "Confirm the credit reset date so he can plan around it today — solve the immediate problem before discussing anything else.", "type": "service", "priority": "medium"},
                {"turn": 2, "suggestion": "This is production-scale generative use on a monetising account. Position the higher generative allocation as protecting income, not as more features.", "type": "product", "priority": "high"},
                {"turn": 4, "suggestion": "He is already paying a third party for video. Studio Cloud All Apps raises his credit allocation and replaces that separate spend with ClipForge Pro. Lead with the consolidation, and net off what he currently pays elsewhere.", "type": "closing", "priority": "high"},
            ],
            "lead_summary": {
                "type": "Upsell",
                "estimated_value": "$480",
                "value_note": "more, every year",
                "confidence": 0.92,
                "recommended_action": "Upgrade Photography 1TB → Studio Cloud All Apps at $59.99/mo — higher generative allocation plus ClipForge Pro, replacing his separate video subscription.",
                "urgency": "Medium-High — currently blocked, and losing production days each month",
                "next_steps": [
                    "Quantify his current third-party video spend and net it off the uplift",
                    "Apply the upgrade in-call to restore credits immediately",
                    "Send the ClipForge Pro quick-start for short-form workflows"
                ]
            }
        }
    },

    # ══════════════════════════════════════════════════════════════════════════
    #  ROUTED AWAY FROM SALES — the engine deliberately stays out of the way
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "robert-signin",
        "title": "Sign-In Failure",
        "description": "He cannot sign in. There is nothing to sell here — just a problem to fix quickly.",
        "type": "No Action",
        "icon": "🔑",
        "customer": {
            "name": "Robert Nkemelu",
            "role": "Individual · Photography plan",
            "company": "Consumer",
            "tier": "Photography 1TB",
            "account_value": "$239.88/yr",
            "products": ["LightVault", "PhotoForge"],
            "tenure": "5 years",
            "health_score": 90,
            "usage_trend": "→ stable",
            "contract_renewal": "Annual · renews 14 Mar",
            "team_size": 1,
            "nps": 9
        },
        "triage": {
            "decision": "standard",
            "propensity": 0.04,
            "reason": "He cannot sign in. Nothing suggests he wants to buy anything — fix it and let him go.",
            "suppression": None,
            "turn": 1
        },
        "conversation": [
            {"role": "customer", "text": "Hello, I can't sign in to my account. It keeps telling me my password is incorrect but I know it's the right one.", "delay": 0},
            {"role": "agent", "text": "Hi Robert, let's get that sorted. Thanks for those two details — that's you verified. I can see your account is active and in good standing — can I check whether you've recently changed your email address or password anywhere?", "delay": 3},
            {"role": "customer", "text": "I did change my email with my provider a few weeks ago, yes. Would that do it?", "delay": 7},
            {"role": "agent", "text": "That's very likely the cause. Your Acme ID is still tied to the old address. I can send a reset to the new one and update it on the account — that should have you back in within a couple of minutes.", "delay": 11},
            {"role": "customer", "text": "Oh brilliant. Yes please, that would be great.", "delay": 15},
            {"role": "agent", "text": "Sending that now. You'll get an email shortly — follow the link and you'll be straight back in. Anything else I can help with today?", "delay": 18},
        ],
        "ai_analysis": {
            "signals": [],
            "lead_score_progression": [6, 5, 4, 4, 3, 3],
            "sentiment_progression": [0.35, 0.5, 0.55, 0.7, 0.85, 0.9],
            "coaching_suggestions": [
                {"turn": 0, "suggestion": "Nothing to sell here. Get him signed in quickly — a fast, clean call is the right result.", "type": "service", "priority": "low"},
            ],
            "resolution_summary": {
                "outcome": "Resolved — nothing to sell",
                "detail": "He is signed in again: email updated, password reset. There was nothing to sell and nothing was offered.",
                "why_no_lead": [
                    "Nothing in the conversation suggested he wanted more",
                    "He has been on the same plan, happily, for five years",
                    "All he wanted was to sign in"
                ]
            }
        }
    },

    {
        "id": "elena-double-charge",
        "title": "Billing Error — Sales Suppressed",
        "description": "Charged twice, and calling about it for the second time. She could be sold to — and must not be.",
        "type": "Suppressed",
        "icon": "🚫",
        "customer": {
            "name": "Elena Marsh",
            "role": "Individual · All Apps",
            "company": "Consumer",
            "tier": "Studio Cloud All Apps",
            "account_value": "$719.88/yr",
            "products": ["PhotoForge", "VectorForge", "PageForge"],
            "tenure": "6 years",
            "health_score": 41,
            "usage_trend": "↑ 20 apps active",
            "contract_renewal": "Annual · renews 30 Nov",
            "team_size": 1,
            "nps": 3
        },
        "triage": {
            "decision": "standard",
            "propensity": 0.61,
            "reason": "She looks likely to buy — but she has been charged twice and this is her second call about it. No offer until it is put right.",
            "suppression": "service_recovery",
            "turn": 1
        },
        "conversation": [
            {"role": "customer", "text": "I have been charged twice this month. Sixty pounds, twice. I rang last week, I was told it would be refunded within five days, and nothing has happened.", "delay": 0},
            {"role": "agent", "text": "I'm very sorry Elena — that shouldn't have happened, and it certainly shouldn't still be outstanding after you'd already raised it. Let me look at this right now.", "delay": 3},
            {"role": "customer", "text": "I've been a customer for six years. I use these apps for my actual work. To be taken money twice and then just ignored for a week is not good enough, frankly.", "delay": 7},
            {"role": "agent", "text": "You're right, and I'm not going to defend it. I can see both charges and I can see last week's case — the refund was raised but never actioned. I'm escalating it now with priority.", "delay": 11},
            {"role": "customer", "text": "Thank you. I just want the money back and some confidence it won't happen again next month.", "delay": 15},
            {"role": "agent", "text": "Completely understood. I'm processing the refund directly rather than routing it back through the queue, and I'll send written confirmation with a reference so you have it on record.", "delay": 19},
        ],
        "ai_analysis": {
            "signals": [],
            "lead_score_progression": [12, 10, 8, 7, 6, 6],
            "sentiment_progression": [0.12, 0.18, 0.15, 0.3, 0.4, 0.55],
            "coaching_suggestions": [
                {"turn": 0, "suggestion": "No offers on this call. Acknowledge what went wrong without making excuses, and process the refund now rather than passing it on.", "type": "service", "priority": "critical"},
                {"turn": 2, "suggestion": "Six-year customer, second contact on the same unresolved issue. Recovery is the only objective — confirm the refund, give a reference, and set a follow-up.", "type": "service", "priority": "critical"},
            ],
            "resolution_summary": {
                "outcome": "Resolved — no offer made",
                "detail": "Refund processed on the call, with written confirmation. She looked {pct}% likely to buy — above the line — and the offer was still held back, because her billing problem was unresolved.",
                "why_no_lead": [
                    "Unresolved billing failure with a broken prior commitment",
                    "Second contact on the same issue — trust already damaged",
                    "She opened the call angry. Selling here would make it worse",
                    "She can be offered something once it is fixed and two weeks have passed"
                ]
            }
        }
    },

    # ══════════════════════════════════════════════════════════════════════════
    #  LICENCE-MODEL EXPANSION — individual licence shared across a small team
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "priya-individual-to-teams",
        "title": "Shared Login — Individual to Teams",
        "description": "A colleague keeps getting signed out. Three people are sharing a licence meant for one.",
        "type": "Upsell",
        "icon": "👥",
        "customer": {
            "name": "Priya Raman",
            "role": "Small business · All Apps (Individual)",
            "company": "Small Business",
            "tier": "All Apps · Individual",
            "account_value": "$719.88/yr",
            "products": ["PhotoForge", "VectorForge", "PageForge"],
            "tenure": "4 years",
            "health_score": 81,
            "usage_trend": "↑ 3 devices · 2 locations",
            "contract_renewal": "Annual · renews 18 Oct",
            "team_size": 3,
            "nps": 8
        },
        "triage": {
            "decision": "growth_engine",
            "propensity": 0.88,
            "reason": "Three people are sharing a licence meant for one. Nothing is broken — the business has outgrown its plan.",
            "suppression": None,
            "turn": 1
        },
        "conversation": [
            {"role": "customer", "text": "Hi — one of my colleagues keeps getting signed out of VectorForge. It says the account is being used somewhere else.", "delay": 0},
            {"role": "agent", "text": "Hi Priya. I can see sign-ins from three devices across two locations this week. An individual licence covers one person on two machines, so that's what's causing the sign-outs.", "delay": 3},
            {"role": "customer", "text": "Ah. Yes, there are three of us now. I started on my own four years ago and I've taken on two designers since. We've just been sharing my login because I didn't know there was another way.", "delay": 8},
            {"role": "agent", "text": "That explains it — and it's worth setting up properly, because you'll be running into the same thing with shared files and with invoicing.", "delay": 13},
            {"role": "customer", "text": "Both, actually. Our accountant keeps asking for a proper company invoice, and we're emailing PageForge files back and forth which is a nightmare. If there's a version built for small studios, I'd rather be set up correctly.", "delay": 18},
            {"role": "agent", "text": "There is, and it's built for exactly this situation. Let me walk you through what changes.", "delay": 24},
        ],
        "ai_analysis": {
            "signals": [
                {"turn": 0, "type": "expansion", "category": "Upsell", "signal": "Concurrent sign-in failure — one individual licence shared across users", "keywords": ["signed out", "used somewhere else"], "confidence": 0.87, "timestamp": 2},
                {"turn": 2, "type": "expansion", "category": "Upsell", "signal": "Team grown to three, all working from one licence", "keywords": ["three of us now", "sharing my login", "didn't know there was another way"], "confidence": 0.93, "timestamp": 9},
                {"turn": 4, "type": "upsell", "category": "Upsell", "signal": "Names admin, invoicing and shared files unprompted", "keywords": ["company invoice", "emailing PageForge files", "built for small studios"], "confidence": 0.96, "timestamp": 19},
            ],
            "lead_score_progression": [55, 68, 81, 88, 93, 95],
            "sentiment_progression": [0.35, 0.45, 0.55, 0.6, 0.65, 0.85],
            "coaching_suggestions": [
                {"turn": 0, "suggestion": "The sign-outs are licence sharing, not a fault. Explain the individual licence limit plainly before offering anything — she is not doing something wrong, she was never told.", "type": "service", "priority": "medium"},
                {"turn": 2, "suggestion": "Three users on one individual licence. Introduce Studio Cloud for teams — per-seat licences, an Admin Console, and no more sign-out conflicts.", "type": "product", "priority": "high"},
                {"turn": 4, "suggestion": "She has named admin, invoicing and file sharing herself — all three are Teams features. Recommend three Studio Cloud for teams licences: Admin Console, 1TB per user, shared libraries and company invoicing. Do not upsell beyond three seats.", "type": "closing", "priority": "high"},
            ],
            "lead_summary": {
                "type": "Upsell",
                "estimated_value": "$2,520",
                "value_note": "more, every year",
                "confidence": 0.95,
                "recommended_action": "Move from one individual All Apps licence to three Studio Cloud for teams licences — Admin Console, per-seat management, 1TB per user, shared libraries and company invoicing.",
                "urgency": "High — colleagues are being signed out of live work today",
                "offer": {
                    "from": {"product": "All Apps · Individual", "cloud": "Studio Cloud"},
                    "to": [{"product": "Studio Cloud for teams × 3", "cloud": "Studio Cloud"}],
                    "crosses_cloud": False,
                    "note": "From one licence to three, inside Studio Cloud.",
                },
                "next_steps": [
                    "Provision three Studio Cloud for teams licences and migrate her assets",
                    "Walk her through the Admin Console and seat reassignment",
                    "Switch billing to company invoicing for the accountant"
                ]
            }
        }
    },

    # ══════════════════════════════════════════════════════════════════════════
    #  CROSS-CLOUD — a Studio Cloud customer whose problem lives in Engage Cloud
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "ravi-creative-to-experience",
        "title": "Asset Chaos — Studio Cloud to Engage Cloud",
        "description": "A happy, growing team keeps publishing out-of-date images. The answer is in a different part of Acme.",
        "type": "Cross-Sell",
        "icon": "🔗",
        "customer": {
            "name": "Ravi Deshpande",
            "role": "Small business · Studio Cloud for teams",
            "company": "Small Business",
            "tier": "Studio Cloud for teams · 8 seats",
            "account_value": "$8,639/yr",
            "products": ["PhotoForge", "VectorForge", "Acme Express", "ClipForge Pro"],
            "tenure": "2 years",
            "health_score": 86,
            "usage_trend": "↑ 240 assets / month",
            "contract_renewal": "Annual · renews 30 Jan",
            "team_size": 8,
            "nps": 9
        },
        "triage": {
            "decision": "growth_engine",
            "propensity": 0.83,
            "reason": "A happy, growing team with nothing broken. What they need next — keeping track of images across four brands — is solved by a different part of Acme.",
            "suppression": None,
            "turn": 1
        },
        "conversation": [
            {"role": "customer", "text": "Hi, quick question — is there a way to stop people on my team using out-of-date versions of our product photos in Express?", "delay": 0},
            {"role": "agent", "text": "Hi Ravi. Express libraries help with a shared brand kit, but they're not really built to be a full asset library. Can I ask roughly how many assets you're managing?", "delay": 4},
            {"role": "customer", "text": "Honestly, thousands. We shoot about two hundred and forty product images a month across four brands. Right now they sit in cloud storage folders and everyone just guesses which one is approved.", "delay": 9},
            {"role": "agent", "text": "So the creative tools themselves are working — the problem is downstream of them. Finding the right approved asset, and knowing it's the current one.", "delay": 15},
            {"role": "customer", "text": "Exactly that. Last month we ran a campaign with last season's packaging on it and nobody caught it. I'd love to know which images actually drive sales too, but that feels like a completely different world.", "delay": 20},
            {"role": "agent", "text": "It's actually the same world — there's an Acme side you haven't seen yet that handles precisely this. Let me show you where it fits.", "delay": 26},
        ],
        "ai_analysis": {
            "signals": [
                {"turn": 0, "type": "cross_sell", "category": "Cross-Sell", "signal": "Version-control pain — the creative tools are fine, governance is missing", "keywords": ["out-of-date versions", "product photos"], "confidence": 0.79, "timestamp": 3},
                {"turn": 2, "type": "cross_sell", "category": "Cross-Sell", "signal": "~2,880 assets a year across four brands, no single source of truth", "keywords": ["two hundred and forty", "four brands", "everyone just guesses"], "confidence": 0.88, "timestamp": 11},
                {"turn": 4, "type": "cross_sell", "category": "Cross-Sell", "signal": "Published wrong-season creative; asks for performance measurement unprompted", "keywords": ["last season's packaging", "nobody caught it", "which images actually drive sales"], "confidence": 0.94, "timestamp": 22},
            ],
            "lead_score_progression": [48, 62, 76, 85, 92, 94],
            "sentiment_progression": [0.45, 0.5, 0.45, 0.55, 0.4, 0.8],
            "coaching_suggestions": [
                {"turn": 0, "suggestion": "This is not a Studio Cloud limitation. Be straight about what Express libraries do and do not cover — credibility here earns the rest of the conversation.", "type": "service", "priority": "medium"},
                {"turn": 2, "suggestion": "Asset volume across four brands with no governance layer. This sits in Engage Cloud — introduce ContentVault Assets, not another Studio Cloud seat.", "type": "product", "priority": "high"},
                {"turn": 4, "suggestion": "He has just described a brand-compliance failure and asked for performance measurement without prompting. Recommend ContentVault Assets for governed, versioned assets, and flag Acme Analytics as the natural follow-on. Cross-cloud opportunity — warm handoff to the Engage Cloud specialist team, do not try to close it yourself.", "type": "closing", "priority": "critical"},
            ],
            "lead_summary": {
                "type": "Cross-Sell",
                "estimated_value": "$3,600",
                "value_note": "more, every year",
                "confidence": 0.93,
                "recommended_action": "Acme ContentVault Assets for governed, versioned asset management across four brands — with Acme Analytics positioned as the follow-on for creative performance.",
                "urgency": "Medium-High — published incorrect creative last month, so brand risk is live",
                "offer": {
                    "from": {"product": "Studio Cloud for teams", "cloud": "Studio Cloud"},
                    "to": [
                        {"product": "ContentVault Assets", "cloud": "Engage Cloud"},
                        {"product": "Acme Analytics", "cloud": "Engage Cloud", "phase": "follow-on"},
                    ],
                    "crosses_cloud": True,
                    "note": "A Studio Cloud customer with an Engage Cloud need. A sales team organised by product line would not have made this offer.",
                },
                "next_steps": [
                    "Warm handoff to the Engage Cloud specialist team within 48h",
                    "Scope asset volume and brand structure for an Assets sizing",
                    "Position Acme Analytics as phase two, once assets are governed"
                ]
            }
        }
    },

    # ══════════════════════════════════════════════════════════════════════════
    #  TRANSLATED CONTACT — Spanish-speaking customer, English-speaking agent
    #  `text` is what was said. `text_en` / `text_translated` is what the Real Time
    #  Voice Translation Agent rendered for the other party.
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "lucia-sign-contracts",
        "title": "Contracts to Sign — Translated Contact",
        "description": "She speaks Spanish; the agent speaks English. She needs her clients to sign contracts.",
        "type": "Cross-Sell",
        "icon": "🌐",
        "translation": {"from": "es-ES", "to": "en-GB", "from_label": "Spanish", "to_label": "English",
                        "latency_ms": 420, "agent": "Real Time Voice Translation Agent"},
        "customer": {
            "name": "Lucía Fernández",
            "role": "Individual · VectorForge Single App",
            "company": "Consumer",
            "tier": "VectorForge · Single App",
            "account_value": "$275.88/yr",
            "products": ["VectorForge"],
            "tenure": "18 months",
            "health_score": 84,
            "usage_trend": "↑ 28% documents YoY",
            "contract_renewal": "Monthly · renews 09 Oct",
            "team_size": 1,
            "nps": 8
        },
        "triage": {
            "decision": "growth_engine",
            "propensity": 0.68,
            "reason": "Her freelance work is growing and she needs contracts signed, which her plan cannot do. The language of the call made no difference.",
            "suppression": None,
            "turn": 1
        },
        "conversation": [
            {"role": "customer", "lang": "es",
             "text": "Hola. Exporto mis ilustraciones a PDF desde VectorForge, pero mis clientes tienen que firmar los contratos, y ahora mismo los imprimo, los firman y me los escanean.",
             "text_en": "Hello. I export my illustrations to PDF from VectorForge, but my clients have to sign the contracts, and right now I print them, they sign them and scan them back to me.",
             "delay": 0},
            {"role": "agent", "lang": "en",
             "text": "Hi Lucía. The PDF export from VectorForge is working as it should — what it can't do is collect a signature. Can I ask how many contracts you send in a month?",
             "text_translated": "Hola, Lucía. La exportación a PDF desde VectorForge funciona como debe; lo que no puede hacer es recoger una firma. ¿Puedo preguntarle cuántos contratos envía al mes?",
             "delay": 5},
            {"role": "customer", "lang": "es",
             "text": "Unos quince. Soy ilustradora autónoma y cada vez tengo más clientes, algunos fuera de España. Esperar a que me devuelvan el papel firmado me retrasa los proyectos una semana.",
             "text_en": "About fifteen. I'm a freelance designer and I have more and more clients, some of them outside Spain. Waiting for the signed paper to come back delays my projects by a week.",
             "delay": 11},
            {"role": "agent", "lang": "en",
             "text": "So the illustration side is fine — the delay is in getting documents approved and signed. That's a different tool from the one you have.",
             "text_translated": "Entonces la parte de ilustración va bien; el retraso está en conseguir que los documentos se aprueben y se firmen. Esa es una herramienta distinta de la que tiene.",
             "delay": 17},
            {"role": "customer", "lang": "es",
             "text": "Exacto. Ahora mismo pago aparte por otro servicio de firmas que casi no uso porque es complicado. Si Acme tiene algo que funcione con mis PDF, prefiero tenerlo todo junto.",
             "text_en": "Exactly. Right now I'm paying for another signature service separately, and I hardly use it because it's complicated. If Acme has something that works with my PDFs, I'd rather have it all in one place.",
             "delay": 22},
            {"role": "agent", "lang": "en",
             "text": "It does, and it works directly with the PDFs you already export. Let me show you how it fits.",
             "text_translated": "Sí, lo tiene, y funciona directamente con los PDF que ya exporta. Déjeme mostrarle cómo encaja.",
             "delay": 28},
        ],
        "ai_analysis": {
            "signals": [
                {"turn": 0, "type": "cross_sell", "category": "Cross-Sell", "signal": "Document workflow gap — printing and scanning contracts for signature", "keywords": ["firmar los contratos", "los imprimo", "me los escanean"], "confidence": 0.80, "timestamp": 3},
                {"turn": 2, "type": "cross_sell", "category": "Cross-Sell", "signal": "Commercial volume growing — fifteen contracts a month, clients abroad", "keywords": ["unos quince", "cada vez tengo más clientes", "me retrasa los proyectos"], "confidence": 0.88, "timestamp": 13},
                {"turn": 4, "type": "cross_sell", "category": "Cross-Sell", "signal": "Paying a third party for e-signatures; asks for one Acme solution", "keywords": ["pago aparte", "otro servicio de firmas", "todo junto"], "confidence": 0.94, "timestamp": 24},
            ],
            "lead_score_progression": [44, 57, 72, 79, 90, 92],
            "sentiment_progression": [0.45, 0.5, 0.4, 0.5, 0.6, 0.8],
            "coaching_suggestions": [
                {"turn": 0, "suggestion": "VectorForge is doing its job. Be clear that collecting a signature is outside what an export can do — then find out the volume.", "type": "service", "priority": "medium"},
                {"turn": 2, "suggestion": "Fifteen contracts a month and growing, with a week lost on each. This is a Docs Cloud need — introduce DocuForge Pro with e-signatures.", "type": "product", "priority": "high"},
                {"turn": 4, "suggestion": "She is already paying a third party and has asked for one Acme solution. Recommend DocuForge Pro at $19.99/mo — e-signatures on the PDFs she already exports. Net off what she pays elsewhere.", "type": "closing", "priority": "high"},
            ],
            "lead_summary": {
                "type": "Cross-Sell",
                "estimated_value": "$240",
                "value_note": "more, every year",
                "confidence": 0.92,
                "recommended_action": "Add DocuForge Pro at $19.99/mo — editable PDFs and legally binding e-signatures, alongside the VectorForge plan already in place.",
                "urgency": "Medium — each contract currently costs a week of delay",
                "offer": {
                    "from": {"product": "VectorForge · Single App", "cloud": "Studio Cloud"},
                    "to": [{"product": "DocuForge Pro", "cloud": "Docs Cloud"}],
                    "crosses_cloud": True,
                    "note": "A Studio Cloud customer with a Docs Cloud need — found on a call held in two languages.",
                },
                "next_steps": [
                    "Add DocuForge Pro in-call and send the first contract for e-signature together",
                    "Send the Spanish-language quick-start for DocuForge Sign",
                    "Confirm the third-party signature service can be cancelled"
                ]
            }
        }
    },
]


# ══════════════════════════════════════════════════════════════════════════════
#  OFFER CATALOGUE — what the offer-match step draws from
#  Grouped by cloud so a cross-cloud recommendation is visibly a boundary crossing.
# ══════════════════════════════════════════════════════════════════════════════
PRODUCT_CATALOGUE = [
    {"cloud": "Studio Cloud", "tone": "acme", "products": [
        "PhotoForge", "VectorForge", "PageForge", "ClipForge Pro", "MotionForge",
        "LightVault", "Acme Express", "Glowfly", "ShapeForge 3D", "Acme Stock",
        "Acme Fonts", "ReelRoom", "Studio Cloud for teams", "Studio Cloud for enterprise"]},
    {"cloud": "Docs Cloud", "tone": "neutral", "products": [
        "DocuForge Pro", "DocuForge Sign"]},
    {"cloud": "Engage Cloud", "tone": "purple", "products": [
        "ContentVault Sites", "ContentVault Assets", "Acme Analytics",
        "Customer Journey Analytics", "Journey Composer", "Real-Time CDP",
        "Acme Target", "LeadForge Engage", "Acme Commerce", "WorkForge", "GenForge"]},
]


# ══════════════════════════════════════════════════════════════════════════════
#  AMAZON CONNECT CONTACT METADATA
#  Mirrors what an agent actually sees in the Connect agent workspace: the CCP
#  softphone, the contact record, and the attributes set by the contact flow.
# ══════════════════════════════════════════════════════════════════════════════

AGENT = {
    "name": "Alex Rivera",
    "login": "arivera",
    "routing_profile": "CC Consumer Care – Tier 1",
    "hierarchy": "EMEA / Dublin / Team 4",
    "channels": ["Voice", "Chat"],
    "instance": "acme-ccp-emea",
}

# Real-time queue metrics shown on the agent's landing view.
QUEUE_METRICS = [
    {"queue": "CC-Consumer-Photography-EN", "in_queue": 7,  "longest_wait": "01:12", "agents": 24, "sla": 88},
    {"queue": "CC-Consumer-Retention-EN",   "in_queue": 3,  "longest_wait": "02:40", "agents": 11, "sla": 79},
    {"queue": "CC-Express-Support-EN",      "in_queue": 12, "longest_wait": "00:48", "agents": 18, "sla": 92},
    {"queue": "CC-Account-Access-EN",       "in_queue": 21, "longest_wait": "03:05", "agents": 30, "sla": 74},
    {"queue": "CC-Billing-EN",              "in_queue": 9,  "longest_wait": "04:22", "agents": 14, "sla": 68},
    {"queue": "CC-SmallBusiness-EN",        "in_queue": 5,  "longest_wait": "01:34", "agents": 9,  "sla": 84},
]

# Wrap-up dispositions an agent selects during After Contact Work.
DISPOSITIONS = {
    "growth_engine": ["Upgrade accepted", "Offer declined", "Callback scheduled", "Referred to sales",
                      "No opportunity found"],
    "standard": ["Issue resolved", "Escalated to Tier 2", "Follow-up required", "No action needed"],
}

# What each disposition teaches the model. `opportunity` is the label the feedback loop
# trains on: was there a real commercial opportunity on this contact?
DISPOSITION_LABEL = {
    "Upgrade accepted":     {"opportunity": True,  "converted": True},
    "Offer declined":       {"opportunity": True,  "converted": False},
    "Callback scheduled":   {"opportunity": True,  "converted": False},
    "Referred to sales":    {"opportunity": True,  "converted": False},
    "No opportunity found": {"opportunity": False, "converted": False},
}

CONTACTS = {
    "aisha-storage-full": {
        "contact_id": "8f2a1c47-9d3e-4b21-a5f0-6c8e2b71d904",
        "channel": "VOICE", "initiation": "INBOUND",
        "queue": "CC-Consumer-Photography-EN", "queue_wait": "00:42", "priority": 3,
        "ivr_path": "Main › Studio Cloud › Storage & Sync",
        "attributes": {
            "customerSegment": "Consumer", "planCode": "PHOTO_20GB", "tenureMonths": "36",
            "authStatus": "VERIFIED", "languageCode": "en-GB", "lastContactDays": "412",
            "storageUtilisation": "100%",
        },
    },
    "tom-cancel-save": {
        "contact_id": "b41d7e60-2af8-4c19-9e73-1d5a0f83c2b6",
        "channel": "VOICE", "initiation": "INBOUND",
        "queue": "CC-Consumer-Retention-EN", "queue_wait": "01:18", "priority": 1,
        "ivr_path": "Main › Billing & Plans › Cancel Subscription",
        "attributes": {
            "customerSegment": "Consumer", "planCode": "CC_ALL_APPS", "tenureMonths": "14",
            "authStatus": "VERIFIED", "languageCode": "en-GB", "cancelIntent": "TRUE",
            "appsUsedLast30d": "2",
        },
    },
    "nina-express-premium": {
        "contact_id": "3c9f0a12-7b64-48d5-8e21-9f4c6d10b7a3",
        "channel": "CHAT", "initiation": "INBOUND",
        "queue": "CC-Express-Support-EN", "queue_wait": "00:26", "priority": 5,
        "ivr_path": "Web widget › Acme Express › Feature help",
        "attributes": {
            "customerSegment": "Consumer", "planCode": "EXPRESS_FREE", "tenureMonths": "5",
            "authStatus": "VERIFIED", "languageCode": "en-GB", "featureGateHits30d": "17",
            "designsCreated30d": "34",
        },
    },
    "marcus-generative-credits": {
        "contact_id": "d7e15b83-4c02-4f97-b6a8-2e930c5714df",
        "channel": "VOICE", "initiation": "INBOUND",
        "queue": "CC-Consumer-Photography-EN", "queue_wait": "00:55", "priority": 3,
        "ivr_path": "Main › Studio Cloud › Generative AI & Credits",
        "attributes": {
            "customerSegment": "Consumer", "planCode": "PHOTO_1TB", "tenureMonths": "24",
            "authStatus": "VERIFIED", "languageCode": "en-GB", "creditsExhaustedMonths": "3",
            "generativeUsagePct": "100%",
        },
    },
    "robert-signin": {
        "contact_id": "5a8c2f19-6e47-4d38-97b1-0c3e8a2f61bd",
        "channel": "VOICE", "initiation": "INBOUND",
        "queue": "CC-Account-Access-EN", "queue_wait": "00:19", "priority": 4,
        "ivr_path": "Main › Account & Sign-in › Password help",
        "attributes": {
            "customerSegment": "Consumer", "planCode": "PHOTO_1TB", "tenureMonths": "60",
            "authStatus": "CHALLENGE_FAILED", "languageCode": "en-GB", "signInFailures24h": "6",
        },
    },
    "priya-individual-to-teams": {
        "contact_id": "6e21b904-8c7f-4a35-b0d2-3f9a7c14e058",
        "channel": "VOICE", "initiation": "INBOUND",
        "queue": "CC-SmallBusiness-EN", "queue_wait": "01:05", "priority": 2,
        "ivr_path": "Main › Account & Sign-in › Used on another device",
        "attributes": {
            "customerSegment": "Small Business", "planCode": "CC_ALL_APPS_IND", "tenureMonths": "48",
            "authStatus": "VERIFIED", "languageCode": "en-GB", "licenceType": "INDIVIDUAL",
            "concurrentSignIns": "3", "distinctLocations": "2", "invoiceRequested": "TRUE",
        },
    },
    "ravi-creative-to-experience": {
        "contact_id": "c0847a5e-93b1-4d26-8f70-5a2e6b91d3c4",
        "channel": "VOICE", "initiation": "INBOUND",
        "queue": "CC-SmallBusiness-EN", "queue_wait": "00:37", "priority": 3,
        "ivr_path": "Main › Studio Cloud › Libraries & Sharing",
        "attributes": {
            "customerSegment": "Small Business", "planCode": "CC_TEAMS_8", "tenureMonths": "24",
            "authStatus": "VERIFIED", "languageCode": "en-GB", "licenceType": "TEAMS",
            "assetsPerMonth": "240", "brandCount": "4", "experienceSuiteOwned": "FALSE",
        },
    },
    "lucia-sign-contracts": {
        "contact_id": "2d5f8a31-0b94-4e67-a1c8-4f72e9d06b15",
        "channel": "VOICE", "initiation": "INBOUND",
        "queue": "CC-Consumer-Photography-EN", "queue_wait": "00:31", "priority": 3,
        "ivr_path": "Main › Studio Cloud › Export & PDF",
        "attributes": {
            "customerSegment": "Consumer", "planCode": "SINGLE_APP", "tenureMonths": "18",
            "authStatus": "VERIFIED", "languageCode": "es-ES", "translation": "ACTIVE",
            "pdfExports30d": "14", "documentSuiteOwned": "FALSE",
        },
    },
    "elena-double-charge": {
        "contact_id": "9b6e4d05-1f83-4a7c-8d92-7e51c0b34a28",
        "channel": "VOICE", "initiation": "INBOUND",
        "queue": "CC-Billing-EN", "queue_wait": "02:07", "priority": 1,
        "ivr_path": "Main › Billing & Plans › Incorrect charge",
        "attributes": {
            "customerSegment": "Consumer", "planCode": "CC_ALL_APPS", "tenureMonths": "72",
            "authStatus": "VERIFIED", "languageCode": "en-GB", "openCaseId": "CASE-40217",
            "repeatContact7d": "TRUE", "duplicateChargeFlag": "TRUE",
        },
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  EXECUTIVE MODEL
#  The commercial case: cost to serve vs revenue per contact, value realisation,
#  maturity position, CX guardrails and the peer benchmark. Every figure here is
#  an ASSUMPTION for sizing — the UI labels it as such throughout.
# ══════════════════════════════════════════════════════════════════════════════

EXEC_MODEL = {
    # Fully-loaded cost of handling one consumer voice contact (talk + ACW + overhead).
    "cost_per_contact": 5.90,
    "revenue_per_contact_today": 0.00,

    # Indicative year-one programme investment: platform, integration, change.
    "programme_cost_year1": 1800000,

    # Coverage ramp — share of eligible contacts running through the engine.
    # Run-rate ARR is derived from coverage so the curve stays consistent with SCALE_MODEL.
    "value_curve": [
        {"quarter": "Q1", "label": "Pilot · 1 queue",   "coverage": 0.04},
        {"quarter": "Q2", "label": "Scale · 3 queues",  "coverage": 0.22},
        {"quarter": "Q3", "label": "Full voice",        "coverage": 0.61},
        {"quarter": "Q4", "label": "Voice + chat",      "coverage": 0.88},
    ],

    # Where a contact centre sits on the journey from cost centre to growth centre.
    "maturity": [
        {"stage": 1, "name": "Cost Centre",       "detail": "Judged on the length and cost of a call. Revenue is nobody's job."},
        {"stage": 2, "name": "Service Excellence","detail": "Judged on customer satisfaction. Quality is managed; value is not."},
        {"stage": 3, "name": "Insight",           "detail": "Calls are studied afterwards. What is learned is reported, not acted on."},
        {"stage": 4, "name": "Revenue Aware",     "detail": "Opportunities are heard during the call and passed to sales."},
        {"stage": 5, "name": "Growth Centre",     "detail": "Revenue is a headline measure. Agents are coached and rewarded for it."},
    ],
    "maturity_today": 2,
    "maturity_after_pilot": 4,

    # The metrics that must NOT move. Executives ask about these before they ask about revenue.
    "guardrails": [
        {"metric": "Calls must not get longer", "target": "no more than 3%", "note": "The AI advises. The agent is never made to act on it"},
        {"metric": "Customers must stay as satisfied", "target": "no lower than today", "note": "Offers are made only where the interest is real"},
        {"metric": "Upset customers are never sold to", "target": "every time", "note": "No offer while a problem is unresolved"},
        {"metric": "Nobody is pestered", "target": "one offer, then 30 days", "note": "No customer is sold to on every call"},
    ],

    # Peer positioning — revenue attributed per contact.
    "benchmark": {
        "bottom_quartile": 0.00,
        "median": 1.90,
        "top_quartile": 4.60,
        "label": "Revenue per conversation, in contact centres like this one",
    },

    # Agent variance is the change-management argument: the tooling closes the gap.
    "agent_variance": {
        "top_quartile": 2.9,
        "bottom_quartile": 0.7,
        "unit": "leads from every 100 sales conversations",
        "note": "The best agents find four times as many as the rest. Guidance during the call is what closes that gap.",
    },

    # The engagement path. Phase 0 is the ask.
    "roadmap": [
        {"phase": "Phase 0", "name": "Value Discovery", "duration": "2 weeks",
         "detail": "Baseline your actual contact mix and size the opportunity on your data, not ours.",
         "outcome": "A business case on your numbers, and where to start"},
        {"phase": "Phase 1", "name": "Pilot", "duration": "8 weeks",
         "detail": "One queue and one team of agents, measured against the limits above.",
         "outcome": "Proof it decides well, and a first sales rate"},
        {"phase": "Phase 2", "name": "Scale", "duration": "2 quarters",
         "detail": "Expand across voice queues, then chat. Agent enablement and coaching model.",
         "outcome": "Steady revenue, part of everyday work"},
        {"phase": "Phase 3", "name": "Growth Centre", "duration": "Ongoing",
         "detail": "Revenue targets, rewards for agents, and sales traced back to the call that started them.",
         "outcome": "Contact centre reported as a growth line"},
    ],
}
