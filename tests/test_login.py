import pytest
from pages.login_page import LoginPage


class TestLogin:

    def test_valid_login(self, page):
        login_page = LoginPage(page)
        login_page.navigate()
        login_page.login("standard_user", "secret_sauce")
        assert page.url == "https://www.saucedemo.com/inventory.html"

    def test_invalid_login(self, page):
        login_page = LoginPage(page)
        login_page.navigate()
        login_page.login("invalid_user", "wrong_password")
        assert login_page.get_error_message() == "Epic sadface: Username and password do not match any user in this service"

    def test_empty_credentials(self, page):
        login_page = LoginPage(page)
        login_page.navigate()
        login_page.login("", "")
        assert login_page.get_error_message() == "Epic sadface: Username is required"