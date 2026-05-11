# backtest-review

## Owner Agent

Quant Research Lead, reviewed by Risk Officer.

## Vertical

Trading.

## Autonomy

Guardrail.

## Purpose

Adversarially review every backtest before forward-test. The goal is to reject,
challenge, or require revision of weak evidence before it becomes operational
risk.

## Inputs

- MT5 backtest artifacts.
- Strategy qualification reports.
- Research hypothesis.
- Test window and data-quality evidence.
- Prior strategy decisions from `memory/` or `docs/decisions/`.

## Outputs

- Pass-for-owner-approval, revise, or block.
- Adversarial objections.
- Evidence gaps.
- Required next action.
- Review record in `reports/skills/backtest-review/`.

## Current Runtime

Run locally through the Telegram/tool router:

```powershell
python scripts/tool_router.py backtest_review
```

The runtime reads the latest local MT5 research artifact from
`mt5-agentic-desk/logs/research/`, the latest trading data-quality artifact
from `reports/skills/data-quality-daily/latest.json`, and writes timestamped
plus `latest.*` review records under `reports/skills/backtest-review/`.

## Success Metrics

- Less than 40% of backtests pass unchanged.
- False-positive rate is trackable.
- Review time saved versus human peer review.
- No forward-test without review artifact.

## Never

- Never approve live trading.
- Never treat a strong backtest as sufficient without data-quality evidence.
- Never ignore test-window or overfitting concerns.
