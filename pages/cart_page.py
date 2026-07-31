from playwright.sync_api import Page
from config import Config


class CartPage:
    URL = f"{Config.BASE_URL}/cart.html"

    def __init__(self, page: Page):
        self.page = page
        self.cart_items = page.locator(".cart_item")
        self.checkout_button = page.locator("[data-test='checkout']")
        self.continue_shopping_button = page.locator("[data-test='continue-shopping']")
        self.item_names = page.locator(".inventory_item_name")

    def get_cart_item_count(self) -> int:
        return self.cart_items.count()

    def get_item_names(self) -> list:
        return self.item_names.all_text_contents()

    def proceed_to_checkout(self):
        self.checkout_button.click()

    def continue_shopping(self):
        self.continue_shopping_button.click()