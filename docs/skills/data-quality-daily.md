# data-quality-daily

## Owner Agent

Quant Ops.

## Vertical

Trading.

## Autonomy

Guardrail.

## Purpose

Check data integrity before trading research, forward-test, or live-readiness
decisions rely on the data.

## Inputs

- MT5 feed freshness and report artifacts.
- Missing bar/gap evidence when available.
- Strategy library freshness.
- Polymarket sync/report freshness where relevant.
- `config/targets.yaml`.

## Outputs

- GREEN, AMBER, RED, or BLOCKED readiness result.
- Data issues and affected symbols/sources.
- Explicit N/A entries for sources that do not exist yet.
- Report in `reports/skills/data-quality-daily/`.

## Success Metrics

- Issues caught before they hit live strategies or research promotion.
- False-positive rate under 10% once enough history exists.
- Every forward-test decision has current data-quality evidence.

## Never

- Never approve strategy deployment.
- Never silently skip missing feeds.
- Never pretend vendor cross-checks or corporate actions exist before they do.
