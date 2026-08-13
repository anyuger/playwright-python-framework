from playwright.sync_api import Page

from config import Config


class AEProductsPage:
    URL = f"{Config.AE_BASE_URL}/products"

    def __init__(self, page: Page):
        self.page = page
        self.search_input = page.locator("#search_product")
        self.search_button = page.locator("#submit_search")
        self.product_name = page.locator(".productinfo p")
        self.product_price = page.locator(".productinfo h2")

    def navigate(self):
        self.page.goto(self.URL, wait_until="domcontentloaded")
        self.search_input.wait_for(timeout=15000)

    def get_product_count(self) -> int:
        return self.product_name.count()

    def get_product_names(self) -> list:
        return self.product_name.all_text_contents()

    def get_product_prices(self) -> list:
        return self.product_price.all_text_contents()

    def view_product(self, product_id: int):
        self.page.locator(f"a[href='/product_details/{product_id}']").click()

    def search_product(self, keyword: str):
        self.search_input.fill(keyword)
        self.search_button.click()



