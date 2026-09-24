# Playwright Python Automation Framework

![Playwright Tests](https://github.com/anyuger/playwright-python-framework/actions/workflows/tests.yml/badge.svg)

A professional test automation framework built with Playwright and Python, demonstrating Page Object Model architecture, API testing, CI/CD integration, and production-grade engineering practices.

## Tech Stack

- **Python 3.13**
- **Playwright** - browser automation
- **pytest** - test runner
- **pytest-playwright** - Playwright pytest integration
- **requests** - API testing
- **allure-pytest** - test reporting
- **python-dotenv** - environment variable management

## Project Structure

Each website under test has its own folder in `sites/` with its own pages, tests and settings.
Shared machinery (browser fixtures, logging, screenshots, pytest and Docker setup) stays at the root.

```
playwright-python-framework/
├── sites/
│   ├── saucedemo/                  # UI tests for saucedemo.com
│   │   ├── config.py               # URL, test users, timeouts
│   │   ├── pages/                  # Page objects: login, inventory, cart, checkout
│   │   └── tests/                  # Login, inventory and end-to-end checkout tests
│   ├── automationexercise/         # UI tests for automationexercise.com
│   │   ├── config.py               # URL, credentials from .env
│   │   ├── pages/                  # Page objects: login, products
│   │   └── tests/                  # Login and product search tests
│   └── reqres_api/                 # REST API tests for reqres.in
│       ├── api_client.py           # REST API client
│       └── tests/                  # CRUD and error handling tests
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