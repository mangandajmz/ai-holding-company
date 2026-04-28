# AI Holding Company — Claude Code Rules

## Automation & Scheduling

**Do not use OpenClaw.** The Telegram bridge (`scripts/telegram_bridge.py`) is the
sole interface for automation, scheduling, and owner interaction. All agent
commands, morning briefs, and scheduled runs go through Telegram.
Use the bridge's `--send-morning-brief` flag or OS-level task scheduling
(Windows Task Scheduler / cron) to trigger recurring jobs.

## Development Philosophy

**No overengineering. Value-add additions only.**

Before adding anything, ask: does this directly improve what the owner sees,
what the agents know, or how reliably the system runs? If not, skip it.

Specifically:
- Do not add abstraction layers, base classes, or helpers for hypothetical
  future use cases. Three similar lines of code is better than a premature utility.
- Do not add configuration options for things that have one correct value.
- Do not add error handling for impossible scenarios.
- Do not refactor working code unless it is directly in the path of a bug or feature.
- New files only when genuinely justified — prefer editing existing ones.

## Architecture

- **Phase 1** — Monitoring: telemetry, log parsing, website checks (`monitoring.py`)
- **Phase 2** — Division crews: CrewAI trading + websites analysis (`phase2_crews.py`)
- **Phase 3** — CEO layer: company scorecard, board approvals (`phase3_holding.py`)
- **Bridge** — Telegram interface to all phases (`telegram_bridge.py`)
- **Memory** — Local vector store for company context (`local_vector_memory.py`)
- **Utils** — Shared helpers only; no new helpers without removing a duplicate (`utils.py`)

## Security

- `shell=False` always for subprocess calls. Use `shlex.split()` on config-sourced strings.
- No secrets in code or config files. Use environment variables.
- Observer mode ON by default — execute commands require explicit `/bot <id> execute confirm`.
- SSH connections use pinned known_hosts (`state/remote_known_hosts`), not `accept-new`.

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
