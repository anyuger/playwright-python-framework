from sites.automationexercise.pages.products_page import ProductsPage


class TestProducts:

    def test_products_page_loads(self, page):
        products_page = ProductsPage(page)
        products_page.navigate()
        assert page.url == ProductsPage.URL
        assert products_page.get_product_count() > 0

    def test_search_product(self, page):
        products_page = ProductsPage(page)
        products_page.navigate()
        products_page.search_product('frozen')
        names = products_page.get_product_names()
        assert all('frozen' in name.lower() for name in names)

    def test_product_prices_displayed(self, page):
        products_page = ProductsPage(page)
        products_page.navigate()
        prices = products_page.get_product_prices()
        assert all('Rs.' in price for price in prices)
