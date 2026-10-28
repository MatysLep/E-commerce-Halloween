const config = window.SHOP_CONFIG;
const sessionKey = "minuit-session";
const flowKey = "minuit-login";

function base64url(bytes) {
  return btoa(String.fromCharCode(...bytes))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

export function accessToken() {
  try {
    const session = JSON.parse(sessionStorage.getItem(sessionKey));
    if (session?.expiresAt > Date.now() + 10000) return session.token;
  } catch {
    /* A malformed or missing browser session is treated as signed out. */
  }
  sessionStorage.removeItem(sessionKey);
  return null;
}

export async function login() {
  if (config.mode === "local") {
    sessionStorage.setItem(
      sessionKey,
      JSON.stringify({ token: "local-demo", expiresAt: Date.now() + 3600000 }),
    );
    return;
  }
  const verifier = base64url(crypto.getRandomValues(new Uint8Array(32)));
  const state = base64url(crypto.getRandomValues(new Uint8Array(24)));
  const challenge = base64url(
    new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))),
  );
  sessionStorage.setItem(flowKey, JSON.stringify({ verifier, state, at: Date.now() }));
  const parameters = new URLSearchParams({
    client_id: config.clientId,
    response_type: "code",
    redirect_uri: `${location.origin}/`,
    scope: "openid email aws.cognito.signin.user.admin",
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
  });
  location.assign(`${config.cognitoDomain}/oauth2/authorize?${parameters}`);
}

export async function finishLogin() {
  const parameters = new URLSearchParams(location.search);
  if (!parameters.has("code") && !parameters.has("error")) return;
  history.replaceState({}, "", "/");
  const flow = JSON.parse(sessionStorage.getItem(flowKey) || "null");
  sessionStorage.removeItem(flowKey);
  if (!flow || parameters.get("state") !== flow.state || Date.now() - flow.at > 600000) {
    throw new Error("La connexion a expiré. Veuillez recommencer.");
  }
  if (parameters.has("error")) throw new Error("La connexion n’a pas été terminée.");
  const response = await fetch(`${config.cognitoDomain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: config.clientId,
      code: parameters.get("code"),
      redirect_uri: `${location.origin}/`,
      code_verifier: flow.verifier,
    }),
  });
  if (!response.ok) throw new Error("Impossible de terminer la connexion. Veuillez réessayer.");
  const tokens = await response.json();
  sessionStorage.setItem(
    sessionKey,
    JSON.stringify({
      token: tokens.access_token,
      expiresAt: Date.now() + tokens.expires_in * 1000,
    }),
  );
}

export function logout() {
  sessionStorage.removeItem(sessionKey);
  if (config.mode !== "local") {
    location.assign(
      `${config.cognitoDomain}/logout?${new URLSearchParams({ client_id: config.clientId, logout_uri: `${location.origin}/` })}`,
    );
  }
}
