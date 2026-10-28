import { accessToken, finishLogin, login, logout } from "./auth.js";
import { cartTotal, normalizeCart, requestKey } from "./cart.mjs";

const $ = (id) => document.getElementById(id);
const money = (cents) =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(cents / 100);
const labels = { CONFIRMED: "Confirmée", PACKED: "Emballée", SHIPPED: "Expédiée" };
const eventLabels = {
  CommandeCreee: "Commande confirmée",
  EmballageTermine: "Emballage terminé",
  ExpeditionTerminee: "Expédition simulée",
};
let products = [];
let category = "Tout";
let cart;
let pending;
try {
  cart = normalizeCart(JSON.parse(localStorage.getItem("minuit-cart")));
  pending = JSON.parse(localStorage.getItem("minuit-pending"));
} catch {
  cart = [];
  pending = null;
}
let busy = false;
let orderLimit = 20;
let refreshTimer;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function message(text, error = false) {
  const node = $("message");
  node.hidden = false;
  node.className = error ? "notice error" : "notice success";
  node.textContent = text;
  node.focus({ preventScroll: true });
}

async function api(path, options = {}) {
  const token = accessToken();
  const response = await fetch(`${window.SHOP_CONFIG.apiBase}${path}`, {
    ...options,
    signal: AbortSignal.timeout(15000),
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  const body = await response.json();
  if (!response.ok)
    throw new Error(typeof body.detail === "string" ? body.detail : "Une erreur est survenue.");
  return body;
}

function saveCart() {
  localStorage.setItem("minuit-cart", JSON.stringify(cart));
  renderCart();
  renderProducts();
}

function changeQuantity(productId, difference) {
  if (busy) return;
  const product = products.find((row) => row.id === productId);
  const current = cart.find((item) => item.product_id === productId);
  const next = (current?.quantity || 0) + difference;
  if (next > Math.min(product?.stock || 0, 20)) return;
  cart = cart.filter((item) => item.product_id !== productId);
  if (next > 0) cart.push({ product_id: productId, quantity: next });
  saveCart();
}

function renderFilters() {
  $("filters").replaceChildren();
  for (const value of ["Tout", ...new Set(products.map((product) => product.category))]) {
    const button = element("button", value === category ? "filter active" : "filter", value);
    button.setAttribute("aria-pressed", String(value === category));
    button.onclick = () => {
      category = value;
      renderFilters();
      renderProducts();
    };
    $("filters").append(button);
  }
}

function renderProducts() {
  $("products").replaceChildren();
  const visible = products.filter(
    (product) => category === "Tout" || product.category === category,
  );
  $("product-count").textContent = `${visible.length} curiosités à découvrir`;
  for (const [index, product] of visible.entries()) {
    const card = element("article", "product-card");
    const art = element("div", `product-art tint-${index % 3}`, product.emoji);
    art.setAttribute("aria-hidden", "true");
    const info = element("div", "product-info");
    info.append(
      element("p", "eyebrow", product.category),
      element("h3", "", product.name),
      element("p", "product-description", product.description),
    );
    const row = element("div", "product-bottom");
    const inCart = cart.find((item) => item.product_id === product.id)?.quantity || 0;
    const button = element("button", "add-button", product.stock ? "+" : "—");
    button.setAttribute("aria-label", `Ajouter ${product.name} au panier`);
    button.disabled = busy || inCart >= Math.min(product.stock, 20);
    button.onclick = () => changeQuantity(product.id, 1);
    row.append(
      element("strong", "price", money(product.price_cents)),
      element("span", "stock", product.stock ? `${product.stock} disponibles` : "Épuisé"),
      button,
    );
    info.append(row);
    card.append(art, info);
    $("products").append(card);
  }
}

function renderCart() {
  $("cart-count").textContent = cart.reduce((count, item) => count + item.quantity, 0);
  $("cart-total").textContent = money(cartTotal(cart, products));
  $("cart-items").replaceChildren();
  if (!cart.length)
    $("cart-items").append(
      element("p", "empty-cart", "Votre panier attend ses premières trouvailles."),
    );
  for (const item of cart) {
    const product = products.find((row) => row.id === item.product_id);
    const row = element("div", "cart-row");
    row.append(element("span", "", product?.name || "Produit indisponible"));
    const controls = element("div", "quantity");
    for (const [label, delta] of [
      ["−", -1],
      ["+", 1],
    ]) {
      const button = element("button", "", label);
      button.setAttribute(
        "aria-label",
        `${delta === 1 ? "Augmenter" : "Diminuer"} la quantité de ${product?.name || item.product_id}`,
      );
      button.disabled = busy || (delta === 1 && item.quantity >= Math.min(product?.stock || 0, 20));
      button.onclick = () => changeQuantity(item.product_id, delta);
      controls.append(button);
      if (delta === -1) controls.append(element("span", "", item.quantity));
    }
    row.append(controls);
    $("cart-items").append(row);
  }
  $("checkout").disabled = busy || !cart.length;
  $("checkout").textContent = busy ? "Confirmation en cours…" : "Confirmer ma commande →";
}

async function loadProducts() {
  products = await api("/api/products");
  renderFilters();
  renderProducts();
  renderCart();
}

async function showOrder(id) {
  try {
    const order = await api(`/api/orders/${encodeURIComponent(id)}`);
    const detail = $("order-detail");
    detail.replaceChildren(element("h2", "", `Commande ${id.slice(0, 8)}`));
    for (const line of order.lines)
      detail.append(
        element(
          "p",
          "",
          `${line.quantity} × ${line.name} — ${money(line.quantity * line.unit_price_cents)}`,
        ),
      );
    detail.append(element("strong", "", `Total : ${money(order.total_cents)}`));
    const history = element("ol", "history");
    for (const event of order.history)
      history.append(
        element(
          "li",
          "",
          `${eventLabels[event.type] || event.type} · ${new Date(event.at).toLocaleString("fr-FR")}`,
        ),
      );
    detail.append(history);
    $("order-dialog").showModal();
  } catch (error) {
    message(error.message, true);
  }
}

async function refreshOrders() {
  clearTimeout(refreshTimer);
  if (!accessToken()) {
    $("order-list").replaceChildren(
      element("p", "", "Connectez-vous pour retrouver vos commandes."),
    );
    $("more-orders").hidden = true;
    return;
  }
  try {
    const orders = await api(`/api/orders?limit=${orderLimit}`);
    $("order-list").replaceChildren();
    if (!orders.length)
      $("order-list").append(
        element(
          "p",
          "empty-orders",
          "Votre histoire avec Minuit commence avec votre première commande.",
        ),
      );
    for (const order of orders) {
      const row = element("div", "order-row");
      const detail = element("button", "text-button", `N° ${order.id.slice(0, 8)} ↗`);
      detail.onclick = () => showOrder(order.id);
      row.append(
        detail,
        element("span", "order-date", new Date(order.created_at).toLocaleString("fr-FR")),
        element("span", `badge ${order.status.toLowerCase()}`, labels[order.status]),
        element("strong", "", money(order.total_cents)),
      );
      $("order-list").append(row);
    }
    $("more-orders").hidden = orders.length < orderLimit || orderLimit >= 100;
    if (orders.some((order) => order.status !== "SHIPPED"))
      refreshTimer = setTimeout(refreshOrders, 5000);
  } catch (error) {
    message(error.message, true);
    refreshTimer = setTimeout(refreshOrders, 15000);
  }
}

$("checkout").onclick = async () => {
  if (!accessToken()) {
    message("Connectez-vous avant de confirmer votre commande.", true);
    return;
  }
  busy = true;
  renderCart();
  renderProducts();
  pending = requestKey(cart, pending);
  localStorage.setItem("minuit-pending", JSON.stringify(pending));
  try {
    const order = await api("/api/orders", {
      method: "POST",
      headers: { "Idempotency-Key": pending.key },
      body: JSON.stringify({ items: cart }),
    });
    cart = [];
    pending = null;
    localStorage.removeItem("minuit-pending");
    saveCart();
    message(
      `Merci ! Votre commande ${order.id.slice(0, 8)} est confirmée. Retrouvez son avancement ci-dessous.`,
    );
    await Promise.all([loadProducts(), refreshOrders()]);
  } catch (error) {
    message(
      `${error.message} Vous pouvez réessayer : un nouvel essai du même panier ne crée pas de doublon.`,
      true,
    );
  } finally {
    busy = false;
    renderCart();
    renderProducts();
  }
};

$("login").onclick = async () => {
  try {
    if (accessToken()) logout();
    else await login();
    $("login").textContent = accessToken() ? "Se déconnecter" : "Se connecter";
    await refreshOrders();
  } catch (error) {
    message(error.message, true);
  }
};
$("refresh-orders").onclick = refreshOrders;
$("more-orders").onclick = () => {
  orderLimit = Math.min(100, orderLimit + 20);
  refreshOrders();
};
$("close-dialog").onclick = () => $("order-dialog").close();

try {
  await finishLogin();
  $("login").textContent = accessToken()
    ? "Se déconnecter"
    : window.SHOP_CONFIG.mode === "local"
      ? "Compte démo"
      : "Se connecter";
  await Promise.all([loadProducts(), refreshOrders()]);
} catch (error) {
  message(error.message, true);
}
