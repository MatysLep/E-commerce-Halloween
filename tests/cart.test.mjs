import test from "node:test";
import assert from "node:assert/strict";
import { normalizeCart, cartTotal, requestKey } from "../frontend/cart.mjs";

test("malformed browser storage cannot introduce invalid quantities", () => {
  assert.deepEqual(normalizeCart(null), []);
  assert.deepEqual(
    normalizeCart([
      { product_id: "a", quantity: -1 },
      { product_id: "b", quantity: 25 },
    ]),
    [{ product_id: "b", quantity: 20 }],
  );
});

test("cart totals use integer cents and combine repeated products", () => {
  const cart = normalizeCart([
    { product_id: "a", quantity: 1 },
    { product_id: "a", quantity: 2 },
  ]);
  assert.equal(cartTotal(cart, [{ id: "a", price_cents: 890 }]), 2670);
});

test("retry after a lost HTTP response preserves the idempotency key", () => {
  const cart = [{ product_id: "a", quantity: 1 }];
  const pending = requestKey(cart, null, () => "first");
  assert.equal(requestKey(cart, pending, () => "second").key, "first");
  assert.equal(
    requestKey([{ product_id: "a", quantity: 2 }], pending, () => "second").key,
    "second",
  );
});
