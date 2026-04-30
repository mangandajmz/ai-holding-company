# Traffic Growth Plan — FreeTraderHub.com

> This document feeds directly into `roadmap.md` (phase milestones) and
> `revenue-streams.md` (which channels activate which streams).
> Traffic is the top of the funnel. Everything downstream depends on it.

---

## The Traffic Architecture

Traffic does not flow uniformly into all revenue streams. Different channels
attract different user types at different intent levels:

```
Channel                  → Primary Intent         → Best Revenue Stream
─────────────────────────────────────────────────────────────────────────
Google Organic (SEO)     → High (problem search)  → Affiliate + Alerts
Trading Discords         → Very High (active)      → Pro Tools + Alerts
Reddit / Forums          → Medium (research)       → Affiliate + Course
YouTube / Shorts         → Low-Medium (discovery)  → Email list → all
Email List               → Highest (trust built)   → All streams
Educator Partnerships    → High (referred trust)   → Course + Pro Tools
```

**One Metric That Matters First:** Monthly unique visitors.
Everything else (email signups, affiliate clicks, subscriptions) is a ratio of traffic.
Target: **10,000 monthly unique visitors within 90 days** of executing this plan.

---

## Channel 1 — SEO (Programmatic + Editorial)

**Why SEO first:** The prop firm niche has high search volume, low-quality existing
content (most sites are thin affiliate pages), and FreeTraderHub's rule library is
a structural SEO advantage that competitors cannot easily replicate.

### 1A — Programmatic SEO (The Rule Library as Content Engine)

Each firm × plan × rule type = a unique, indexable page with genuine utility.
With 3 firms, 13 plans, and 94 rules, that's a foundation for 200–500 pages.

**Target URL structure:**
```
/rules/{firm}/{plan}/{rule-type}
  → /rules/ftmo/normal/max-daily-loss
  → /rules/fundednext/stellar/trailing-drawdown
  → /rules/the5ers/hyper-growth/consistency-rule

/tools/{tool-name}/{instrument}
  → /tools/position-sizer/eurusd
  → /tools/pass-probability/nasdaq

/compare/{firm-a}-vs-{firm-b}
  → /compare/ftmo-vs-fundednext
  → /compare/ftmo-vs-the5ers-swing-trader
```

**Priority programmatic pages (build first):**

| Page | Search Intent | Monthly Searches (est.) | Affiliate Opportunity |
|---|---|---|---|
| FTMO vs FundedNext | Research | 3,000–8,000 | High |
| FTMO max daily loss rule | Problem | 1,000–2,000 | Medium |
| FundedNext trailing drawdown | Problem | 500–1,500 | Medium |
| Best prop firm for swing trading | Research | 1,000–3,000 | High |
| How to pass FTMO challenge | Problem | 5,000–15,000 | High |
| The5ers consistency rule explained | Problem | 300–800 | Low |
| Prop firm position size calculator | Tool | 1,000–3,000 | Medium |

**Structured data to add:**
- FAQPage schema on all rule pages (triggers rich results in Google)
- HowTo schema on tool pages
- BreadcrumbList on all pages

### 1B — Editorial SEO (Long-Form "Field Notes")

High-value, high-effort pages that capture featured snippets and establish authority.
These are not thin pages — they are the best resource on the internet for that query.

**Target editorial pieces (one per month):**
1. "Complete guide to prop firm drawdown rules — every type explained" (pillar page)
2. "How to read a prop firm's terms of service without getting burned"
3. "The 7 ways traders fail FTMO challenges (and how to avoid each one)"
4. "FTMO vs FundedNext 2026: independent comparison with no affiliate bias"
5. "What happens when a prop firm changes its rules mid-challenge"
6. "Monte Carlo simulation for traders: how to know your actual pass probability"

**Each piece should:**
- Be 2,000–4,000 words
- Include the FreeTraderHub tools in context (natural tool embed)
- Have a single email capture CTA ("Get rule change alerts")
- Link to relevant programmatic pages in the rule library

### 1C — SEO Technical Checklist

- [ ] Submit XML sitemap to Google Search Console
- [ ] Verify Core Web Vitals (tools are already lightweight — maintain this)
- [ ] Add canonical tags to prevent duplicate rule pages
- [ ] Internal linking: every rule page links to the relevant tool
- [ ] Every tool page links to the relevant rule pages

**SEO Traffic Target:**

| Month | Target Monthly Organic Visitors |
|---|---|
| Month 1 | Baseline (measure current) |
| Month 2 | +50% (programmatic pages indexed) |
| Month 3 | +150% (editorial pages gaining traction) |
| Month 4 | +300% |
| Month 6 | 8,000–15,000/month |

---

## Channel 2 — Trading Discord Communities

**Why Discord:** Prop firm traders are highly concentrated in Discord servers.
These communities have 10,000–100,000+ members actively discussing challenges.
A single tool mention in the right server can drive 500+ sessions in a day.

### Target Communities

| Community Type | Examples | Strategy |
|---|---|---|
| FTMO-focused servers | FTMO Official, Unofficial FTMO traders | Share tool when relevant to discussion |
| Prop firm general | r/Propfirm Discord, Funded Traders | Post tool links in #resources channels |
| Forex/trading | BabyPips, ForexFactory Discord | Contextual mentions when rule questions arise |
| Educator servers | Popular trading educators' communities | Partnership approach (see Channel 5) |

### Playbook

**Week 1:** Join 10 relevant Discord servers as a genuine participant.
Do not post tool links immediately. Observe conversations, understand pain points.

**Week 2–3:** Answer rule questions with genuine help. When relevant, mention
the tool naturally: "I've been using freetraderhub.com's loss limit tracker for
exactly this — it handles trailing drawdown automatically."

**Week 4+:** Build relationships with server moderators. Offer:
- A dedicated invite link for their community (trackable UTM)
- A "Resource of the month" feature if the server has one
- Co-create a pinned FAQ post using the rule library as the source

**Avoid:** Spam posting, unsolicited DMs, posting the same message in multiple servers.
The trading community is tight-knit — reputation damage spreads fast.

**Discord Traffic Target:** 1,000–3,000 monthly referral sessions by Month 3.

---

## Channel 3 — Reddit

**Relevant subreddits:**
- r/Forex (large, active)
- r/Forexstrategy
- r/PropFirms (niche, high intent)
- r/Daytrading
- r/algotrading

**Strategy:**
Same as Discord — genuine participation first, tools mentioned in context.
Reddit upvotes evergreen content; a well-answered post stays visible for years.

**High-value Reddit content formats:**
- "I made a Monte Carlo tool to estimate your prop challenge pass rate — here's
  what I found after testing 10,000 simulations" (tool showcase with data)
- "Prop firm rule cheat sheet for 2026 — rules compared across FTMO, FundedNext,
  The5ers" (rule library as a shareable resource)
- "AMA: I track rule changes across every major prop firm — ask me anything"

**Reddit Traffic Target:** 500–2,000 monthly referral sessions by Month 2 (posts have
long tails; early posts keep driving traffic for months).

---

## Channel 4 — YouTube & Short-Form Video

**Why video:** Many prop firm traders are visual learners who watch YouTube tutorials.
Tool demos convert extremely well in video format. A 5-minute video showing
"How I use FreeTraderHub to avoid failing my FTMO challenge" is both a traffic
driver and a trust builder.

### Option A — Owned Channel (Higher effort, higher compounding)

Build a FreeTraderHub YouTube channel:
- Format: 5–10 minute tool walkthroughs and rule explainers
- Upload cadence: 2 videos per month minimum
- Topics: mirror editorial SEO pieces as video versions

**YouTube Shorts / TikTok (lower effort, faster reach):**
- 60-second format: "One rule that kills most FTMO challenges — and how to track it"
- Screen recording of the tool in action
- No production cost — screen record + voiceover is sufficient

### Option B — YouTube Partnerships (Lower effort, faster results)

Identify 5–10 trading YouTubers who cover prop firms (search "FTMO review" on YouTube
— channels with 10K–200K subscribers are the sweet spot: large enough to drive traffic,
small enough to say yes to a free collaboration).

**Partnership offer:**
- Free Pro account + a custom affiliate link earning them 30% of referred subscriptions
- Provide a pre-written tool tutorial script they can adapt
- Ask for an honest tool review in a "prop firm toolkit" video

**Video Traffic Target:** 1,000–5,000 monthly sessions by Month 4 (slower to build
than SEO or Discord, but high-trust and compounds via YouTube search).

---

## Channel 5 — Trading Educator Partnerships

**Why educators:** Trading coaches and course creators have pre-built audiences
of exactly the right users — traders preparing for prop firm challenges.
A single educator endorsement can drive more qualified traffic than months of SEO.

### Ideal Partner Profile

- Runs a trading course or coaching program ($200–$2,000+)
- Covers prop firm trading or forex/futures
- Audience: 5,000–50,000 followers across YouTube, Discord, or email
- Not yet partnered with a competing tool

### Partnership Models

**Model A — Tool Embed / Recommendation**
Educator mentions or recommends FreeTraderHub tools to their students.
In return: Pro account, co-branded landing page, or revenue share on upgrades.

**Model B — Co-Created Content**
Co-author a "Prop Firm Challenge Toolkit" guide that both parties distribute.
Educator gets content; FreeTraderHub gets email capture and traffic.

**Model C — Affiliate Share on Course Sales**
If FreeTraderHub launches a course (Stream 4), educators can earn 30–40%
commission for referring students. High-incentive, low-effort for the educator.

**Outreach sequence (5 targets per month):**
1. Genuinely engage with their content for 1 week
2. DM or email: "I built the tools your students need — want to take a look?"
3. Offer a free Pro account with no strings attached
4. Follow up once; if no response, move to next target

**Partnership Traffic Target:** 500–3,000 monthly sessions from educator referrals
by Month 3. Quality is higher than any other channel — these users convert.

---

## Channel 6 — Email List (The Compound Asset)

The email list is not just a revenue channel — it is the traffic multiplier.
Every email sent to the list generates a traffic spike independent of search or social.

### Email List Growth Tactics

**On-site capture (highest priority):**
- Exit-intent popup: "Get a free rule change alert — we'll email you when FTMO
  or FundedNext updates their rules." (Not "subscribe to our newsletter.")
- Tool completion CTA: After running Monte Carlo, show "Save this result and get
  notified when firm rules change — enter your email."
- Rule library: After viewing any rule page: "Get alerted when this rule changes."
- Inline in blog posts: Single field, value-specific ask, not generic subscribe.

**Off-site capture:**
- Discord and Reddit: Link to a free "2026 Prop Firm Rule Cheat Sheet" PDF
  gated behind email (Beehiiv or ConvertKit landing page, <30 min to build)
- YouTube: "Download the free rule comparison sheet" in every video description

**Email List Milestones (tied to revenue unlocks):**

| List Size | What It Unlocks |
|---|---|
| 100 subscribers | Send rule alert survey (Stream 3 validation) |
| 250 subscribers | Launch rule alert paid tier (Stream 3) |
| 500 subscribers | Pro tool waitlist launch email |
| 1,000 subscribers | Course pre-sell (minimum viable list for a launch) |
| 2,500 subscribers | Media kit ready for sponsored listings (Stream 5) |
| 5,000 subscribers | Full newsletter monetisation; B2B outreach viable |

### Email Nurture Sequence (New Subscribers)

| Email | Day | Content |
|---|---|---|
| Welcome | 0 | "Here's the rule cheat sheet you asked for + 3 ways to use the tools" |
| Value | 2 | "The trailing drawdown trap that kills 60% of FTMO challenges" |
| Tool tutorial | 5 | "How to use the Monte Carlo simulator before buying a challenge" |
| Rule change story | 9 | "Last month FundedNext changed this rule — here's what happened" |
| Soft offer | 14 | "Want instant alerts when this happens again? [Rule Alert upgrade]" |

---

## Traffic → Revenue Funnel Map

Every traffic channel feeds the email list. The email list feeds all revenue streams.

```
SEO Organic ──────────┐
Discord/Reddit ────────┤
YouTube ───────────────┼──→ LANDING PAGE / TOOL USE ──→ EMAIL LIST
Educator Referrals ────┤                                      │
Direct/Word of Mouth ──┘                                      │
                                                              ▼
                                               ┌─────────────────────────┐
                                               │  Nurture Sequence       │
                                               │  (5 emails, 14 days)    │
                                               └─────────────────────────┘
                                                              │
                              ┌───────────────┬──────────────┼──────────────┬───────────────┐
                              ▼               ▼              ▼              ▼               ▼
                         Affiliate       Rule Alert      Pro Tools      Course        Sponsored
                         (passive)       ($7/mo)         ($12/mo)       ($147)        Listings
                         Day 15          Month 1–2       Month 2–3      Month 3       Month 4
```

---

## Traffic KPI Dashboard

| KPI | Month 1 | Month 2 | Month 3 | Month 6 |
|---|---|---|---|---|
| Monthly unique visitors | baseline | +50% | +150% | +500% |
| Organic search sessions | baseline | +30% | +100% | +400% |
| Discord/Reddit referral sessions | 0 | 300 | 1,000 | 2,500 |
| YouTube referral sessions | 0 | 0 | 300 | 1,500 |
| Email list size | 0 | 100 | 500 | 2,500 |
| Email open rate | — | 45%+ | 40%+ | 35%+ |
| Email click rate | — | 8%+ | 6%+ | 5%+ |
| Tool session duration | baseline | +10% | +20% | +30% |

---

## Traffic Growth Risk Register

| Risk | Mitigation |
|---|---|
| Google algo update devalues programmatic pages | Mix with editorial content; build backlinks naturally |
| Discord bans promotional content | Lead with value, never spam; build relationships first |
| YouTube algorithm ignores small channel | Partner with existing channels before building owned |
| Email open rates drop | Segment list; send rule-specific alerts not generic newsletters |
| One educator drives 80% of referral traffic | Diversify to 5+ educator partnerships |
