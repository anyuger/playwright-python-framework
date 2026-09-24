"""
Unit tests for the spec-to-test agent. No API key, network or browser needed:
the Anthropic client and the pytest runner are replaced with fakes.
"""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from agent import checks
from agent.config import AgentConfig
from agent.context import build_context, page_object_api
from agent.generator import GeneratedFile
from agent.llm_client import BudgetExceededError, LLMClient, LLMUnavailableError, calculate_cost
from agent.pipeline import NEEDS_REVIEW, QUARANTINED, TRUSTED, SpecPipeline, add_skip_markers
from agent.runner import RunResult
from agent.site import SiteError, load_site
from agent.spec import load_spec

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def run_from_repo_root(monkeypatch):
    monkeypatch.chdir(REPO_ROOT)


class FastConfig(AgentConfig):
    MAX_RETRIES = 3
    MAX_REPAIR_ATTEMPTS = 2
    MAX_RUN_COST_USD = 1.00


# ------------------------------------------------------------------ fakes

def fake_response(model="claude-sonnet-5", input_tokens=1000, output_tokens=500, code="x = 1"):
    return SimpleNamespace(
        model=model,
        stop_reason="tool_use",
        content=[SimpleNamespace(type="tool_use", input={"code": code, "coverage": [], "assumptions": []})],
        usage=SimpleNamespace(
            input_tokens=input_tokens, output_tokens=output_tokens,
            cache_creation_input_tokens=0, cache_read_input_tokens=0,
        ),
    )


def api_error(status_code, error_class):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return error_class("simulated", response=httpx2.Response(status_code, request=request), body=None)


class FakeAnthropic:
    """Plays back a script of responses or exceptions, recording the models asked for."""

    def __init__(self, script):
        self.script = list(script)
        self.models_called = []
        self.messages = self

    def create(self, **request):
        self.models_called.append(request["model"])
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_llm(script, sleeps=None):
    sleeps = sleeps if sleeps is not None else []
    return LLMClient(client=FakeAnthropic(script), config=FastConfig, sleep=sleeps.append)


# ------------------------------------------------------------------ LLM client

class TestLLMClient:

    def test_cost_uses_model_pricing(self):
        usage = SimpleNamespace(input_tokens=1_000_000, output_tokens=100_000,
                                cache_creation_input_tokens=0, cache_read_input_tokens=500_000)
        # Sonnet 5: $2 input + $1 output (100K x $10/M) + $0.10 cache read
        assert calculate_cost("claude-sonnet-5", usage) == pytest.approx(3.10)

    def test_retries_transient_errors_with_growing_backoff(self):
        sleeps = []
        llm = make_llm([
            api_error(429, anthropic.RateLimitError),
            api_error(529, anthropic.OverloadedError),
            fake_response(),
        ], sleeps)
        llm.create_message(purpose="t", messages=[])
        assert llm.calls[0].attempt == 3
        assert len(sleeps) == 2 and sleeps[1] > sleeps[0]

    def test_falls_back_when_primary_stays_unavailable(self):
        llm = make_llm([api_error(529, anthropic.OverloadedError)] * 3
                       + [fake_response(model=FastConfig.FALLBACK_MODEL)])
        llm.create_message(purpose="t", messages=[])
        assert llm.client.models_called == [FastConfig.PRIMARY_MODEL] * 3 + [FastConfig.FALLBACK_MODEL]
        assert llm.calls[0].model == FastConfig.FALLBACK_MODEL

    def test_unknown_model_goes_straight_to_fallback(self):
        llm = make_llm([api_error(404, anthropic.NotFoundError), fake_response()])
        llm.create_message(purpose="t", messages=[])
        assert llm.client.models_called == [FastConfig.PRIMARY_MODEL, FastConfig.FALLBACK_MODEL]

    def test_bad_request_is_not_retried(self):
        llm = make_llm([api_error(400, anthropic.BadRequestError)])
        with pytest.raises(anthropic.BadRequestError):
            llm.create_message(purpose="t", messages=[])

    def test_raises_when_every_model_fails(self):
        llm = make_llm([api_error(500, anthropic.InternalServerError)] * 6)
        with pytest.raises(LLMUnavailableError):
            llm.create_message(purpose="t", messages=[])

    def test_budget_stops_further_calls(self):
        # 1M output tokens on Sonnet 5 = $10, over the $1 budget
        llm = make_llm([fake_response(output_tokens=1_000_000), fake_response()])
        llm.create_message(purpose="first", messages=[])
        with pytest.raises(BudgetExceededError):
            llm.create_message(purpose="second", messages=[])


# ------------------------------------------------------------------ spec + static checks

GOOD_CODE = '''import pytest
from sites.saucedemo.pages.login_page import LoginPage
from sites.saucedemo.pages.inventory_page import InventoryPage
from sites.saucedemo.config import Config


class TestSample:

    @pytest.fixture(autouse=True)
    def login(self, page):
        login_page = LoginPage(page)
        login_page.navigate()
        login_page.login(Config.STANDARD_USER, Config.PASSWORD)

    def test_add_one(self, page):
        """AC-1: one item shows badge 1"""
        inventory_page = InventoryPage(page)
        inventory_page.add_item_to_cart("Sauce Labs Backpack")
        assert inventory_page.get_cart_count() == "1"

    def test_add_two(self, page):
        """AC-2: two items show badge 2"""
        inventory_page = InventoryPage(page)
        inventory_page.add_item_to_cart("Sauce Labs Backpack")
        inventory_page.add_item_to_cart("Sauce Labs Bike Light")
        assert inventory_page.get_cart_count() == "2"
'''
CRITERIA = {"AC-1": "one item", "AC-2": "two items"}


def messages(analysis):
    return [f.message for f in analysis.all_findings]


def saucedemo_api():
    return page_object_api(load_site("saucedemo"))


def analyze(code, criteria=CRITERIA):
    return checks.analyze(code, criteria, saucedemo_api(), load_site("saucedemo").allowed_imports)


# ------------------------------------------------------------------ sites


class TestSites:

    def test_saucedemo_layout_is_found(self):
        site = load_site("saucedemo")
        assert [p.name for p in site.page_files] == [
            "cart_page.py", "checkout_page.py", "inventory_page.py", "login_page.py"]
        assert site.package == "sites.saucedemo"
        assert site.generated_dir.as_posix() == "sites/saucedemo/tests/generated"
        assert site.style_example.as_posix() == "sites/saucedemo/tests/test_checkout.py"

    def test_page_object_api_is_per_site(self):
        assert "add_item_to_cart" in saucedemo_api()["InventoryPage"]
        assert "search_product" in page_object_api(load_site("automationexercise"))["ProductsPage"]

    def test_unknown_site_lists_the_real_ones(self):
        with pytest.raises(SiteError) as error:
            load_site("nosuchsite")
        assert "saucedemo" in str(error.value) and "automationexercise" in str(error.value)

    def test_site_without_page_objects_is_refused(self):
        with pytest.raises(SiteError):
            load_site("reqres_api")   # API tests only - nothing for the agent to build on

    def test_specs_found_without_the_shell_expanding_globs(self):
        site = load_site("saucedemo")
        on_disk = sorted(p.as_posix() for p in Path("sites/saucedemo/specs").glob("*.md"))
        assert site.find_specs() == on_disk   # no hard-coded count: specs get added over time
        assert site.find_specs(["checkout_required_fields"]) == [
            "sites/saucedemo/specs/checkout_required_fields.md"]
        assert len(site.find_specs(["sites/saucedemo/specs/checkout_*.md"])) == 2
        with pytest.raises(SiteError):
            site.find_specs(["no_such_spec"])

    def test_context_names_the_site_package(self):
        context = build_context(load_site("saucedemo"))
        assert "from sites.saucedemo.config import Config" in context
        assert "## sites/saucedemo/pages/login_page.py" in context


class TestStaticChecks:

    def test_spec_criteria_are_parsed(self):
        spec = load_spec("sites/saucedemo/specs/checkout_required_fields.md")
        assert list(spec.criteria) == ["AC-1", "AC-2", "AC-3"]
        assert spec.name == "checkout_required_fields"

    def test_clean_file_has_no_findings(self):
        analysis = analyze(GOOD_CODE)
        assert analysis.all_findings == []
        assert analysis.tests["test_add_one"].criteria == {"AC-1"}

    def test_invented_page_object_method_is_a_blocker(self):
        code = GOOD_CODE.replace("get_cart_count()", "get_badge_text()", 1)
        analysis = analyze(code)
        assert any("InventoryPage has no 'get_badge_text'" in f.message for f in analysis.blockers)

    def test_invented_method_in_fixture_is_caught(self):
        code = GOOD_CODE.replace("login_page.login(", "login_page.sign_in(")
        analysis = analyze(code)
        assert any("LoginPage has no 'sign_in'" in f.message for f in analysis.blockers)

    def test_hard_wait_is_a_blocker(self):
        code = GOOD_CODE.replace('        assert inventory_page.get_cart_count() == "1"',
                                 '        page.wait_for_timeout(2000)\n        assert inventory_page.get_cart_count() == "1"')
        assert any("Hard wait" in m for m in messages(analyze(code)))

    def test_raw_locator_needs_review_not_repair(self):
        code = GOOD_CODE.replace(
            '        assert inventory_page.get_cart_count() == "2"',
            '        page.locator("[data-test=\'remove-sauce-labs-backpack\']").click()  # NEW-LOCATOR: remove\n'
            '        assert inventory_page.get_cart_count() == "1"')
        analysis = analyze(code)
        assert analysis.blockers == []
        assert [f.severity for f in analysis.tests["test_add_two"].findings] == [checks.REVIEW]

    def test_raw_locator_is_caught_whatever_the_variable_is_called(self):
        # Found by the first real run: the model wrote overview_page.locator(...) with no
        # NEW-LOCATOR comment on that line, and the old check only knew "page.locator"
        code = GOOD_CODE.replace(
            '        assert inventory_page.get_cart_count() == "1"',
            '        overview = page\n'
            '        expect_text = overview.locator("[data-test=\'total-label\']").text_content()\n'
            '        assert expect_text == "Total: $32.39"')
        findings = analyze(code).tests["test_add_one"].findings
        assert [f.severity for f in findings] == [checks.REVIEW]
        assert "overview.locator()" in findings[0].message

    def test_raw_locator_in_a_fixture_flags_the_tests(self):
        code = GOOD_CODE.replace(
            "        login_page.login(Config.STANDARD_USER, Config.PASSWORD)",
            "        login_page.login(Config.STANDARD_USER, Config.PASSWORD)\n"
            "        page.get_by_text(\"Open Menu\").click()")
        analysis = analyze(code)
        assert analysis.blockers == []
        for name in ("test_add_one", "test_add_two"):
            assert any("in fixture/helper 'login'" in f.message for f in analysis.tests[name].findings)

    def test_uncovered_criterion_and_missing_assert(self):
        code = GOOD_CODE.replace('        assert inventory_page.get_cart_count() == "2"\n', "")
        analysis = analyze(code, {**CRITERIA, "AC-3": "not tested"})
        assert "AC-3" in analysis.uncovered_criteria
        assert any("cannot fail" in m for m in messages(analysis))

    def test_forbidden_import_and_syntax_error(self):
        analysis = analyze("import os\n" + GOOD_CODE)
        assert any("Import not allowed: os" in m for m in messages(analysis))
        broken = analyze("def test_x(:\n")
        assert "Syntax error" in broken.blockers[0].message

    def test_importing_another_sites_pages_is_a_blocker(self):
        code = GOOD_CODE.replace("from sites.saucedemo.pages.login_page",
                                 "from sites.automationexercise.pages.login_page")
        assert any("Import not allowed: sites.automationexercise" in f.message for f in analyze(code).blockers)

    def test_assertion_values_detect_changed_expectations(self):
        before = 'def test_x(p):\n    assert p.text() == "Error: Last Name is required"\n'
        after = 'def test_x(p):\n    assert p.text() == "Error: Last name required"\n'
        assert checks.assertion_values(before) != checks.assertion_values(after)

    def test_skip_markers_are_inserted_above_tests(self):
        marked = add_skip_markers(GOOD_CODE, {"test_add_two": "agent: needs review - x"})
        lines = marked.splitlines()
        index = next(i for i, line in enumerate(lines) if "def test_add_two" in line)
        assert lines[index - 1] == "    @pytest.mark.skip(reason='agent: needs review - x')"
        compile(marked, "marked.py", "exec")


# ------------------------------------------------------------------ pipeline (self-healing loop)

class FakeGenerator:
    def __init__(self, versions):
        self.versions = list(versions)
        self.repair_prompts = []

    def generate(self, spec):
        return GeneratedFile(code=self.versions.pop(0), model="fake")

    def repair(self, spec, previous, problems):
        self.repair_prompts.append(problems)
        return GeneratedFile(code=self.versions.pop(0), model="fake")


class FakeRunner:
    def __init__(self, runs, failure_message="AssertionError"):
        self.runs = list(runs)
        self.failure_message = failure_message

    def __call__(self, test_file):
        outcomes = self.runs.pop(0)
        failed = {name: self.failure_message for name, outcome in outcomes.items() if outcome != "passed"}
        return RunResult(outcomes=outcomes, messages=failed)


def make_pipeline(tmp_path, generator, runner, config=FastConfig):
    site = replace(load_site("saucedemo"), generated_dir=tmp_path / "generated")  # never write into the repo
    return SpecPipeline(generator, site, page_object_api(site), tmp_path / "run", runner=runner, config=config)


def two_ac_spec(tmp_path):
    path = tmp_path / "badge.md"
    path.write_text("# Badge\n- AC-1: one item\n- AC-2: two items\n", encoding="utf-8")
    return load_spec(str(path))


class TestPipeline:

    def test_self_healing_flow_and_verdicts(self, tmp_path):
        v1 = GOOD_CODE.replace('get_cart_count() == "2"', 'get_badge() == "2"')     # invented method
        v2 = GOOD_CODE                                                              # fixed, but test_add_two fails
        v3 = GOOD_CODE.replace('get_cart_count() == "2"', 'get_cart_count() == "3"')  # "fixed" by changing expectation
        generator = FakeGenerator([v1, v2, v3])
        runner = FakeRunner([
            {"test_add_one": "passed", "test_add_two": "failed"},
            {"test_add_one": "passed", "test_add_two": "passed"},
            {"test_add_one": "passed", "test_add_two": "passed"},   # stability re-run
        ])
        result = make_pipeline(tmp_path, generator, runner).process(two_ac_spec(tmp_path))

        verdicts = {v.name: v for v in result.verdicts}
        assert result.status == "done" and len(result.attempts) == 3
        assert "InventoryPage has no 'get_badge'" in generator.repair_prompts[0]
        assert verdicts["test_add_one"].verdict == TRUSTED
        assert verdicts["test_add_two"].verdict == NEEDS_REVIEW
        assert any("Expected values changed" in r for r in verdicts["test_add_two"].reasons)

        written = Path(result.output_path).read_text(encoding="utf-8")
        assert written.count("@pytest.mark.skip") == 1

    def test_still_failing_test_is_quarantined(self, tmp_path):
        generator = FakeGenerator([GOOD_CODE] * 3)
        runner = FakeRunner([{"test_add_one": "passed", "test_add_two": "failed"}] * 3)
        result = make_pipeline(tmp_path, generator, runner).process(two_ac_spec(tmp_path))
        verdicts = {v.name: v.verdict for v in result.verdicts}
        assert verdicts == {"test_add_one": TRUSTED, "test_add_two": QUARANTINED}

    def test_flaky_test_needs_review(self, tmp_path):
        generator = FakeGenerator([GOOD_CODE])
        runner = FakeRunner([
            {"test_add_one": "passed", "test_add_two": "passed"},
            {"test_add_one": "passed", "test_add_two": "failed"},
        ])
        result = make_pipeline(tmp_path, generator, runner).process(two_ac_spec(tmp_path))
        verdicts = {v.name: v for v in result.verdicts}
        assert verdicts["test_add_two"].verdict == NEEDS_REVIEW
        assert "Flaky" in verdicts["test_add_two"].reasons[0]

    def test_file_is_rejected_when_blockers_survive_repairs(self, tmp_path):
        bad = GOOD_CODE.replace("get_cart_count()", "get_badge()")
        result = make_pipeline(tmp_path, FakeGenerator([bad] * 3), FakeRunner([])).process(two_ac_spec(tmp_path))
        assert result.status == "rejected" and result.output_path == ""

    def test_existing_reviewed_file_is_not_overwritten(self, tmp_path):
        reviewed = tmp_path / "generated" / "test_gen_badge.py"
        reviewed.parent.mkdir(parents=True)
        reviewed.write_text("# reviewed and edited by a human\n", encoding="utf-8")
        runner = FakeRunner([{"test_add_one": "passed", "test_add_two": "passed"}] * 2)

        result = make_pipeline(tmp_path, FakeGenerator([GOOD_CODE]), runner).process(two_ac_spec(tmp_path))

        assert reviewed.read_text(encoding="utf-8") == "# reviewed and edited by a human\n"
        assert result.output_path == "" and "already exists" in result.note
        assert (tmp_path / "run" / "badge" / "test_gen_badge.py").exists()   # new version parked

    def test_overwrite_replaces_the_existing_file(self, tmp_path):
        class Overwrite(FastConfig):
            OVERWRITE_GENERATED = True
        reviewed = tmp_path / "generated" / "test_gen_badge.py"
        reviewed.parent.mkdir(parents=True)
        reviewed.write_text("# old\n", encoding="utf-8")
        runner = FakeRunner([{"test_add_one": "passed", "test_add_two": "passed"}] * 2)

        result = make_pipeline(tmp_path, FakeGenerator([GOOD_CODE]), runner, Overwrite).process(two_ac_spec(tmp_path))

        assert result.output_path and "class TestSample" in reviewed.read_text(encoding="utf-8")

    def test_unreachable_site_stops_without_paying_for_repairs(self, tmp_path):
        generator = FakeGenerator([GOOD_CODE] * 3)
        runner = FakeRunner([{"test_add_one": "error", "test_add_two": "error"}],
                            failure_message="Page.goto: net::ERR_NAME_NOT_RESOLVED")
        result = make_pipeline(tmp_path, generator, runner).process(two_ac_spec(tmp_path))
        assert result.status == "error" and "Environment problem" in result.error
        assert generator.repair_prompts == [] and result.output_path == ""
