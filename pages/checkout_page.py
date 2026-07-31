from playwright.sync_api import Page
from config import Config


class CheckoutPage:
    URL = f"{Config.BASE_URL}/checkout-step-one.html"

    def __init__(self, page: Page):
        self.page = page
        self.first_name_input = page.locator("[data-test='firstName']")
        self.last_name_input = page.locator("[data-test='lastName']")
        self.postal_code_input = page.locator("[data-test='postalCode']")
        self.continue_button = page.locator("[data-test='continue']")
        self.finish_button = page.locator("[data-test='finish']")
        self.complete_header = page.locator("[data-test='complete-header']")
        self.error_message = page.locator("[data-test='error']")

    def fill_customer_info(self, first_name: str, last_name: str, postal_code: str):
        self.first_name_input.fill(first_name)
        self.last_name_input.fill(last_name)
        self.postal_code_input.fill(postal_code)

    def continue_to_overview(self):
        self.continue_button.click()

    def finish_checkout(self):
        self.finish_button.click()

    def get_complete_header(self) -> str:
        return self.complete_header.text_content()

    def get_error_message(self) -> str:
        return self.error_message.text_content()