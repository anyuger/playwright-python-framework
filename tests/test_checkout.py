import pytest
from pages.login_page import LoginPage
from pages.inventory_page import InventoryPage
from pages.cart_page import CartPage
from pages.checkout_page import CheckoutPage
from config import Config


class TestCheckout:

    @pytest.fixture(autouse=True)
    def login(self, page):
        login_page = LoginPage(page)
        login_page.navigate()
        login_page.login(Config.STANDARD_USER, Config.PASSWORD)

    def test_complete_checkout_flow(self, page):
        # Add item to cart
        inventory_page = InventoryPage(page)
        inventory_page.add_item_to_cart("Sauce Labs Backpack")
        inventory_page.go_to_cart()

        # Verify cart
        cart_page = CartPage(page)
        assert cart_page.get_cart_item_count() == 1
        assert "Sauce Labs Backpack" in cart_page.get_item_names()

        # Proceed to checkout
        cart_page.proceed_to_checkout()

        # Fill customer info
        checkout_page = CheckoutPage(page)
        checkout_page.fill_customer_info("John", "Doe", "V5C 0A3")
        checkout_page.continue_to_overview()

        # Finish checkout
        checkout_page.finish_checkout()

        # Verify order complete
        assert checkout_page.get_complete_header() == "Thank you for your order!"

    def test_checkout_without_customer_info(self, page):
        inventory_page = InventoryPage(page)
        inventory_page.add_item_to_cart("Sauce Labs Backpack")
        inventory_page.go_to_cart()

        cart_page = CartPage(page)
        cart_page.proceed_to_checkout()

        checkout_page = CheckoutPage(page)
        checkout_page.continue_to_overview()

        assert checkout_page.get_error_message() == "Error: First Name is required"

    def test_cart_shows_correct_items(self, page):
        inventory_page = InventoryPage(page)
        inventory_page.add_item_to_cart("Sauce Labs Backpack")
        inventory_page.add_item_to_cart("Sauce Labs Bike Light")
        inventory_page.go_to_cart()

        cart_page = CartPage(page)
        assert cart_page.get_cart_item_count() == 2
        item_names = cart_page.get_item_names()
        assert "Sauce Labs Backpack" in item_names
        assert "Sauce Labs Bike Light" in item_names