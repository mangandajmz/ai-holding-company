"""Natural, truth-grounded Chief of Staff answers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from org_truth_retriever import ROOT, TruthBundle, collect_truth_bundle


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    word = singular if count == 1 else (plural or f"{singular}s")
    number = "one" if count == 1 else str(count)
    return f"{number} {word}"


def _approval_phrase(bundle: TruthBundle) -> str:
    if not bundle.pending_approvals:
        return "I do not see a pending owner approval in the current approval snapshot."
    first = bundle.pending_approvals[0]
    topic = str(first.get("topic") or first.get("approval_id") or "approval").strip()
    return f"You have {_plural(len(bundle.pending_approvals), 'approval')} waiting, led by {topic}."


def _first_approval_topic(bundle: TruthBundle) -> str:
    if not bundle.pending_approvals:
        return ""
    first = bundle.pending_approvals[0]
    return str(first.get("topic") or first.get("approval_id") or "approval").strip()


def _status_reason(bundle: TruthBundle) -> str:
    if bundle.company_risks:
        return bundle.company_risks[0]
    if bundle.company_actions:
        return bundle.company_actions[0]
    return "The latest scorecard does not include a specific risk note."


def _answer_owner_needs(bundle: TruthBundle) -> tuple[str, str]:
    if bundle.truth_state == "unknown":
        return (
            "I do not have current company evidence yet. Refresh the company reports before I tell you what needs the owner.",
            "refresh",
        )

    parts: list[str] = []
    if bundle.pending_approvals:
        topic = _first_approval_topic(bundle)
        parts.append(f"You have one real decision today: {topic}.")
        parts.append(f"That is {_plural(len(bundle.pending_approvals), 'approval')} waiting in the current snapshot.")
    else:
        parts.append(
            f"You're clear on approvals right now. The company is {bundle.company_status} in the latest stored CEO report."
        )

    parts.append(_status_reason(bundle))
    if bundle.approved_awaiting_execution:
        parts.append(
            f"There are also {_plural(len(bundle.approved_awaiting_execution), 'approved item')} waiting for execution follow-through, which is likely the operating drag to clean up next."
        )
    owner_need = "approve" if bundle.pending_approvals else "none"
    return " ".join(parts), owner_need


def _format_issue(issue: dict[str, Any]) -> str:
    metric = str(issue.get("metric") or "Trading issue").strip()
    actual = str(issue.get("actual") or "").strip()
    target = str(issue.get("target") or "").strip()
    details = ""
    if actual or target:
        details = f" ({actual} vs {target})".replace(" vs )", ")")
    action = str(issue.get("action") or "").strip()
    if action:
        return f"{metric}{details}; next step is {action}"
    return f"{metric}{details}"


def _answer_trading(bundle: TruthBundle) -> tuple[str, str]:
    if bundle.data_quality_status not in {"", "UNKNOWN"}:
        if bundle.data_quality_status != "GREEN" or bundle.trading_status == "UNKNOWN":
            detail = bundle.data_quality_brief or "The latest data-quality skill output is available."
            return (f"Trading data-quality readiness is {bundle.data_quality_status}. {detail}", "none")
    if bundle.trading_status == "UNKNOWN":
        return (
            "I do not have current trading evidence in the stored division reports. Treat trading status as unknown until the trading readiness reports are refreshed.",
            "refresh",
        )
    if not bundle.trading_issues:
        return (f"Trading is {bundle.trading_status}. I do not see an open AMBER or RED trading issue in the current scorecard.", "none")
    issue_text = _format_issue(bundle.trading_issues[0])
    return (f"Trading is {bundle.trading_status} because of {issue_text}.", "none")


def _answer_strategy_review(bundle: TruthBundle) -> tuple[str, str]:
    if bundle.backtest_review_status not in {"", "UNKNOWN"}:
        answer = bundle.backtest_review_brief or f"Backtest review is {bundle.backtest_review_status}."
        if bundle.backtest_review_next_action:
            answer = f"{answer} {bundle.backtest_review_next_action}"
        owner_need = "approve" if bundle.backtest_review_status == "PASS_FOR_OWNER_APPROVAL" else "none"
        return answer, owner_need
    return _answer_trading(bundle)


def _answer_support(bundle: TruthBundle) -> tuple[str, str]:
    if bundle.support_triage_status not in {"", "UNKNOWN"}:
        detail = bundle.support_triage_brief or "The latest support triage artifact is available."
        owner_need = "approve" if bundle.support_triage_status == "AMBER" else "none"
        if detail.lower().startswith("support triage is "):
            return detail, owner_need
        return f"Support triage is {bundle.support_triage_status}. {detail}", owner_need
    return (
        "I do not have a support triage artifact yet. Support is only knowable after a local ticket source is wired or scanned.",
        "refresh",
    )


def _answer_blockers(bundle: TruthBundle) -> tuple[str, str]:
    blockers: list[str] = []
    for approval in bundle.pending_approvals:
        topic = str(approval.get("topic") or approval.get("approval_id") or "approval").strip()
        blockers.append(f"owner approval for {topic}")
    for issue in bundle.trading_issues[:2]:
        blockers.append(_format_issue(issue))
    if not blockers:
        if bundle.truth_state == "unknown":
            return ("I do not have current evidence to identify blockers yet.", "refresh")
        return ("I do not see a stored blocker in the current reports and approval state.", "none")
    return "The main blocker is " + "; ".join(blockers) + ".", "approve" if bundle.pending_approvals else "none"


def answer_company_question(question: str, root: Path | str = ROOT) -> dict[str, Any]:
    """Answer a company question from durable local truth only."""

    bundle = collect_truth_bundle(root)
    normalized = question.lower().strip()

    if any(term in normalized for term in ("backtest", "forward-test", "forward test", "strategy")):
        answer, owner_need = _answer_strategy_review(bundle)
    elif any(term in normalized for term in ("support", "ticket", "customer")):
        answer, owner_need = _answer_support(bundle)
    elif "trading" in normalized:
        answer, owner_need = _answer_trading(bundle)
    elif any(term in normalized for term in ("blocked", "blocker", "stuck")):
        answer, owner_need = _answer_blockers(bundle)
    else:
        answer, owner_need = _answer_owner_needs(bundle)

    if any(term in normalized for term in ("show evidence", "sources", "source", "evidence")):
        sources = bundle.source_paths()
        if sources:
            answer = f"{answer} Evidence: " + ", ".join(sources) + "."
        else:
            answer = f"{answer} I do not have source files to cite yet."

    return {
        "ok": True,
        "question": question,
        "answer": answer,
        "owner_need": owner_need,
        "truth_state": bundle.truth_state,
        "sources": bundle.source_paths(),
    }


def render_company_answer(response: dict[str, Any]) -> str:
    """Render the Chief of Staff answer for humans."""

    answer = str(response.get("answer") or "").strip()
    if not answer:
        return "I do not have enough stored company evidence to answer that yet."
    return answer


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ask the truth-grounded Chief of Staff.")
    parser.add_argument("--question", required=True, help="Natural owner question.")
    parser.add_argument("--root", default=str(ROOT), help="Project root for truth retrieval.")
    parser.add_argument("--json", action="store_true", help="Print structured JSON instead of conversational text.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    response = answer_company_question(args.question, root=Path(args.root))
    if args.json:
        print(json.dumps(response, indent=2))
    else:
        print(render_company_answer(response))


if __name__ == "__main__":
    main()
