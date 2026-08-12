from config import Config
from pages.ae_login_page import AELoginPage


class TestAELogin:
    def test_valid_login(self, page):
        login_page = AELoginPage(page)
        login_page.navigate()
        login_page.login(Config.AE_EMAIL, Config.AE_PASSWORD)
        assert login_page.is_logged_in()

    def test_invalid_username(self, page):
        login_page = AELoginPage(page)
        login_page.navigate()
        login_page.login("invalid@gmail.com", Config.AE_PASSWORD)
        assert login_page.get_error_message() == "Your email or password is incorrect!"

    def test_invalid_password(self, page):
        login_page = AELoginPage(page)
        login_page.navigate()
        login_page.login(Config.AE_EMAIL, 'invalid')
        assert login_page.get_error_message() == "Your email or password is incorrect!"

    def test_missing_login_credentials(self, page):
        login_page = AELoginPage(page)
        login_page.navigate()
        login_page.login(Config.AE_EMAIL, '')
        assert not login_page.is_logged_in()
