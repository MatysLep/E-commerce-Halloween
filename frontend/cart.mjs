export function normalizeCart(cart) {
  if (!Array.isArray(cart)) return [];
  const quantities = new Map();
  for (const item of cart.slice(0, 50)) {
    if (
      typeof item?.product_id !== "string" ||
      !Number.isInteger(item.quantity) ||
      item.quantity < 1
    )
      continue;
    quantities.set(
      item.product_id,
      Math.min(20, (quantities.get(item.product_id) || 0) + item.quantity),
    );
  }
  return [...quantities].map(([product_id, quantity]) => ({ product_id, quantity }));
}

export function cartTotal(cart, products) {
  return cart.reduce((sum, item) => {
    const product = products.find((row) => row.id === item.product_id);
    return sum + (product?.price_cents || 0) * item.quantity;
  }, 0);
}

export function requestKey(cart, pending, generate = () => crypto.randomUUID()) {
  const fingerprint = JSON.stringify(
    [...cart].sort((a, b) => a.product_id.localeCompare(b.product_id)),
  );
  return pending?.fingerprint === fingerprint ? pending : { fingerprint, key: generate() };
}
