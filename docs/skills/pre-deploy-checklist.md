# pre-deploy-checklist

## Owner Agent

Risk Officer.

## Vertical

Trading.

## Autonomy

Guardrail.

## Purpose

Block unsafe strategy go-live or forward-test promotion. This is a trading
strategy deployment guardrail, not a generic software deploy checklist.

## Inputs

- Backtest review.
- Data-quality daily result.
- Strategy qualification report.
- Paper/watchlist evidence.
- Broker/recon status when available.
- Prior owner decisions.

## Outputs

- BLOCK or PASS-FOR-HUMAN-APPROVAL.
- Missing evidence.
- Risk explanation.
- Required next condition.

## Success Metrics

- No strategy promotion without required evidence.
- Blocks are specific and resolvable.
- Risk cannot approve, only block or pass to owner.

## Never

- Never auto-approve.
- Never approve live trading.
- Never treat missing evidence as low risk.
