# Revenue Streams — FreeTraderHub.com

> **Part of an integrated strategy. Read alongside:**
> - `traffic-growth-plan.md` — channels that feed each stream
> - `revenue-model.md` — projections and trust rules
> - `business-model-canvas.md` — full business model
> - `roadmap.md` — when to build each stream

Five streams ranked by speed-to-revenue, trader trust alignment, and build effort.
Each stream includes the specific traffic source that activates it.

---

## Stream 1 — Prop Firm Affiliate Commissions

**Model:** Performance affiliate (CPA / revenue share)
**Primary Traffic Source:** SEO organic (comparison + rule searches) + Email list
**Roadmap Phase:** Phase 1 — revenue possible by Day 15

**How it works:**
Add clearly labelled affiliate links to comparison tables, firm profile pages, and
the rule library. When a user clicks through and purchases a challenge, FreeTraderHub
earns a commission. Disclosure: "We may earn a commission — this doesn't affect our
rule data or reviews."

**Traffic → Conversion Path:**
```
Google search: "FTMO vs FundedNext" 
  → Comparison page with affiliate links 
  → Click to firm 
  → Purchase challenge 
  → Commission ($16–$40)
```

**Target Segment:** Both challenge takers (pre-purchase research) and researchers
comparing firms before their first challenge.

**Pricing Hypothesis:**
- FTMO: 8–20% of challenge price → $200 challenge = $16–$40/referral
- FundedNext: up to 18% tiered → $100 challenge = $18/referral
- The5ers: 20–40% + lifetime revenue share → highest LTV per referral
- Conservative target: $30 avg commission × 50 conversions/month = **$1,500/month**

**Validation Experiment (< $0, 14 days):**
1. Sign up for all three affiliate programs (free, instant approval)
2. Build one "Firm Comparison Table" with UTM-tracked affiliate links
3. Share in 2–3 Discord servers contextually (see `traffic-growth-plan.md` Channel 2)
4. Measure CTR and purchase conversion over 14 days
5. Success signal: >2% CTR, >0.5% purchase conversion

**Effort:** Low | **Risk:** Medium (trust risk if disclosure inadequate)
**Revenue Timeline:** Day 15

**Trust Safeguards:**
- Disclosure label on every affiliate link
- Firm rankings driven by rule clarity, pass rate, payout speed — not commission size
- Rule accuracy maintained independently of affiliate relationship

**SEO Content That Feeds This Stream (from `traffic-growth-plan.md` Section 1B):**
- "FTMO vs FundedNext 2026 — independent comparison"
- "Best prop firm for swing trading"
- "The 7 ways traders fail FTMO challenges"

---

## Stream 2 — Pro Tool Subscription

**Model:** Freemium SaaS
**Primary Traffic Source:** Direct tool users + Discord power users → in-tool upgrade prompt
**Roadmap Phase:** Phase 2 — build after waitlist validation (Day 45–75)

**How it works:**
Current tools stay completely free (maintains trust, preserves traffic). A Pro tier unlocks:
- Saved tool sessions (persist across browser sessions and devices)
- Multi-firm comparison view (same trade through FTMO + FundedNext rules side-by-side)
- Advanced Monte Carlo: custom confidence intervals, strategy-specific inputs
- Export to PDF/CSV for trading journals
- Early access to new tools and beta features

**Traffic → Conversion Path:**
```
Discord: "How do I compare FTMO and FundedNext rules for the same trade?"
  → FreeTraderHub tool link shared
  → User runs tool, gets value
  → "Save this result" button clicked
  → Pro upgrade modal shown
  → Subscribes at $12/month
```

**Target Segment:** Serious/repeat challenge takers — traders who have failed at
least one challenge and treat prop trading as a semi-professional activity.

**Pricing Hypothesis:**
- Free: current tools, no account required
- Pro: $12/month or $99/year (31% annual discount)
- A/B test: $9/month vs $19/month — hypothesis $12 is the sweet spot

**Validation Experiment (< $200, 30 days):**
1. Add a ghost "Save session" button to Position Sizer (no functionality yet)
2. On click: modal — "Save sessions across devices — coming to Pro. Join waitlist."
3. Measure click rate over 30 days without building anything
4. Share in Discord; observe which power-user questions reveal need for multi-firm view
5. Success signal: >5% of tool users click the gated feature; >50 waitlist signups

**Effort:** Medium (auth + billing + feature gates)
**Risk:** Low (free tier untouched; Pro is additive)
**Revenue Timeline:** Month 2–3

**Upsell Trigger:**
The highest-value upgrade moment is when a user runs Monte Carlo and gets a low
pass probability. Show: "Run this with your exact strategy parameters — upgrade to Pro."

**Tech Stack:**
- Auth: Clerk (free to 10K MAU)
- Billing: Stripe
- Feature flags: PostHog free tier

---

## Stream 3 — Firm Rule-Change Alert Subscription

**Model:** Data subscription / premium newsletter tier
**Primary Traffic Source:** Email list (captured from tools + SEO content)
**Roadmap Phase:** Phase 2 — launch at 250 email subscribers (Day 30–50)

**How it works:**
Prop firms change rules (drawdown thresholds, consistency requirements, max daily loss)
with little or no notice. A rule change mid-challenge can turn a passing strategy into
a failing one overnight. FreeTraderHub already maintains the rule library — the delta
between versions is the product.

- Free tier: view current rules on site
- Alert tier ($7/month): email notification when a firm you follow changes a rule,
  with a plain-English diff:
  > "FTMO Normal plan: max daily loss changed from 5% to 4% effective May 1.
  > If you're mid-challenge with a $100K account, your daily floor is now $4,000
  > instead of $5,000. Here's how to adjust your position sizing: [tool link]"

**Traffic → Conversion Path:**
```
SEO article: "What happens when a prop firm changes its rules mid-challenge"
  → Reader subscribes to email list
  → Nurture email Day 9: "Last month FundedNext changed this rule..."
  → Nurture email Day 14: "Want instant alerts? → Rule Alert upgrade"
  → Subscribes at $7/month
```

**Target Segment:** Active challenge takers managing live funded accounts or
mid-challenge evaluations — the users with the most to lose from missing a rule change.

**Pricing Hypothesis:** $7/month. Less than 1/10th of the cheapest challenge fee.
ROI is obvious: one avoided breach pays for 14+ months of subscription.

**Validation Experiment (< $100, 21 days):**
1. Post Tally or Typeform survey to email list and 2 Discord servers:
   "Would you pay $7/month for instant alerts when FTMO or FundedNext changes rules?"
2. Collect email pre-commitments (not credit cards — lower friction, still signal)
3. Success signal: >80 pre-commitments in 21 days

**Effort:** Low-Medium (rule library already maintained; delta detection adds 2–4 weeks)
**Risk:** Low (solves a clear, expensive pain point; low churn)
**Revenue Timeline:** Month 1–2

**Lowest-Effort Build Option:**
Use Beehiiv's paid subscription feature. When a rule changes, manually (or via script)
trigger a premium broadcast. No custom auth or billing code needed.

**Compound Benefit:** Alert subscribers are the highest-value affiliate targets.
A rule change alert naturally leads to: "FundedNext just tightened their rules —
here's how they compare to FTMO this month [affiliate link]."

---

## Stream 4 — Prop Firm Challenge Prep Course

**Model:** One-time digital product (evergreen)
**Primary Traffic Source:** Email list (1,000+ required) + Educator partnerships
**Roadmap Phase:** Phase 2–3 — pre-sell at Day 90 if waitlist >30

**How it works:**
A structured, self-paced course:
- Module 1: Anatomy of a prop challenge (rule types, evaluation phases, common traps)
- Module 2: Risk management for challenges (position sizing, daily limits, scaling)
- Module 3: Reading firm rules correctly (worked examples from the rule library)
- Module 4: Using FreeTraderHub tools in a live challenge context
- Module 5: What to do after you pass (funded account risk management)

Delivered via Gumroad or Podia. Video (Loom) + written guides. Lifetime access.

**Traffic → Conversion Path:**
```
Educator partnership: "I recommend FreeTraderHub tools to all my students"
  → Students visit site
  → Join email list
  → Receive launch email: "The challenge prep course is live — $97 for 48 hours"
  → Purchase ($147)
```

**Target Segment:** New traders preparing for their first challenge, or repeat failures
seeking a systematic approach rather than just better tools.

**Pricing Hypothesis:** $147 standard / $97 launch price for first 50 students.
Framing: "One course purchase = the cost of one avoided challenge failure."

**Validation Experiment (< $50, 30 days):**
1. Publish a long-form guide: "Complete guide to not failing your FTMO challenge" (free)
2. At the end: "Want the full structured course? Join the waitlist — $97 for first 50."
3. Share the guide via Discord, Reddit, and email list
4. Success signal: >30 waitlist signups. Pre-sell before recording.

**Effort:** High (5–8 hours video, scripts, platform setup)
**Risk:** Medium (content can go stale; mitigate with principles-first framing)
**Revenue Timeline:** Month 2–3 (after pre-sell validation)

**Educator Partnership Activation (from `traffic-growth-plan.md` Channel 5):**
Educators earn 30–40% on course referrals. This turns every educator partnership
into a distribution channel specifically for this stream.

**Pricing Ladder:**
Free tools → $7/mo alerts → $12/mo Pro → $147 course → (future) $497 coaching

---

## Stream 5 — Sponsored Firm Listings (Directory Model)

**Model:** B2B sponsored placement — clearly labelled
**Primary Traffic Source:** Media kit (requires 8,000+ monthly visitors + 1,000+ email list)
**Roadmap Phase:** Phase 3 — pursue only after traffic threshold met (Day 120–180)

**How it works:**
Expand the rule library into a full prop firm directory. Smaller/newer firms pay for
a "Featured" badge, priority placement in comparison tables, and a verified profile
page with their own messaging. Editorial content and rule data remain 100% independent.

**B2B Traffic → Conversion Path:**
```
Prop firm marketing team Googles "prop firm comparison site"
  → Finds FreeTraderHub directory
  → Sees traffic data in media kit
  → Pays $300/month for Featured listing
```

**Target Segment (B2B):** Newer prop firms trying to build credibility against FTMO.
Budget: $200–$500/month per firm.

**Pricing Hypothesis:**
- Featured listing: $300/month
- Maximum 3 sponsors (maintains perceived neutrality)
- Annual prepay: $2,500/year (30% discount)

**Validation Experiment (< $0, 30 days):**
1. Add 2–3 new firm profiles to rule library (free; demonstrates directory intent)
2. Build a simple media kit (traffic, list size, audience demographics)
3. Cold email 5 smaller prop firms with free 30-day trial offer
4. Success signal: >1 firm agrees to paid listing after trial

**Effort:** Low (directory is essentially built; "Featured" badge is minimal)
**Risk:** High trust risk if firms feel listing creates editorial obligation
**Mitigation:** Explicit contract: sponsored firms cannot change rule data or scores
**Revenue Timeline:** Month 3–4

---

## Scoring Summary

| Stream | Monthly Rev (Yr 1) | Effort | Risk | Time to $1 | Primary Traffic Source |
|---|---|---|---|---|---|
| 1. Affiliate | $1,500 | Low | Medium | 15 days | SEO + Email |
| 2. Pro tools | $960 | Medium | Low | 60–90 days | Discord + Direct |
| 3. Rule alerts | $840 | Low-Med | Low | 30–60 days | Email list |
| 4. Course | $1,470 | High | Medium | 60–90 days | Email + Educators |
| 5. Sponsored listings | $600 | Low | High | 90–120 days | Media kit |
| **Total** | **$5,370/mo** | | | | |

**Priority order:** 1 → 3 → 2 → 4 → 5

**Traffic dependency:**
- Streams 1 and 3 need 2,000+ monthly visitors (achievable Month 1–2 via SEO + Discord)
- Stream 2 needs 200+ active tool users/month (achievable Month 1)
- Stream 4 needs 1,000+ email subscribers (achievable Month 2–3)
- Stream 5 needs 8,000+ monthly visitors (achievable Month 4–5)

See `traffic-growth-plan.md` for how to hit each traffic threshold.
