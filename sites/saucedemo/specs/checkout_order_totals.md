# Checkout: order totals

Site: saucedemo.com, logged in as `standard_user`, with only "Sauce Labs Backpack" ($29.99) in the cart.
The user completes "Checkout: Your Information" with any valid values and reaches the overview page.

## Acceptance criteria

- AC-1: The overview shows the item subtotal as "Item total: $29.99".
- AC-2: The overview shows tax as "Tax: $2.40".
- AC-3: The overview shows the order total as "Total: $32.39".

## Notes

The overview labels use `data-test="subtotal-label"`, `data-test="tax-label"` and `data-test="total-label"`.
