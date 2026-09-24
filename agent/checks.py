"""
Static checks on generated test code, done with Python's ast module
before anything runs. This is the first half of "can we trust it?"
(the second half is actually running the tests).

Two severities:
- BLOCKER: the file must not be used as-is. The agent gets these back
  and repairs the file (syntax errors, invented page object methods, sleeps...).
- REVIEW:  the code may work, but a human should look before it gates CI
  (raw locators outside page objects, ...).
"""
import ast
import re
import textwrap
from dataclasses import dataclass, field

BLOCKER = "blocker"
REVIEW = "review"

# Without a site: test tools only. A site adds its own config and pages (see Site.allowed_imports).
ALLOWED_IMPORTS = ("pytest", "re", "playwright.sync_api")
CRITERION_ID = re.compile(r"\bAC-\d+\b")
# page.locator(...), overview_page.get_by_role(...), page.locator(...).locator(...) - any receiver
RAW_LOCATOR_CALL = re.compile(r"(^|\.)(locator|get_by_\w+)$")


@dataclass
class Finding:
    severity: str
    message: str
    test: str = ""   # empty for file-level findings

    def __str__(self):
        where = f"{self.test}: " if self.test else ""
        return f"[{self.severity}] {where}{self.message}"


@dataclass
class TestInfo:
    name: str
    source: str
    criteria: set = field(default_factory=set)
    findings: list = field(default_factory=list)


@dataclass
class Analysis:
    tests: dict = field(default_factory=dict)          # name -> TestInfo
    file_findings: list = field(default_factory=list)
    uncovered_criteria: list = field(default_factory=list)

    @property
    def all_findings(self) -> list:
        found = list(self.file_findings)
        for info in self.tests.values():
            found.extend(info.findings)
        return found

    @property
    def blockers(self) -> list:
        return [f for f in self.all_findings if f.severity == BLOCKER]


def analyze(code: str, criteria: dict, api: dict, allowed_imports: tuple = ALLOWED_IMPORTS) -> Analysis:
    """
    code:            the generated test file
    criteria:        the spec's acceptance criteria {"AC-1": "..."}
    api:             page object API from context.page_object_api()
    allowed_imports: modules a test may import (Site.allowed_imports) - importing
                     another site's pages is a blocker
    """
    analysis = Analysis()
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        analysis.file_findings.append(Finding(BLOCKER, f"Syntax error line {error.lineno}: {error.msg}"))
        analysis.uncovered_criteria = sorted(criteria)
        return analysis

    analysis.file_findings.extend(_check_imports(tree, allowed_imports))
    lines = code.splitlines()

    for func in find_test_functions(tree):
        source = ast.get_source_segment(code, func) or ""
        # Full lines, so a trailing "# NEW-LOCATOR" comment on the last line is included
        raw_lines = "\n".join(lines[func.lineno - 1:func.end_lineno])
        info = TestInfo(name=func.name, source=source)
        info.criteria = set(CRITERION_ID.findall(ast.get_docstring(func) or ""))
        info.findings = _check_test(func, raw_lines, info.criteria, criteria, api)
        analysis.tests[func.name] = info

    # Fixtures and helpers can call page objects too, and can hide raw locators
    test_nodes = set(id(f) for f in find_test_functions(tree))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and id(node) not in test_nodes:
            analysis.file_findings.extend(_check_page_object_usage(node, api))
            raw = sorted({f"{_call_name(c)}()" for c in ast.walk(node)
                          if isinstance(c, ast.Call) and RAW_LOCATOR_CALL.search(_call_name(c))})
            if raw:
                # We don't trace which test uses which fixture, so every test is flagged (the safe side)
                for info in analysis.tests.values():
                    info.findings.append(Finding(
                        REVIEW, f"Raw locator {', '.join(raw)} in fixture/helper '{node.name}'", info.name))

    if not analysis.tests:
        analysis.file_findings.append(Finding(BLOCKER, "No test functions found"))

    covered = set().union(*(t.criteria for t in analysis.tests.values())) if analysis.tests else set()
    analysis.uncovered_criteria = sorted(set(criteria) - covered)
    for cid in analysis.uncovered_criteria:
        analysis.file_findings.append(Finding(BLOCKER, f"{cid} is not covered by any test docstring"))
    return analysis


def find_test_functions(tree: ast.Module) -> list:
    """test_* functions at module level or inside Test* classes."""
    found = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            found.append(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            found.extend(
                item for item in node.body
                if isinstance(item, ast.FunctionDef) and item.name.startswith("test_")
            )
    return found


def assertion_values(test_source: str) -> set:
    """
    The literal values a test asserts on, e.g. {"Error: Last Name is required", 1}.
    Used to detect a repair that quietly changed an expected value.
    """
    try:
        tree = ast.parse(_dedent(test_source))
    except SyntaxError:
        return set()
    values = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            scope = [node]
        elif _is_expect_chain(node):
            scope = node.args + [k.value for k in node.keywords]  # the matcher's expected value only
        else:
            continue
        for part in scope:
            for sub in ast.walk(part):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, (str, int, float)):
                    values.add(sub.value)
    return values


# ---------------------------------------------------------------- helpers

def _check_imports(tree: ast.Module, allowed_imports: tuple) -> list:
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        else:
            continue
        for module in modules:
            if not any(module == ok or module.startswith(ok + ".") for ok in allowed_imports):
                findings.append(Finding(BLOCKER, f"Import not allowed: {module}"))
    return findings


def _check_test(func, raw_source, test_criteria, spec_criteria, api) -> list:
    name = func.name
    findings = []

    if not test_criteria:
        findings.append(Finding(BLOCKER, "Docstring does not reference an acceptance criterion (AC-n)", name))
    for cid in sorted(test_criteria - set(spec_criteria)):
        findings.append(Finding(BLOCKER, f"References {cid}, which is not in the spec", name))

    has_assertion = any(
        isinstance(node, ast.Assert) or _is_expect_chain(node) for node in ast.walk(func)
    )
    if not has_assertion:
        findings.append(Finding(BLOCKER, "No assert or expect() - the test cannot fail", name))

    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            called = _call_name(node)
            if called in ("time.sleep", "sleep") or called.endswith(".wait_for_timeout"):
                findings.append(Finding(BLOCKER, f"Hard wait {called}() - use auto-waiting or expect()", name))
            if RAW_LOCATOR_CALL.search(called):
                findings.append(Finding(REVIEW, f"Raw locator {called}() outside a page object", name))
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("http"):
            findings.append(Finding(BLOCKER, f"Hard-coded URL '{node.value}' - use Config", name))

    findings.extend(_check_page_object_usage(func, api))

    if "NEW-LOCATOR" in raw_source and not any("Raw locator" in f.message for f in findings):
        findings.append(Finding(REVIEW, "Marked NEW-LOCATOR - a page object needs updating", name))

    unique = []
    for finding in findings:  # the same problem can appear on several lines
        if (finding.severity, finding.message) not in [(u.severity, u.message) for u in unique]:
            unique.append(finding)
    return unique


def _check_page_object_usage(func, api) -> list:
    """Catch calls to page object methods/attributes that do not exist."""
    variables = {}  # variable name -> page object class
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            cls = _call_name(node.value)
            if cls in api:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        variables[target.id] = cls

    findings = []
    reported = set()
    for node in ast.walk(func):
        if not isinstance(node, ast.Attribute):
            continue
        owner = None
        if isinstance(node.value, ast.Name) and node.value.id in variables:
            owner = variables[node.value.id]
        elif isinstance(node.value, ast.Call) and _call_name(node.value) in api:
            owner = _call_name(node.value)  # e.g. LoginPage(page).navigate()
        if owner and node.attr not in api[owner] and (owner, node.attr) not in reported:
            reported.add((owner, node.attr))
            findings.append(Finding(
                BLOCKER,
                f"{owner} has no '{node.attr}'. Available: {', '.join(sorted(api[owner]))}",
                func.name,
            ))
    return findings


def _call_name(call: ast.Call) -> str:
    """'page.locator' for page.locator(...), 'LoginPage' for LoginPage(...)."""
    parts = []
    node = call.func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif isinstance(node, ast.Call):
        parts.append(_call_name(node) + "()")
    return ".".join(reversed(parts))


def _is_expect_chain(node) -> bool:
    """True for expect(x).to_have_text(...) style assertions."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr.startswith(("to_", "not_to_"))
        and "expect" in _call_name(node)
    )


def _dedent(source: str) -> str:
    return textwrap.dedent(source)
