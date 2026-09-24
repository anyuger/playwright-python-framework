"""Writes the run report (markdown for people, JSON for tooling)."""
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

ICONS = {"trusted": "✅ trusted", "needs_review": "👀 needs review", "quarantined": "🚧 quarantined"}


def build_markdown(results: list, llm, run_id: str, site_name: str = "") -> str:
    title = f"# Spec-to-test agent run {run_id}" + (f" - site `{site_name}`" if site_name else "")
    lines = [title, ""]

    totals = Counter(v.verdict for r in results for v in r.verdicts)
    lines += [
        "## Summary",
        "",
        f"- Specs: {len(results)} "
        f"({sum(r.status == 'done' for r in results)} done, "
        f"{sum(r.status == 'rejected' for r in results)} rejected, "
        f"{sum(r.status == 'error' for r in results)} errors)",
        f"- Tests: {totals['trusted']} trusted, {totals['needs_review']} need review, "
        f"{totals['quarantined']} quarantined",
        f"- LLM cost: ${llm.total_cost:.4f} over {len(llm.calls)} calls "
        f"(budget ${llm.config.MAX_RUN_COST_USD:.2f})",
        "",
    ]

    for result in results:
        spec = result.spec
        lines += [f"## {spec.title}", "", f"Spec: `{spec.path}` - status: **{result.status}**"]
        if result.error:
            lines.append(f"\n> {result.error}")
        if result.output_path:
            lines.append(f"\nWritten to `{result.output_path}`")
        repairs = sum(a["kind"] == "repair" for a in result.attempts)
        lines += ["", f"Attempts: {len(result.attempts)} ({repairs} repairs)", ""]

        if result.verdicts:
            lines += ["| Test | Covers | Result | Verdict | Why |", "|---|---|---|---|---|"]
            for v in result.verdicts:
                why = "; ".join(v.reasons).replace("|", "/") or "-"
                lines.append(
                    f"| `{v.name}` | {', '.join(v.criteria)} | {v.outcome} | {ICONS[v.verdict]} | {why} |"
                )
            lines.append("")

        if result.uncovered_criteria:
            lines.append(f"**Not covered:** {', '.join(result.uncovered_criteria)}\n")
        for attempt in result.attempts:
            if attempt["blockers"]:
                lines.append(f"Attempt {attempt['attempt']} blockers:")
                lines += [f"- {b}" for b in attempt["blockers"]]
                lines.append("")
        if result.assumptions:
            lines.append("Model's assumptions and possible defects:")
            lines += [f"- {a}" for a in result.assumptions]
            lines.append("")

    lines += [
        "## LLM calls",
        "",
        "| Purpose | Model | Try | In | Out | Cache write | Cache read | Latency | Cost |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for c in llm.calls:
        lines.append(
            f"| {c.purpose} | {c.model} | {c.attempt} | {c.input_tokens} | {c.output_tokens} | "
            f"{c.cache_write_tokens} | {c.cache_read_tokens} | {c.latency_seconds}s | ${c.cost_usd:.4f} |"
        )
    return "\n".join(lines) + "\n"


def write_reports(results: list, llm, run_dir: Path, run_id: str, site_name: str = "") -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    markdown = build_markdown(results, llm, run_id, site_name)
    (run_dir / "report.md").write_text(markdown, encoding="utf-8")

    data = {
        "run_id": run_id,
        "site": site_name,
        "total_cost_usd": llm.total_cost,
        "calls": [c.to_dict() for c in llm.calls],
        "specs": [
            {
                "spec": r.spec.path,
                "status": r.status,
                "error": r.error,
                "output_path": r.output_path,
                "uncovered_criteria": r.uncovered_criteria,
                "model_coverage": r.model_coverage,
                "assumptions": r.assumptions,
                "attempts": r.attempts,
                "verdicts": [asdict(v) for v in r.verdicts],
            }
            for r in results
        ],
    }
    (run_dir / "report.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return run_dir / "report.md"
