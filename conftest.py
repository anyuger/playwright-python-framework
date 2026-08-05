import pytest
import os
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright

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


@pytest.fixture(scope="session")
def browser():
    logger.info("Starting browser session")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        yield browser
        browser.close()
    logger.info("Browser session closed")


@pytest.fixture(scope="function")
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    logger.info(f"Starting test - new page created")
    yield page
    context.close()
    logger.info("Test complete - context closed")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        if report.failed:
            logger.error(f"TEST FAILED: {item.name}")
            page = item.funcargs.get("page")
            if page:
                screenshots_dir = "screenshots"
                os.makedirs(screenshots_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = os.path.join(
                    screenshots_dir, f"{item.name}_{timestamp}.png"
                )
                page.screenshot(path=screenshot_path)
                logger.info(f"Screenshot saved: {screenshot_path}")
        else:
            logger.info(f"TEST PASSED: {item.name}")