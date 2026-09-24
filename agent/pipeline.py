"""
The agent loop for one spec:

    generate -> static checks -> run -> (repair -> checks -> run)* -> verdicts -> write

Every test ends up with one verdict:

    TRUSTED       passed every run, never touched by self-healing, uses page objects only.
                  Runs in CI as-is.
    NEEDS_REVIEW  passes, but a human should look first (raw locators, changed or added
                  by a repair, failed before passing, flaky). Written with a skip marker.
    QUARANTINED   still failing after all repairs. Could be a wrong test or a real
                  product defect - triage. Written with a skip marker.

If static blockers survive every repair, the whole file is REJECTED and only
kept in the run folder.
"""
import ast
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from agent import checks
from agent.generator import GenerationError
from agent.llm_client import BudgetExceededError, LLMUnavailableError
from agent.runner import run_tests
from agent.spec import Spec
from agent.config import AgentConfig
from agent.site import Site

logger = logging.getLogger(__name__)

TRUSTED = "trusted"
NEEDS_REVIEW = "needs_review"
QUARANTINED = "quarantined"


@dataclass
class TestVerdict:
    name: str
    criteria: list
    outcome: str
    verdict: str
    reasons: list = field(default_factory=list)


@dataclass
class SpecResult:
    spec: Spec
    status: str = "done"             # done | rejected | error
    verdicts: list = field(default_factory=list)
    attempts: list = field(default_factory=list)
    uncovered_criteria: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)
    model_coverage: dict = field(default_factory=dict)
    output_path: str = ""
    error: str = ""
    note: str = ""                   # e.g. an existing reviewed file was kept


class SpecPipeline:

    def __init__(self, generator, site: Site, api: dict, run_dir: Path, runner=run_tests,
                 config=AgentConfig):
        self.generator = generator
        self.site = site
        self.api = api
        self.run_dir = Path(run_dir)
        self.runner = runner          # swapped for a fake in unit tests
        self.config = config

    def process(self, spec: Spec) -> SpecResult:
        result = SpecResult(spec=spec)
        work_dir = self.run_dir / spec.name
        work_dir.mkdir(parents=True, exist_ok=True)

        first_sources = None       # test name -> source, from the first parsable version
        ever_failed = set()
        current = analysis = run = None

        try:
            for attempt in range(self.config.MAX_REPAIR_ATTEMPTS + 1):
                # 1. Generate or repair
                if attempt == 0:
                    current = self.generator.generate(spec)
                else:
                    problems = self._problems_for_repair(analysis, run)
                    current = self.generator.repair(spec, current, problems)
                candidate = work_dir / f"attempt_{attempt}" / f"test_gen_{spec.name}.py"
                candidate.parent.mkdir(parents=True, exist_ok=True)
                candidate.write_text(current.code, encoding="utf-8")

                # 2. Static checks
                analysis = checks.analyze(current.code, spec.criteria, self.api, self.site.allowed_imports)
                if first_sources is None and analysis.tests:
                    first_sources = {n: t.source for n, t in analysis.tests.items()}
                record = {
                    "attempt": attempt,
                    "kind": "generate" if attempt == 0 else "repair",
                    "blockers": [str(f) for f in analysis.blockers],
                    "outcomes": {},
                }
                result.attempts.append(record)

                if analysis.blockers:
                    logger.info(f"{spec.name} attempt {attempt}: {len(analysis.blockers)} blockers")
                    run = None
                    continue  # don't spend time running a file we already know is wrong

                # 3. Run it
                run = self.runner(str(candidate))
                record["outcomes"] = dict(run.outcomes)
                ever_failed.update(n for n, o in run.outcomes.items() if o != "passed")
                logger.info(f"{spec.name} attempt {attempt}: {run.outcomes}")
                if run.all_passed:
                    break
                if is_environment_failure(run):
                    # The site or network is down - a repair can't fix that, so don't pay for one
                    result.status = "error"
                    result.error = "Environment problem (site unreachable), not a test problem - stopped without repairs"
                    logger.error(f"{spec.name}: {result.error}")
                    break

        except (GenerationError, LLMUnavailableError, BudgetExceededError) as error:
            result.status, result.error = "error", str(error)
            logger.error(f"{spec.name}: {error}")
            return result

        result.assumptions = current.assumptions
        result.model_coverage = current.coverage
        result.uncovered_criteria = analysis.uncovered_criteria

        # On any error nothing is written to the site's tests/generated; candidates stay in the run folder
        if result.status == "error":
            return result
        if analysis.blockers or run is None:
            result.status = "rejected"
            result.error = "Blockers remain after all repair attempts"
            return result

        # 4. A second run of the passing file to catch flaky tests (no LLM cost)
        flaky = set()
        if run.all_passed:
            stability = self.runner(str(candidate))
            flaky = {n for n, o in stability.outcomes.items() if o != "passed"}

        # 5. Verdict per test, then write the file
        result.verdicts = self._verdicts(analysis, run, first_sources or {}, ever_failed, flaky)
        result.output_path = self._write_output(spec, current, result)
        return result

    # ------------------------------------------------------------------

    def _problems_for_repair(self, analysis, run) -> str:
        if analysis is not None and analysis.blockers:
            return "Static check blockers:\n" + "\n".join(f"- {f}" for f in analysis.blockers)
        return run.failure_summary()

    def _verdicts(self, analysis, run, first_sources, ever_failed, flaky) -> list:
        verdicts = []
        for name, info in analysis.tests.items():
            outcome = run.outcomes.get(name, "not run")
            reasons = []

            if outcome != "passed":
                reasons.append(
                    f"Still failing after repairs ({outcome}: {one_line(run.messages.get(name, ''))}). "
                    f"Wrong test or real defect - triage"
                )
                verdict = QUARANTINED
            else:
                reasons += [f.message for f in info.findings if f.severity == checks.REVIEW]
                if name not in first_sources:
                    reasons.append("Added by self-healing")
                elif info.source != first_sources[name]:
                    reasons.append("Changed by self-healing")
                    before = checks.assertion_values(first_sources[name])
                    after = checks.assertion_values(info.source)
                    if before != after:
                        reasons.append(
                            f"Expected values changed in repair: removed {sorted(map(str, before - after))}, "
                            f"added {sorted(map(str, after - before))}"
                        )
                if name in ever_failed:
                    reasons.append("Failed at least once before passing")
                if name in flaky:
                    reasons.append("Flaky: failed on the stability re-run")
                verdict = NEEDS_REVIEW if reasons else TRUSTED

            verdicts.append(TestVerdict(name, sorted(info.criteria), outcome, verdict, reasons))
        return verdicts

    def _write_output(self, spec: Spec, generated, result: SpecResult) -> str:
        """Save to the site's tests/generated with skip markers on anything not trusted."""
        code = add_skip_markers(generated.code, {
            v.name: f"agent: {v.verdict.replace('_', ' ')} - {'; '.join(v.reasons)}"
            for v in result.verdicts if v.verdict != TRUSTED
        })
        header = (
            f"# Generated by the spec-to-test agent from {spec.path} on {date.today()}\n"
            f"# Model: {generated.model or 'unknown'}\n"
            f"# Tests marked skip need a human: review, then delete the marker to promote.\n"
        )
        out_dir = Path(self.site.generated_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"test_gen_{spec.name}.py"

        if path.exists() and not self.config.OVERWRITE_GENERATED:
            # Don't undo a human's review: keep their file, park the new one for comparison
            parked = self.run_dir / spec.name / path.name
            parked.write_text(header + code, encoding="utf-8")
            result.note = (
                f"`{path.as_posix()}` already exists (it may have been reviewed and edited) and was kept. "
                f"The new version is in `{parked.as_posix()}`. Use --overwrite to replace it."
            )
            return ""

        path.write_text(header + code, encoding="utf-8")
        return path.as_posix()  # same in reports on Windows and Linux


def is_environment_failure(run) -> bool:
    """Every test failed with a network error: the app is unreachable."""
    return bool(run.outcomes) and all(
        outcome != "passed" and "net::ERR_" in run.messages.get(name, "")
        for name, outcome in run.outcomes.items()
    )


def one_line(text: str, limit: int = 160) -> str:
    """First line of an error message, shortened for tables and skip reasons."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    return first if len(first) <= limit else first[: limit - 3] + "..."


def add_skip_markers(code: str, reasons: dict) -> str:
    """Insert @pytest.mark.skip(reason=...) above each named test function."""
    if not reasons:
        return code
    tree = ast.parse(code)
    lines = code.splitlines()
    targets = []
    for func in checks.find_test_functions(tree):
        if func.name in reasons:
            first_line = min([func.lineno] + [d.lineno for d in func.decorator_list])
            def_line = lines[func.lineno - 1]
            indent = def_line[: len(def_line) - len(def_line.lstrip())]
            reason = reasons[func.name][:300]
            targets.append((first_line, f"{indent}@pytest.mark.skip(reason={reason!r})"))

    for line_number, marker in sorted(targets, reverse=True):  # bottom-up keeps numbers valid
        lines.insert(line_number - 1, marker)

    code = "\n".join(lines) + "\n"
    if not any(line.strip() == "import pytest" for line in lines):
        code = "import pytest\n" + code
    return code
