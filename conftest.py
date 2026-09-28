import pytest
import os
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("test_run.log", mode="w")
    ]
)
logger = logging.getLogger(__name__)

# The browser, context and page fixtures come from pytest-playwright, so its options work:
#   pytest --headed                     show the browser window (headless by default)
#   pytest --browser firefox            run in another browser; repeat --browser for several
#   pytest --tracing retain-on-failure  keep a Playwright trace of each failed test (set in pytest.ini)


@pytest.fixture(autouse=True)
def _keep_page_for_screenshots(request):
    # Only for tests that use a browser, so API and agent unit tests never start one.
    # Autouse fixtures from this file run before a test class's autouse login, so the page
    # is stored on the test item even when the login fails, and the screenshot hook finds it.
    if "page" in request.fixturenames:
        request.node._page = request.getfixturevalue("page")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    # "setup" covers fixtures (a broken login), "call" covers the test body
    if report.when not in ("setup", "call"):
        return

    if report.failed:
        logger.error(f"TEST FAILED ({report.when}): {item.name}")
        page = getattr(item, "_page", None)
        if page:
            # Title and URL tell "our bug" from "the site showed something else"
            # (e.g. a Cloudflare "Just a moment..." check) without opening the screenshot
            try:
                logger.error(f"Page at failure: {page.url} - title '{page.title()}'")
            except Exception as error:
                logger.error(f"Page at failure: could not read page ({error})")
            screenshots_dir = "screenshots"
            os.makedirs(screenshots_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(
                screenshots_dir, f"{item.name}_{report.when}_{timestamp}.png"
            )
            try:
                page.screenshot(path=screenshot_path)
                logger.info(f"Screenshot saved: {screenshot_path}")
            except Exception as error:
                logger.error(f"Screenshot failed ({error})")
    elif report.when == "call" and report.passed:
        logger.info(f"TEST PASSED: {item.name}")