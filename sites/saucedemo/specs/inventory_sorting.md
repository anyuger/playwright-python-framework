# Inventory: sorting products

Site: saucedemo.com, logged in as `standard_user`, on the inventory page.

## Acceptance criteria

- AC-1: Choosing "Price (low to high)" lists the products by price ascending: the first product is "Sauce Labs Onesie" ($7.99) and the last is "Sauce Labs Fleece Jacket" ($49.99).
- AC-2: Choosing "Price (high to low)" lists the products by price descending: the first product is "Sauce Labs Fleece Jacket" ($49.99) and the last is "Sauce Labs Onesie" ($7.99).
- AC-3: Choosing "Name (Z to A)" lists the products by name descending: the first product is "Test.allTheThings() T-Shirt (Red)" and the last is "Sauce Labs Backpack".

## Notes

The sort dropdown has `data-test="product-sort-container"`, with option values `az`, `za`, `lohi` and `hilo`.
Each product's name has `data-test="inventory-item-name"` and its price `data-test="inventory-item-price"` (text like `$7.99`).
