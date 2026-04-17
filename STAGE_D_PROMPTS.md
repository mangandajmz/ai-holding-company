# Stage D — Integration Readiness Sprint
## Claude Code Prompts

**How to use this file:**
Copy one prompt block at a time into Claude Code. Complete each block fully and verify its
success criteria before moving to the next. Blocks are ordered by dependency — do not skip ahead.

**Philosophy reminder (per CLAUDE.md):**
- No overengineering. Make the smallest change that closes the gap.
- No new files unless genuinely justified.
- No refactoring of working code that isn't in the path of the fix.
- `shell=False` always for any subprocess calls.
- Read PLAN.md before touching anything.

**Code Review Gate (per CLAUDE.md — mandatory after every block):**
After each block's success criteria pass, run a Codex review on all files touched in
that block before moving to the next. Check style/linting, logic, and security.
Full gate definition is in CLAUDE.md → "Code Review Gate" section.

---

## BLOCK 1 — projects.yaml Path Corrections
> Do this first. All monitoring depends on it.

```
Read PLAN.md completely before doing anything. Every rule in that file applies to this task.

Your job is to correct the broken file paths in config/projects.yaml. This is a config-only
change — do not touch any source code, bot logic, or website files.

CONTEXT:
All four portfolio projects have moved from OneDrive/Manganda LTD into the ai-holding-company
folder. The paths in config/projects.yaml still point to the old locations and must be updated.
The new root for all projects is:
  C:/Users/james/OneDrive/Documents/Claude/Projects/AI Holding Company/ai-holding-company

Before making any change, verify that each new path actually exists on disk.

CHANGES REQUIRED in config/projects.yaml:

1. trading_bots[id=mt5_desk]
   repo_path:
     OLD: C:/Users/james/OneDrive/Documents/Manganda LTD/AI Models/mt5-agentic-desk
     NEW: C:/Users/james/OneDrive/Documents/Claude/Projects/AI Holding Company/ai-holding-company/mt5-agentic-desk
   Also update the report and health command paths that reference the old ai-holding-company
   location — replace any hardcoded C:/Users/james/OneDrive/Documents/Manganda LTD/AI Models/
   ai-holding-company prefix with the new root path above.

2. trading_bots[id=polymarket]
   repo_path:
     OLD: C:/Users/james/OneDrive/Documents/Manganda LTD/Trading/polymarket-bot
     NEW: C:/Users/james/OneDrive/Documents/Claude/Projects/AI Holding Company/ai-holding-company/polymarket-bot
   remote_readonly.ssh_key_path stays unchanged: C:/Users/james/.ssh/ai_capital_vps
   Also update any hardcoded command paths that reference the old location.

3. websites[id=freeghosttools]
   local_project_path:
     OLD: C:/Users/james/OneDrive/Documents/Manganda LTD/Tools/free-utility-tools
     NEW: C:/Users/james/OneDrive/Documents/Claude/Projects/AI Holding Company/ai-holding-company/free-utility-tools
   local_sitemap_path:
     OLD: C:/Users/james/OneDrive/Documents/Manganda LTD/Tools/free-utility-tools/sitemap.xml
     NEW: C:/Users/james/OneDrive/Documents/Claude/Projects/AI Holding Company/ai-holding-company/free-utility-tools/sitemap.xml

4. websites[id=freetraderhub] — THIS ENTRY NEEDS SPLITTING INTO TWO
   The current entry points to the research team folder, not the website.
   Replace the single freetraderhub entry with two separate entries:

   Entry A — the website:
     id: "freetraderhub_website"
     name: "FreeTraderHub"
     url: "https://freetraderhub.com/"
     timeout_sec: 10
     local_project_path: "C:/Users/james/OneDrive/Documents/Claude/Projects/AI Holding Company/ai-holding-company/finance_web_page"

   Entry B — the research team:
     id: "freetraderhub_research"
     name: "FreeTraderHub Research Team"
     url: "https://freetraderhub.com/"
     timeout_sec: 10
     local_project_path: "C:/Users/james/OneDrive/Documents/Claude/Projects/AI Holding Company/ai-holding-company/free-traderhub-research-team"
     local_reports_base: "C:/Users/james/OneDrive/Documents/Claude/Projects/AI Holding Company/ai-holding-company/free-traderhub-research-team/reports"
     local_reports_glob: "*/00_executive_brief.md"

5. future_divisions — update both repo_path values:
   research_division_seed:
     OLD: C:/Users/james/OneDrive/Documents/Manganda LTD/AI Models/free-traderhub-research-team
     NEW: C:/Users/james/OneDrive/Documents/Claude/Projects/AI Holding Company/ai-holding-company/free-traderhub-research-team
   websites_division_seed:
     OLD: C:/Users/james/OneDrive/Documents/Manganda LTD/Tools/free-utility-tools
     NEW: C:/Users/james/OneDrive/Documents/Claude/Projects/AI Holding Company/ai-holding-company/free-utility-tools

RULES:
- Only edit config/projects.yaml. No other files.
- Do not change any values other than the paths listed above.
- Do not add new keys, restructure the YAML, or change indentation style.
- Verify each new path resolves before writing it.

SUCCESS CRITERIA:
- All paths in config/projects.yaml resolve to directories that exist on disk.
- No path contains "Manganda LTD" anywhere in the file.
- YAML is valid — run a syntax check after editing.
- The freetraderhub entry has been split into freetraderhub_website and freetraderhub_research.
```

> **→ CODEX REVIEW GATE** — run on `config/projects.yaml` before starting Block 2.
> Check: YAML syntax, no secrets, no hardcoded credentials. Full gate in CLAUDE.md.

---

## BLOCK 2 — Messaging Conflicts
> Complete Block 1 first. These are website source changes — CEO-approved per PLAN.md §5.

```
Read PLAN.md completely before doing anything. Every rule in that file applies to this task.

Per PLAN.md §5, website source changes require CEO approval. This task IS that approval —
the CEO has explicitly issued this as a goal. Log this as a CEO-approved website change.

Your job is to fix two honesty problems in the website copy before any monetization work
begins. Make the smallest change that removes the false claim. Do not redesign, rewrite,
or restructure any page.

---

FIX 1 — FreeGhostTools: Remove false AdSense claim and dead ad scripts
File: free-utility-tools/about.html

There are three things to remove:

a) The AdSense script tag in the <head> (loads a script for a pub-id that doesn't exist):
   Remove this entire line:
   <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXXX" crossorigin="anonymous"></script>

b) The false claim in the about-callout__text div. Replace only the sentence about AdSense
   and affiliate partnerships. The current text reads:
     "FreeGhostTools is supported by non-intrusive display advertising via Google AdSense
      and small commissions from affiliate partnerships with services like NordVPN, Grammarly,
      Wise, FreshBooks, and Adobe Acrobat. These partnerships let us keep every tool free —
      no paywalls, no accounts, no limits."
   Replace with:
     "FreeGhostTools is kept free through small commissions from affiliate partnerships.
      We plan to introduce non-intrusive advertising in future and will notify users before
      doing so. No paywalls, no accounts, no limits — ever."

c) Any <ins class="adsbygoogle"> ad slot blocks and their associated inline <script> push
   calls that reference ca-pub-XXXXXXXXXXXXXXXXX. Remove the entire block for each ad slot
   found (the <ins> tag and its paired <script>(adsbygoogle = ...).push({})</script>).
   Do not remove surrounding layout divs — only the ad tags themselves.

---

FIX 2 — FreeGhostTools: Remove placeholder affiliate links across all tool pages
15 HTML files contain affiliate links where the ID is still the literal text AFFILIATE_ID.
These are dead links that earn nothing and look unprofessional if inspected.

The affected files are:
  case-converter.html, compress-image.html, compress-pdf.html, convert-image.html,
  currency-converter.html, jpg-to-pdf.html, loan-calculator.html, merge-pdf.html,
  pdf-to-jpg.html, pdf-to-word.html, remove-background.html, resize-image.html,
  split-pdf.html, word-counter.html, word-to-pdf.html

For each file:
- Find every <a> tag whose href contains the literal string "AFFILIATE_ID".
- If the link is a standalone affiliate banner block (class="affiliate-banner" or similar),
  remove the entire banner element including its parent wrapper div if that wrapper contains
  only the banner. Do not remove surrounding layout or navigation.
- If the AFFILIATE_ID link is inline within body text (e.g. the Canva Pro mention in
  convert-image.html), replace the <a> tag with a plain <span> preserving the link text.
- Do not remove the NordVPN affiliate link (aff_id=144709 via Impact.com) — that one is
  live and correct.

---

FIX 3 — FreeTraderHub: Update "no ads" meta copy
File: finance_web_page/index.html

Two meta tags need updating before any monetization can be introduced on this site.

Line 26 — og:description:
  CURRENT: "Free position size and drawdown calculator for forex, stocks, crypto and futures
            traders. No ads, no sign-up, runs in your browser."
  NEW:     "Free position size and drawdown calculator for forex, stocks, crypto and futures
            traders. No sign-up, privacy-first, runs entirely in your browser."

Line 39 — twitter:description:
  CURRENT: "FreeTrader Hub — Free position size calculator, drawdown calculator and live
            market headlines. No signup, no ads, no cost."
  NEW:     "FreeTrader Hub — Free position size calculator, drawdown calculator and live
            market headlines. No signup, privacy-first, no cost."

Line 1533 — footer text (small, inside a div):
  CURRENT: "No subscriptions, no ads, no data collection. Runs entirely in your browser."
  NEW:     "No subscriptions, no data collection. Runs entirely in your browser."

Only edit the three strings above. Touch nothing else in index.html.

---

RULES (apply to all three fixes):
- Edit only the specific strings described. No layout, style, or logic changes.
- Do not add, move, or rename any files.
- Do not touch any JavaScript tool logic.
- Per PLAN.md R3: these are the only website source changes authorised in this task.

SUCCESS CRITERIA:
- grep for "ca-pub-XXXXXXXXXXXXXXXXX" in free-utility-tools/ returns zero results.
- grep for "adsbygoogle" in free-utility-tools/ returns zero results.
- grep for "AFFILIATE_ID" across all free-utility-tools HTML files returns zero results.
- grep for "no ads" (case-insensitive) in finance_web_page/index.html returns zero results.
- NordVPN affiliate link (aff_id=144709) is still present and unchanged.
```

> **→ CODEX REVIEW GATE** — run on all modified HTML files + `finance_web_page/index.html` before Block 3.
> Check: valid HTML structure, no broken tags, no accidental content removal. Full gate in CLAUDE.md.

---

## BLOCK 3 — Umami Analytics on FreeGhostTools
> Complete Blocks 1 and 2 first. CEO-approved website change per PLAN.md §5.

```
Read PLAN.md completely before doing anything. Every rule in that file applies to this task.

Per PLAN.md §5, website source changes require CEO approval. This task IS that approval.

Your job is to add Umami analytics to all 25 HTML pages in free-utility-tools/. This is the
same privacy-first analytics stack already live on FreeTraderHub. No new infrastructure —
same Umami deployment, new project within it.

IMPORTANT — DO THIS STEP FIRST (manual, not automated):
Before running this task, a new Umami project for FreeGhostTools must be created at:
  https://umami-kappa-lake.vercel.app
Go to Settings → Websites → Add Website → name it "FreeGhostTools" → copy the website ID.

If you do not have the FreeGhostTools website ID yet, STOP and ask the CEO for it before
proceeding. Do not reuse the FreeTraderHub website ID (60daf4ca-e7a2-46fb-8fd1-02db81e4fbef).

---

STEP 1 — Add Umami script to all 25 HTML pages.

The Umami snippet to add (replace FREEGHOSTTOOLS_WEBSITE_ID with the real ID):

  <!-- Umami Analytics -->
  <script defer
    src="https://umami-kappa-lake.vercel.app/script.js"
    data-website-id="FREEGHOSTTOOLS_WEBSITE_ID">
  </script>

Add this snippet immediately before the closing </head> tag on every .html file in
free-utility-tools/. The 25 files are:
  404.html, about.html, age-calculator.html, case-converter.html, compress-image.html,
  compress-pdf.html, contact.html, convert-image.html, currency-converter.html, index.html,
  jpg-to-pdf.html, loan-calculator.html, merge-pdf.html, password-generator.html,
  pdf-to-jpg.html, pdf-to-word.html, percentage-calculator.html, privacy.html,
  qr-code-generator.html, remove-background.html, resize-image.html, split-pdf.html,
  terms.html, word-counter.html, word-to-pdf.html

Do not add the snippet if a Umami script tag is already present on a page.

---

STEP 2 — Add named event tracking to the NordVPN affiliate link.

The NordVPN affiliate link (href contains "aff_id=144709") appears on age-calculator.html.
Find it and add the attribute:
  data-umami-event="affiliate-click"
  data-umami-event-partner="nordvpn"

Example result:
  <a href="https://...aff_id=144709..." data-umami-event="affiliate-click"
     data-umami-event-partner="nordvpn" ...>

If the NordVPN link appears on other pages too, add the same attributes to those instances.

---

RULES:
- Only add the Umami snippet and the two data attributes. No other changes.
- Do not alter page layout, styles, or any tool logic.
- If the website ID has not been provided, stop and ask before editing any file.
- Per PLAN.md R3: no other website source changes are authorised in this task.

SUCCESS CRITERIA:
- Every .html file in free-utility-tools/ contains exactly one Umami script tag.
- All 25 files contain "umami-kappa-lake.vercel.app".
- The NordVPN link on age-calculator.html has data-umami-event="affiliate-click".
- No FreeTraderHub website ID (60daf4ca-...) appears anywhere in free-utility-tools/.
```

> **→ CODEX REVIEW GATE** — run on all 25 modified HTML files before Block 4.
> Check: exactly one Umami script per page (no duplicates), valid HTML, correct data attribute syntax. Full gate in CLAUDE.md.

---

## BLOCK 4 — Polymarket SSH Diagnosis
> Can run in parallel with Blocks 2–3. Read-only diagnostic — no code changes.

```
Read PLAN.md completely before doing anything. Every rule in that file applies to this task.

This is a diagnostic task only. You are not writing or changing any code. You are
investigating why the Polymarket VPS SSH connection returns exit code 255 and reporting
your findings clearly so the CEO can decide on the fix.

CONNECTION DETAILS (from config/projects.yaml):
  host:        167.234.219.208
  port:        22
  user:        aicg_ro
  ssh_key:     C:/Users/james/.ssh/ai_capital_vps

DIAGNOSTIC STEPS — run each one and report the full output:

1. Basic connectivity test:
   ssh -vvv -i "C:/Users/james/.ssh/ai_capital_vps" -o BatchMode=yes
       -o ConnectTimeout=10 aicg_ro@167.234.219.208 exit 2>&1
   Capture the first 30 lines. Identify which of these failure classes it falls into:
   - "Connection refused"  → wrong port or sshd not running
   - "Connection timed out" → firewall or security group blocking port 22
   - "Permission denied (publickey)" → key not trusted on remote
   - "Could not resolve hostname" → DNS failure
   - "Host key verification failed" → stale known_hosts entry
   - rc=255 with no clear message → report the raw output verbatim

2. Key file check (local):
   Check that C:/Users/james/.ssh/ai_capital_vps exists and report its permissions.
   The key file must be chmod 600 (owner read/write only). If permissions are wrong,
   report this as a finding — do not fix it automatically, flag it for CEO action.

3. Known hosts check:
   Check whether 167.234.219.208 appears in C:/Users/james/.ssh/known_hosts (or
   ~/.ssh/known_hosts). If the host key has changed since last connection, that would
   cause verification failure.

4. Report structure:
   After running the diagnostics, produce a clear report with:
   - FAILURE CLASS: (one of the six classes above, or "unknown")
   - ROOT CAUSE: one sentence
   - EVIDENCE: the relevant lines from the ssh -vvv output
   - RECOMMENDED FIX: the exact command or step needed to resolve it
   - ESTIMATED EFFORT: how long the fix will take

RULES:
- Read-only investigation only. Do not modify any SSH config, known_hosts, or key files.
- Do not attempt to "just fix it" — diagnose first, report findings, wait for CEO decision.
- Per PLAN.md R5: any VPS changes that affect live services require CEO approval first.
- shell=False for all subprocess calls per CLAUDE.md.

SUCCESS CRITERIA:
- A clear failure class is identified.
- The recommended fix is specific enough to execute without ambiguity.
- No files have been modified.
```

> **→ CODEX REVIEW GATE** — Block 4 is read-only diagnostics. Review the diagnostic report itself:
> check that no credentials or key contents are logged in plain text. Full gate in CLAUDE.md.

---

## BLOCK 5 — MT5 Signal Verification
> Can run in parallel with Blocks 2–3. Read-only verification — no code changes.

```
Read PLAN.md completely before doing anything. Every rule in that file applies to this task.

This is a read-only verification task. You are confirming that the MT5 Agentic Desk is
alive, that the 8 approved strategies are correctly registered, and that the scheduler is
generating signal evaluations. No code changes — observation only.

Per PLAN.md R2: MT5 bot source is read-only. Do not write, deploy, or change any parameters.

PROJECT LOCATION: mt5-agentic-desk/
(after Block 1 path correction; if Block 1 is not yet done, use the path from
config/projects.yaml trading_bots[id=mt5_desk].repo_path)

CHECK 1 — Scheduler is generating signal evaluations:
  Read: mt5-agentic-desk/logs/runtime/runtime_events.jsonl
  Look for entries from the last 7 trading days (Mon–Fri, 07:00–21:00 UTC).
  Report:
  - The timestamp of the most recent entry
  - How many signal evaluation events appear in the last 7 days
  - Whether any ERROR or EXCEPTION entries appear
  If the file is empty or missing, report that as a critical finding.

CHECK 2 — Strategy library state:
  Read: mt5-agentic-desk/library/strategies.json
  For each strategy entry, report:
  - strategy name / id
  - current status (candidate / pending_review / active / rejected)
  - date last updated (if present)
  Confirm that exactly 8 strategies are at active or approved status.
  If any active strategy shows an error state or unexpected status, flag it.

CHECK 3 — Runtime log tail:
  Read the last 50 lines of: mt5-agentic-desk/logs/runtime/runtime.log
  Report any warnings, errors, or anomalies found.

CHECK 4 — Scheduler config:
  Confirm the APScheduler config is set to:
  - Trading mode: every 15 minutes, Mon–Fri 07:00–21:00 UTC
  - Research mode: once daily at midnight
  Report the actual configured values, not the expected ones.

REPORT FORMAT:
  Produce a concise status report with four sections matching the four checks above.
  End with a one-line verdict: GREEN (all checks pass), AMBER (minor issues found),
  or RED (signal evaluation not running or strategies not at active status).

RULES:
- Read files only. Do not modify any MT5 source, config, or log files.
- Do not run any MT5 commands or scripts.
- Per PLAN.md R2: bot source is strictly read-only.

SUCCESS CRITERIA:
- All four checks have been run and reported.
- A clear GREEN / AMBER / RED verdict is given.
- No files have been modified.
```

> **→ CODEX REVIEW GATE** — Block 5 is read-only. No code review needed.
> Confirm only: no credentials or sensitive log content included in the output report.

---

## STAGE D — Close Checklist
> Run this prompt only after Blocks 1–5 are all complete.

```
Read PLAN.md completely before doing anything.

Your job is to verify that Stage D of the Integration Readiness Sprint is complete and
update PLAN.md to reflect this.

VERIFICATION CHECKS — confirm each one before updating PLAN.md:

1. config/projects.yaml — grep for "Manganda LTD". Should return zero results.
2. free-utility-tools/ — grep for "AFFILIATE_ID". Should return zero results.
3. free-utility-tools/ — grep for "ca-pub-XXXXXXXXXXXXXXXXX". Should return zero results.
4. free-utility-tools/ — confirm every .html file contains "umami-kappa-lake.vercel.app".
5. finance_web_page/index.html — grep for "no ads" (case-insensitive). Should return zero results.
6. Polymarket SSH — confirm the SSH diagnostic report was produced (Block 4 complete).
7. MT5 — confirm the strategy verification report was produced (Block 5 complete).

PLAN.md UPDATES — only if all checks above pass:

1. In §11 Stage Plan table, update Stage D:
   FROM: 🟡 IN PROGRESS — analysis complete, sprint executing (see §11.1)
   TO:   ✅ COMPLETE — 2026-[today's date]

2. In §11.1 Stage D definition of done, tick off completed items by replacing [ ] with [x]
   for each item that is genuinely complete. If the Polymarket SSH is not yet resolved
   (only diagnosed), leave that checkbox unticked and add a note with the failure class
   found in Block 4.

3. At the bottom of §11 infrastructure list, add:
   - Stage D (Integration Readiness Sprint): ✅ COMPLETE — [today's date]. All four
     projects.yaml paths corrected. Messaging conflicts resolved. FreeGhostTools Umami live.
     MT5 verified [GREEN/AMBER/RED]. Polymarket SSH: [RESOLVED/DIAGNOSED — see §11.1].

4. Update the document version line at the top:
   Version: 5.3
   Last updated: [today's date]
   Add to the version note: "v5.3 change: Stage D complete. Sprint close verified."

5. Update the footer line to match version 5.3.

RULES:
- Do not update PLAN.md until all verification checks have been run.
- If any check fails, stop and report which check failed and what was found.
- Do not change any section of PLAN.md other than the four items listed above.
- Per PLAN.md §14: this file is updated at the end of every completed stage.

SUCCESS CRITERIA:
- All 7 verification checks pass.
- PLAN.md version is 5.3 with today's date.
- Stage D shows ✅ COMPLETE in §11 table.
- No other section of PLAN.md has been altered.
```

---

*STAGE_D_PROMPTS.md — AI Holding Company — created 2026-04-15*
*Use one block at a time. Complete and verify before moving to the next.*
