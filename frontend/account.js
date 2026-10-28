import { accessToken, login, logout, accountRequest, signIn } from "./auth.js";
import { normalizeCart } from "./cart.mjs";
const $ = (id) => document.getElementById(id);
let mode = new URLSearchParams(location.search).get("mode") === "signup" ? "signup" : "signin";
let working = false;
const isLocal = window.SHOP_CONFIG.mode === "local";
const returnTo =
  new URLSearchParams(location.search).get("return") === "orders" ? "/orders.html" : "/#catalogue";
function notice(text, error = false) {
  $("auth-message").hidden = false;
  $("auth-message").className = error ? "notice error" : "notice success";
  $("auth-message").textContent = text;
}
function setMode(next) {
  mode = next;
  $("auth-message").hidden = true;
  const signup = mode === "signup";
  const confirm = mode === "confirm";
  $("account-title").textContent = confirm
    ? "Vérifiez votre e-mail."
    : signup
      ? "La magie commence ici."
      : "Heureux de vous revoir.";
  $("account-intro").textContent = confirm
    ? "Saisissez le code à 6 chiffres reçu par e-mail pour activer votre compte."
    : signup
      ? "Créez votre compte pour préparer votre prochaine nuit."
      : "Entrez dans votre petit monde d’Halloween.";
  $("password-field").hidden = confirm;
  $("password").required = !confirm;
  $("password").minLength = signup ? 12 : 1;
  $("password").autocomplete = signup ? "new-password" : "current-password";
  $("password-help").hidden = !signup;
  $("confirmation-field").hidden = !signup;
  $("password-confirm").required = signup;
  $("code-field").hidden = !confirm;
  $("verification-code").required = confirm;
  $("resend-code").hidden = !confirm || isLocal;
  $("auth-submit").textContent = confirm
    ? "Vérifier mon compte →"
    : signup
      ? "Créer mon compte →"
      : "Se connecter →";
  for (const [id, selected] of [
    ["signin-tab", !signup],
    ["signup-tab", signup],
  ]) {
    $(id).classList.toggle("active", selected);
    $(id).setAttribute("aria-pressed", String(selected));
  }
  $("password").value = "";
  $("password-confirm").value = "";
  $("verification-code").value = "";
}
function setWorking(value) {
  working = value;
  for (const control of document.querySelectorAll(".account-card button")) control.disabled = value;
}
$("signin-tab").onclick = () => setMode("signin");
$("signup-tab").onclick = () => setMode("signup");
$("toggle-password").onclick = () => {
  const show = $("password").type === "password";
  $("password").type = show ? "text" : "password";
  $("toggle-password").textContent = show ? "Masquer" : "Voir";
  $("toggle-password").setAttribute(
    "aria-label",
    show ? "Masquer le mot de passe" : "Afficher le mot de passe",
  );
  $("toggle-password").setAttribute("aria-pressed", String(show));
};
$("account-form").onsubmit = async (event) => {
  event.preventDefault();
  if (working) return;
  const email = $("email").value.trim();
  const password = $("password").value;
  if (mode === "signup" && password !== $("password-confirm").value) {
    notice("Les deux mots de passe doivent être identiques.", true);
    return;
  }
  if (
    mode === "signup" &&
    !/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{12,}$/.test(password)
  ) {
    notice(
      "Choisissez au moins 12 caractères, avec majuscule, minuscule, chiffre et symbole.",
      true,
    );
    return;
  }
  setWorking(true);
  notice("Un instant, la magie opère…");
  try {
    if (mode === "signup") {
      const result = await accountRequest("SignUp", {
        Username: email,
        Password: password,
        UserAttributes: [{ Name: "email", Value: email }],
      });
      setMode(result.UserConfirmed ? "signin" : "confirm");
      notice(
        result.UserConfirmed
          ? "Compte créé. Vous pouvez vous connecter."
          : "Un code de vérification vous a été envoyé par e-mail.",
      );
    } else if (mode === "confirm") {
      await accountRequest("ConfirmSignUp", {
        Username: email,
        ConfirmationCode: $("verification-code").value.trim(),
      });
      setMode("signin");
      notice("Votre compte est activé. Connectez-vous pour continuer.");
    } else {
      await signIn(email, password);
      location.assign(returnTo);
    }
  } catch (error) {
    if (error.code === "UserNotConfirmedException") setMode("confirm");
    notice(
      error.name === "TimeoutError" || error instanceof TypeError
        ? "Connexion au service impossible. Réessayez dans quelques instants."
        : error.message,
      true,
    );
  } finally {
    setWorking(false);
  }
};
$("resend-code").onclick = async () => {
  if (!$("email").reportValidity()) return;
  setWorking(true);
  try {
    await accountRequest("ResendConfirmationCode", { Username: $("email").value.trim() });
    notice("Un nouveau code vous a été envoyé.");
  } catch (error) {
    notice(error.message, true);
  } finally {
    setWorking(false);
  }
};
$("demo-login").onclick = async () => {
  await login();
  location.assign(returnTo);
};
$("hosted-login").onclick = async () => {
  try {
    await login();
  } catch (error) {
    notice(error.message, true);
  }
};
$("login").onclick = async () => {
  if (accessToken()) {
    try {
      await logout();
      location.assign("/account.html");
    } catch (error) {
      notice(error.message, true);
    }
  } else setMode("signin");
};
$("login").textContent = accessToken() ? "Se déconnecter" : "Mon compte";
try {
  $("cart-count").textContent = normalizeCart(
    JSON.parse(localStorage.getItem("minuit-cart")),
  ).reduce((sum, item) => sum + item.quantity, 0);
} catch {
  /* Empty basket. */
}
setMode(mode);
$("local-account-note").hidden = !isLocal;
$("hosted-login").hidden = isLocal;
$("account-form").hidden = false;
