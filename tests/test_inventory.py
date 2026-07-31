import pytest
from pages.login_page import LoginPage
from pages.inventory_page import InventoryPage
from config import Config


class TestInventory:

    @pytest.fixture(autouse=True)
    def login(self, page):
        login_page = LoginPage(page)
        login_page.navigate()
        login_page.login(Config.STANDARD_USER, Config.PASSWORD)

    def test_inventory_page_loads(self, page):
        inventory_page = InventoryPage(page)
        assert page.url == f"{Config.BASE_URL}/inventory.html"
        assert inventory_page.get_item_count() == 6

    def test_add_single_item_to_cart(self, page):
        inventory_page = InventoryPage(page)
        inventory_page.add_item_to_cart("Sauce Labs Backpack")
        assert inventory_page.get_cart_count() == "1"

    def test_add_multiple_items_to_cart(self, page):
        inventory_page = InventoryPage(page)
        inventory_page.add_item_to_cart("Sauce Labs Backpack")
        inventory_page.add_item_to_cart("Sauce Labs Bike Light")
        assert inventory_page.get_cart_count() == "2"

    def test_navigate_to_cart(self, page):
        inventory_page = InventoryPage(page)
        inventory_page.add_item_to_cart("Sauce Labs Backpack")
        inventory_page.go_to_cart()
        assert page.url == f"{Config.BASE_URL}/cart.html"