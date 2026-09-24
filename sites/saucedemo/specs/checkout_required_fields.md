# Checkout: required customer fields

Site: saucedemo.com, logged in as `standard_user`, with "Sauce Labs Backpack" in the cart,
on the "Checkout: Your Information" step.

## Acceptance criteria

- AC-1: Continuing with first name and postal code filled but last name empty shows the error "Error: Last Name is required".
- AC-2: Continuing with first and last name filled but postal code empty shows the error "Error: Postal Code is required".
- AC-3: Continuing with all three fields filled moves the user to the checkout overview page (`/checkout-step-two.html`).
