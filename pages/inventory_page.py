from playwright.sync_api import Page
from config import Config


class InventoryPage:
    URL = f"{Config.BASE_URL}/inventory.html"

    def __init__(self, page: Page):
        self.page = page
        self.inventory_items = page.locator(".inventory_item")
        self.cart_icon = page.locator(".shopping_cart_link")
        self.cart_badge = page.locator(".shopping_cart_badge")

    def get_item_count(self) -> int:
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