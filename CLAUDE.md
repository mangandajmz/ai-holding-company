# AI Holding Company — Claude Code Rules

## Automation & Scheduling

**Do not use OpenClaw.** The Telegram bridge (`scripts/aiogram_bridge.py`) is the
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
- **Bridge** — Telegram interface to all phases (`aiogram_bridge.py`)
- **Memory** — Local vector store for company context (`local_vector_memory.py`)
- **Utils** — Shared helpers only; no new helpers without removing a duplicate (`utils.py`)

## Security

- `shell=False` always for subprocess calls. Use `shlex.split()` on config-sourced strings.
- No secrets in code or config files. Use environment variables.
- Observer mode ON by default — execute commands require explicit `/bot <id> execute confirm`.
- SSH connections use pinned known_hosts (`state/remote_known_hosts`), not `accept-new`.

## Code Review Gate

**Every block of work must pass a Codex review before the next block starts.**
This is non-negotiable. It was established in Stage D (commit e533073) and applies
to every stage, every file, every tool used to build this system.

Submit all files created or modified in the block. Codex must check all three categories
and return clean before work continues:

**Style / Linting**
- Python: PEP 8, consistent naming, no unused imports
- YAML: 2-space indentation, no duplicate keys
- JSON: valid syntax, consistent formatting

**Logic**
- Edge cases: None, empty, zero, and malformed inputs handled without raising
- Graceful degradation: safe defaults returned when data is missing
- Data flow: output structure matches what the consuming function expects
- No off-by-one risks in loops, slices, or index operations

**Security**
- `shell=False` on every subprocess call — no exceptions
- `shlex.split()` on every config-sourced command string
- No hardcoded secrets, tokens, API keys, or credentials anywhere
- No cloud API calls — no openai, anthropic, or external AI endpoints (R1)
- No file writes outside `ai-holding-company/` (R8)
- No new network connections without explicit CEO approval

Resolve ALL flagged issues. Re-run tests after fixes. Only move forward once clean.
