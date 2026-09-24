"""
Runs a generated test file with pytest in a subprocess and returns the
result of every test (read from pytest's JUnit XML), plus the output
the agent needs to repair failures.
"""
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

MAX_OUTPUT_CHARS = 6000  # keep repair prompts (and their cost) bounded


@dataclass
class RunResult:
    outcomes: dict = field(default_factory=dict)   # test name -> passed/failed/error/skipped
    messages: dict = field(default_factory=dict)   # test name -> failure message
    output: str = ""
    exit_code: int = 0

    @property
    def all_passed(self) -> bool:
        return bool(self.outcomes) and all(o == "passed" for o in self.outcomes.values())

    def failure_summary(self) -> str:
        failed = [name for name, outcome in self.outcomes.items() if outcome != "passed"]
        lines = [f"- {name}: {self.outcomes[name]} - {self.messages.get(name, '')}" for name in failed]
        if not self.outcomes:
            lines.append("- No test results: the file failed during import or collection")
        return "Failing tests:\n" + "\n".join(lines) + f"\n\npytest output (tail):\n{self.output}"


def run_tests(test_file: str, timeout_seconds: int = 600) -> RunResult:
    test_path = Path(test_file)
    report_path = test_path.with_suffix(".junit.xml")
    command = [
        sys.executable, "-m", "pytest", str(test_path),
        "--override-ini=addopts=",   # no --headed / allure from pytest.ini
        "-p", "no:cacheprovider",
        f"--junitxml={report_path}",
        "-q", "--tb=short",
    ]
    # UTF-8 both ways, so a non-ASCII character in pytest output can't crash the agent on Windows
    env = {**os.environ, "HEADLESS": "true", "PYTHONIOENCODING": "utf-8"}

    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout_seconds, env=env
        )
        output, exit_code = completed.stdout + completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as error:
        output, exit_code = f"Timed out after {timeout_seconds}s\n{error.stdout or ''}", -1

    result = RunResult(output=output[-MAX_OUTPUT_CHARS:], exit_code=exit_code)
    if report_path.exists():
        _read_junit(report_path, result)
    return result


def _read_junit(report_path: Path, result: RunResult):
    root = ET.parse(report_path).getroot()
    for case in root.iter("testcase"):
        name = case.get("name", "").split("[")[0]
        outcome, message = "passed", ""
        for tag in ("failure", "error", "skipped"):
            element = case.find(tag)
            if element is not None:
                outcome = "failed" if tag == "failure" else tag
                message = (element.get("message") or "").strip()[:500]
                break
        result.outcomes[name] = outcome
        result.messages[name] = message
