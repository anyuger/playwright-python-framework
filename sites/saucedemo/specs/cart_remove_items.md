# Cart: removing items

Site: saucedemo.com, logged in as `standard_user`.

## Acceptance criteria

- AC-1: With one item ("Sauce Labs Backpack") in the cart, removing it on the cart page leaves the cart with 0 items.
- AC-2: With two items ("Sauce Labs Backpack" and "Sauce Labs Bike Light") in the cart, removing the backpack on the cart page leaves only "Sauce Labs Bike Light".
- AC-3: After the only item in the cart is removed, the cart badge is no longer shown.

## Notes

On the cart page each item has a "Remove" button with `data-test="remove-<item-name-in-kebab-case>"`,
for example `remove-sauce-labs-backpack`.
