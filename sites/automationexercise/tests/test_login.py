from sites.automationexercise.config import Config
from sites.automationexercise.pages.login_page import LoginPage


class TestLogin:
    def test_valid_login(self, page):
        login_page = LoginPage(page)
        login_page.navigate()
        login_page.login(Config.EMAIL, Config.PASSWORD)
        assert login_page.is_logged_in()

    def test_invalid_username(self, page):
        login_page = LoginPage(page)
        login_page.navigate()
        login_page.login("invalid@gmail.com", Config.PASSWORD)
        assert login_page.get_error_message() == "Your email or password is incorrect!"

    def test_invalid_password(self, page):
        login_page = LoginPage(page)
        login_page.navigate()
        login_page.login(Config.EMAIL, 'invalid')
        assert login_page.get_error_message() == "Your email or password is incorrect!"

    def test_missing_login_credentials(self, page):
        login_page = LoginPage(page)
        login_page.navigate()
        login_page.login(Config.EMAIL, '')
        assert not login_page.is_logged_in()
