from playwright.sync_api import Page
from sites.saucedemo.config import Config


class InventoryPage:
    URL = f"{Config.BASE_URL}/inventory.html"

    def __init__(self, page: Page):
        self.page = page
        self.inventory_items = page.locator(".inventory_item")
        self.cart_icon = page.locator(".shopping_cart_link")
        self.cart_badge = page.locator(".shopping_cart_badge")
        self.sort_dropdown = page.locator("[data-test='product-sort-container']")
        self.item_names = page.locator("[data-test='inventory-item-name']")
        self.item_prices = page.locator("[data-test='inventory-item-price']")

    def get_item_count(self) -> int:
        # count() does not wait, so wait for the product list to render first
        self.inventory_items.first.wait_for()
        return self.inventory_items.count()

    def add_item_to_cart(self, item_name: str):
        item = self.page.locator(
            f".inventory_item:has-text('{item_name}')"
        )
        item.locator("button").click()

    def get_cart_count(self) -> str:
        return self.cart_badge.text_content()

    def go_to_cart(self):
        self.cart_icon.click()

    def sort_by(self, option: str):
        """option is the dropdown's value: az, za, lohi or hilo"""
        self.sort_dropdown.select_option(option)

    def get_item_names(self) -> list:
        self.inventory_items.first.wait_for()
        return self.item_names.all_text_contents()

    def get_item_prices(self) -> list:
        """Prices as numbers, e.g. [7.99, 9.99, ...]"""
        self.inventory_items.first.wait_for()
        return [float(price.replace("$", "")) for price in self.item_prices.all_text_contents()]