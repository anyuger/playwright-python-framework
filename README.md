# Playwright Python Automation Framework

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

```
playwright-python-framework/
├── pages/                  # Page Object Model classes
│   ├── login_page.py       # Login page interactions
│   ├── inventory_page.py   # Inventory/product page interactions
│   ├── cart_page.py        # Shopping cart interactions
│   └── checkout_page.py    # Checkout flow interactions
├── tests/                  # Test suites
│   ├── test_login.py       # Login tests (valid, invalid, empty)
│   ├── test_inventory.py   # Inventory and cart tests
│   ├── test_checkout.py    # End-to-end checkout tests
│   └── test_api.py         # REST API tests (reqres.in)
├── utils/                  # Shared utilities
│   └── api_client.py       # REST API client
├── test_data/              # Test data (reserved for future use)
├── config.py               # Centralized configuration
├── conftest.py             # Fixtures, logging, screenshot on failure
├── pytest.ini              # pytest configuration
└── requirements.txt        # Pinned dependencies
```

## Design Decisions

- **Page Object Model** - each page is a class with locators as attributes and user actions as methods. Tests call `login_page.login()`, not raw Playwright selectors, so locator changes require a single fix in one place.
- **Config layer** - all URLs, credentials, and timeouts live in `config.py`. No hardcoded values in test files.
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

REQRES_API_KEY=your_api_key_here

Get a free API key at [reqres.in](https://reqres.in).

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_login.py

# Run with verbose output
pytest -v

# Run headless (no browser window)
pytest --headless
```

## Test Coverage

### UI Tests (saucedemo.com)
- Login - valid credentials, invalid credentials, empty fields
- Inventory - page loads, item count, add single/multiple items to cart
- Checkout - complete end-to-end flow, missing customer info validation, cart item verification

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