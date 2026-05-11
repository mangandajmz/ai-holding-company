# broker-reconcile

## Owner Agent

Quant Ops.

## Vertical

Trading.

## Autonomy

Guardrail.

## Purpose

Run daily three-way reconciliation between internal blotter, broker, and
clearing/export source once those sources exist.

## Current Status

Spec only. The repo does not yet have a canonical internal blotter, broker
export, or clearing source.

## Inputs

- Internal blotter.
- Broker export.
- Clearing/export source where relevant.
- Strategy/order identifiers.

## Outputs

- Breaks/day.
- Break details.
- MTTR.
- Block state for trading actions when breaks are unresolved.

## Success Metrics

- Breaks/day.
- Mean time to resolution.
- No trading promotion when reconciliation breaks are unresolved.

## Never

- Never hide breaks.
- Never auto-resolve mismatches.
- Never treat missing exports as a clean reconciliation.
