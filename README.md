# Playwright Python Automation Framework

![Playwright Tests](https://github.com/anyuger/playwright-python-framework/actions/workflows/tests.yml/badge.svg)

A professional test automation framework built with Playwright and Python, demonstrating Page Object Model architecture, API testing, CI/CD integration, and production-grade engineering practices.

It also includes a **spec-to-test agent** that uses Claude to generate tests from acceptance criteria, repairs its own failures, and decides which generated tests can be trusted and which need a human. See [Spec-to-test agent](#spec-to-test-agent).

## Tech Stack

- **Python 3.13**
- **Playwright** - browser automation
- **pytest** - test runner
- **pytest-playwright** - Playwright pytest integration
- **requests** - API testing
- **allure-pytest** - test reporting
- **python-dotenv** - environment variable management
- **anthropic** - Claude API, used by the spec-to-test agent

## Project Structure

Each website under test has its own folder in `sites/` with its own pages, tests and settings.
Shared machinery (browser fixtures, logging, screenshots, pytest and Docker setup, the agent) stays at the root.

```
playwright-python-framework/
├── sites/
│   ├── saucedemo/                  # UI tests for saucedemo.com
│   │   ├── config.py               # URL, test users, timeouts
│   │   ├── pages/                  # Page objects: login, inventory, cart, checkout
│   │   ├── specs/                  # Specs with acceptance criteria - agent input
│   │   └── tests/                  # Login, inventory and end-to-end checkout tests
│   │       └── generated/          # Tests written by the agent
│   ├── automationexercise/         # UI tests for automationexercise.com
│   │   ├── config.py               # URL, credentials from .env
│   │   ├── pages/                  # Page objects: login, products
│   │   └── tests/                  # Login and product search tests
│   └── reqres_api/                 # REST API tests for reqres.in
│       ├── api_client.py           # REST API client
│       └── tests/                  # CRUD and error handling tests
├── agent/                          # Spec-to-test agent (see below)
│   └── tests/                      # Agent unit tests (mocked, no API calls)
├── conftest.py                     # Shared fixtures, logging, screenshot on failure
├── pytest.ini                      # pytest configuration
├── Dockerfile                      # Container for CI runs
└── requirements.txt                # Pinned dependencies
```

### Adding a new site

1. Create `sites/<site_name>/` with `config.py`, `pages/`, `tests/` and an empty `__init__.py` in each folder.
2. Import with the full path, for example `from sites.<site_name>.pages.login_page import LoginPage`.
3. Run it with `pytest sites/<site_name>`.

## Design Decisions

- **Page Object Model** - each page is a class with locators as attributes and user actions as methods. Tests call `login_page.login()`, not raw Playwright selectors, so locator changes require a single fix in one place.
- **Config layer** - each site keeps its URLs, credentials, and timeouts in its own `config.py`. No hardcoded values in test files.
- **One folder per site** - pages, tests and settings for a site live together under `sites/`, so sites never share or overwrite each other's page objects.
- **Session-scoped browser, function-scoped page** - one browser instance per test run, fresh context per test. Ensures test isolation without the overhead of launching a new browser for every test.
- **Screenshot on failure** - `conftest.py` hooks into pytest's reporting lifecycle and automatically captures a timestamped screenshot when any test fails.
- **Logging** - every test run produces a `test_run.log` with timestamps and pass/fail status for each test, making failures traceable without re-running.
- **API key in .env** - credentials are never committed to source control.

## Setup

### Prerequisites
- Python 3.13+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/anyuger/playwright-python-framework.git
cd playwright-python-framework

# Create and activate virtual environment
python -m venv venv
venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate    # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install
```

### Environment Variables

Create a `.env` file in the project root:

```
REQRES_API_KEY=your_api_key_here
AE_EMAIL=your_automationexercise_email
AE_PASSWORD=your_automationexercise_password
ANTHROPIC_API_KEY=your_anthropic_key_here   # only needed for the agent
```

Get a free API key at [reqres.in](https://reqres.in).

## Running Tests

```bash
# Run all tests
pytest

# Run one site
pytest sites/saucedemo
pytest sites/automationexercise
pytest sites/reqres_api

# Run specific test file
pytest sites/saucedemo/tests/test_login.py

# Run with verbose output
pytest -v

# Run headless (no browser window)
$env:HEADLESS="true"; pytest   # Windows PowerShell
HEADLESS=true pytest             # Mac/Linux
```

## Running Tests in Docker

```bash
# Build the image
docker build -t playwright-framework .

# Run tests
docker run --rm -e REQRES_API_KEY=your_key_here -e AE_EMAIL=your_email -e AE_PASSWORD=your_password -e HEADLESS=true playwright-framework
```

## Test Coverage

### UI Tests (saucedemo.com)
- Login - valid credentials, invalid credentials, empty fields
- Inventory - page loads, item count, add single/multiple items to cart
- Checkout - complete end-to-end flow, missing customer info validation, cart item verification

### UI Tests (automationexercise.com)
- Login - valid credentials, invalid email, invalid password, missing password
- Products - page loads, product search, prices displayed

### API Tests (reqres.in)
- GET users - paginated list, single user
- POST - create user and verify response
- PUT - update user and verify response
- DELETE - delete user and verify 204 status
- Error handling - 404 for non-existent user

## Reporting

Allure results are generated automatically on every test run. To view the report:

```bash
# Install Allure CLI (one-time setup)
# See https://allurereport.org/docs/install/

# Generate and open report
allure serve allure-results
```

## Spec-to-test agent

The agent turns a spec with acceptance criteria into Playwright tests that use a site's existing page objects. It is built on the Claude API and runs locally or in GitHub Actions. It works on any site in `sites/` that has `config.py` and `pages/`.

```
spec.md -> generate -> static checks -> run -> repair (up to N times) -> verdict per test -> sites/<site>/tests/generated/
```

### Specs

A spec is markdown in `sites/<site>/specs/` with numbered criteria. Every generated test must reference the criteria it covers in its docstring, which is how coverage is checked without taking the model's word for it.

```markdown
# Checkout: required customer fields
- AC-1: Continuing with an empty last name shows the error "Error: Last Name is required".
- AC-2: ...
```

### Running it

Run from the repo root:

```bash
python -m agent --site saucedemo                             # every spec in sites/saucedemo/specs/
python -m agent --site saucedemo checkout_required_fields    # one spec, by name
python -m agent --site saucedemo "cart_*" --max-cost 0.50 --max-repairs 1
```

Generated files may already have been reviewed and edited by a human, so the agent never silently replaces one: if `test_gen_<spec>.py` exists, it is kept and the new version is saved in the run folder for comparison. Pass `--overwrite` (or tick "overwrite" in the workflow) to replace it.

Spec patterns are expanded by the agent itself, so they work the same in PowerShell and bash.

An example from a real run is in [docs/sample_run/report.md](docs/sample_run/report.md): 3 specs, 9 tests, $0.05, 3 trusted and 6 flagged for review.

Each run writes `agent_runs/<timestamp>_<site>/report.md` (and `report.json`) with every test's verdict, every attempt, and every LLM call's tokens, latency and cost. In CI, the **Spec-to-test agent** workflow (Actions tab, run manually, choose the site) does the same inside Docker, puts the report on the run page, and opens a pull request with the generated tests. It needs an `ANTHROPIC_API_KEY` repository secret, and "Allow GitHub Actions to create pull requests" turned on in the repo settings.

### Trusted or reviewed?

Generated tests are not all equal. Every test gets one verdict:

| Verdict | Rule | What happens |
|---|---|---|
| Trusted | Passed every run, including a stability re-run. Never changed by self-healing. Uses page objects only. | Runs in CI as-is |
| Needs review | Passes, but uses raw locators, was added or changed by a repair, failed before passing, or was flaky | Written with a `skip` marker and the reasons |
| Quarantined | Still failing after all repairs - a wrong test, or a real product defect | Written with a `skip` marker - triage it |

A file is **rejected** (not written) if static blockers survive every repair.

Static checks run on the code before anything executes (`agent/checks.py`, using Python's `ast` module):

- **Blockers** (sent back to the model to repair): syntax errors, calls to page object methods or locators that do not exist (the most common hallucination), `time.sleep` / `wait_for_timeout`, hard-coded URLs, imports outside the site's own config and pages, tests with no assertion, criteria with no test.
- **Review flags**: `page.locator(...)` in a test instead of a page object. The model must mark these `# NEW-LOCATOR` so a human moves them into the right page object.

### Self-healing, with limits

When checks or runs fail, the agent sends the problems (blocker list or pytest output) back to the model for a repair, up to `MAX_REPAIR_ATTEMPTS`. The repair may fix locators, waits and structure, but **must not change an expected value from the spec to make a test pass** - that would hide a real bug. The agent compares the asserted values before and after each repair and flags any change. If every test fails with a network error, the agent stops instead of paying for repairs that cannot help.

### Cost, latency and reliability

- **Prompt caching** - the site context (page objects, config, a style example) is the same for every spec, so it is cached; later calls read it at a tenth of the input price.
- **Budget cap** - `AGENT_MAX_COST_USD` (default $1.00) is checked before every call; the run stops cleanly when it is reached.
- **Retries** - 429, 5xx, 529 (overloaded) and network errors are retried with exponential backoff plus jitter, honouring `retry-after`. Other errors (400, 401) fail fast.
- **Model fallback** - if the primary model (`claude-sonnet-5`) stays unavailable, or is retired, the call falls back to `claude-haiku-4-5-20251001`.
- **Structured output** - the model answers through a forced tool call (`submit_test_file`), so the code, coverage map and assumptions arrive as fields, not text to parse. Output cut off at `max_tokens` is treated as a failure.
- Every call is logged with tokens, cache hits, latency and cost.

Settings live in `AgentConfig` in `agent/config.py`; most can be overridden with environment variables.

### Limits

- A passing test is not proof that it checks the right thing. The verdicts reduce review work; they do not replace review. A next step would be mutation-style checks (break the app on purpose and confirm the test fails).
- The agent only knows a site through its page objects and config. A site with no page objects (like `reqres_api`) is not supported.
- Prices in `AgentConfig.PRICING` are copied from the Claude pricing page and need updating when prices change.

The agent's own logic is covered by `agent/tests/test_agent_unit.py`, which uses a fake API client and a fake test runner, so it runs in the normal CI with no API key and no cost.
