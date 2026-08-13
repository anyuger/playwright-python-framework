from playwright.sync_api import Page

from config import Config


class AELoginPage:
    URL = f'{Config.AE_BASE_URL}/login'

    def __init__(self, page: Page):
        self.page = page
        self.username_input = page.locator("[data-qa='login-email']")
        self.password_input = page.locator("[data-qa='login-password']")
        self.login_button = page.locator("[data-qa='login-button']")
        self.error_message = page.locator("p:has-text('Your email or password is incorrect!')")

    def navigate(self):
        self.page.goto(self.URL, wait_until="domcontentloaded")
        self.page.locator("[data-qa='login-email']").wait_for(timeout=15000)

    def login(self, username, password):
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.login_button.click()

    def is_logged_in(self) -> bool:
        return self.page.locator("a[href='/logout']").is_visible()

    def get_error_message(self) -> str:
        return self.error_message.text_content()
