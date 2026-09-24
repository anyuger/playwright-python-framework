"""
Turns a spec into a pytest file, and repairs that file when checks or the
test run fail.

The model must answer through a tool (submit_test_file), which gives us
structured output: the code, which criteria each test covers, and any
assumptions it made. We still verify coverage ourselves - the model's
claim goes in the report, the docstrings decide.
"""
from dataclasses import dataclass, field

from agent.spec import Spec

SUBMIT_TOOL = {
    "name": "submit_test_file",
    "description": "Submit the complete pytest file for the spec.",
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The complete Python test file, ready to save and run.",
            },
            "coverage": {
                "type": "array",
                "description": "Which tests cover which acceptance criteria.",
                "items": {
                    "type": "object",
                    "properties": {
                        "criterion_id": {"type": "string"},
                        "test_names": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["criterion_id", "test_names"],
                },
            },
            "assumptions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Anything you had to assume or could not verify from the spec and code.",
            },
        },
        "required": ["code", "coverage", "assumptions"],
    },
}

RULES = """You are a senior test automation engineer writing pytest + Playwright (sync API)
tests for an existing Page Object Model framework.

Rules:
1. Follow the style of the reference test file: a Test* class, an autouse login
   fixture when the flow needs a logged-in user, the `page` fixture from conftest.py.
2. Use existing page object methods and locator attributes. Never invent a method
   or attribute that is not in the page object source you were given.
3. If the spec needs an element no page object exposes, you may use
   page.locator("[data-test='...']") directly in the test, and you must put the
   comment `# NEW-LOCATOR: <why>` on that line. A human will move it into a page object.
4. URLs, users and passwords come from the site's `Config`. No hard-coded base URLs or credentials.
5. No time.sleep() and no page.wait_for_timeout(). Rely on Playwright auto-waiting
   or `expect` from playwright.sync_api.
6. Every test starts its docstring with the criterion IDs it covers, e.g. "AC-2: ...".
   Every criterion must be covered by at least one test.
7. Every test must assert something observable. Expected values come from the spec,
   word for word. Do not guess expected values the spec does not give.
8. Allowed imports: {allowed_imports}. Nothing else - not another site's pages.
Submit the file with the submit_test_file tool."""

REPAIR_INSTRUCTIONS = """Your previous test file has problems. Fix them and submit the complete file again.

Healing rules:
- You may fix locators, waits, imports, syntax, test structure and the use of page objects.
- You must NOT change an expected value that comes from the spec just to make a test pass.
  If the app behaves differently from the spec, keep the assertion as the spec says,
  and describe the mismatch in `assumptions` - that is a possible product defect.
- Keep the test names unless a test has to be split or removed."""


@dataclass
class GeneratedFile:
    code: str
    coverage: dict = field(default_factory=dict)       # {"AC-1": ["test_x"]}
    assumptions: list = field(default_factory=list)
    model: str = ""


class GenerationError(Exception):
    """The model did not return a usable file."""


class SpecToTestGenerator:

    def __init__(self, llm, framework_context: str, allowed_imports: tuple):
        self.llm = llm
        rules = RULES.format(allowed_imports=", ".join(
            f"{m}.*" if m.endswith(".pages") else m for m in allowed_imports
        ))
        # The rules and framework context are identical for every spec in the run, so they
        # are marked for prompt caching: later calls read them at ~10% of the input price.
        self.system = [
            {"type": "text", "text": rules},
            {"type": "text", "text": framework_context, "cache_control": {"type": "ephemeral"}},
        ]

    def generate(self, spec: Spec) -> GeneratedFile:
        prompt = f"Write the test file for this spec.\n\n<spec path=\"{spec.path}\">\n{spec.text}\n</spec>"
        return self._ask(f"generate:{spec.name}", prompt)

    def repair(self, spec: Spec, previous: GeneratedFile, problems: str) -> GeneratedFile:
        prompt = (
            f"{REPAIR_INSTRUCTIONS}\n\n"
            f"<spec path=\"{spec.path}\">\n{spec.text}\n</spec>\n\n"
            f"<previous_code>\n{previous.code}\n</previous_code>\n\n"
            f"<problems>\n{problems}\n</problems>"
        )
        return self._ask(f"repair:{spec.name}", prompt)

    def _ask(self, purpose: str, prompt: str) -> GeneratedFile:
        response = self.llm.create_message(
            purpose=purpose,
            system=self.system,
            messages=[{"role": "user", "content": prompt}],
            tools=[SUBMIT_TOOL],
            tool_choice={"type": "tool", "name": "submit_test_file"},
        )

        if response.stop_reason == "max_tokens":
            raise GenerationError(f"{purpose}: output was cut off at max_tokens")

        tool_calls = [block for block in response.content if block.type == "tool_use"]
        if not tool_calls or not tool_calls[0].input.get("code"):
            raise GenerationError(f"{purpose}: model did not submit a test file")

        data = tool_calls[0].input
        coverage = {
            item["criterion_id"]: list(item.get("test_names", []))
            for item in data.get("coverage", [])
            if isinstance(item, dict) and "criterion_id" in item
        }
        return GeneratedFile(
            code=data["code"],
            coverage=coverage,
            assumptions=list(data.get("assumptions", [])),
            model=getattr(response, "model", ""),
        )
