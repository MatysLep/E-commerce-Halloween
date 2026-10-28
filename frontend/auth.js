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

export async function logout() {
  const token = accessToken();
  if (config.mode === "local" && token && token !== "local-demo") {
    const response = await fetch(`${config.apiBase}/api/auth/signout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) throw new Error("Impossible de fermer la session. Réessayez.");
  }
  sessionStorage.removeItem(sessionKey);
  if (config.mode !== "local") {
    location.assign(
      `${config.cognitoDomain}/logout?${new URLSearchParams({ client_id: config.clientId, logout_uri: `${location.origin}/` })}`,
    );
  }
}

// Public Cognito APIs: credentials go directly to Cognito over HTTPS.
export async function accountRequest(action, parameters) {
  if (config.mode === "local") {
    const actionPath = action === "SignUp" ? "signup" : "signin";
    const response = await fetch(`${config.apiBase}/api/auth/${actionPath}`, {
      method: "POST",
      signal: AbortSignal.timeout(15000),
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: parameters.Username || parameters.AuthParameters?.USERNAME,
        password: parameters.Password || parameters.AuthParameters?.PASSWORD,
      }),
    });
    const result = await response.json();
    if (!response.ok)
      throw new Error(
        typeof result.detail === "string"
          ? result.detail
          : "Vérifiez votre adresse e-mail et votre mot de passe.",
      );
    return action === "SignUp"
      ? { UserConfirmed: true }
      : {
          AuthenticationResult: { AccessToken: result.access_token, ExpiresIn: result.expires_in },
        };
  }
  const response = await fetch(
    `https://cognito-idp.${config.region || "eu-west-3"}.amazonaws.com/`,
    {
      method: "POST",
      signal: AbortSignal.timeout(15000),
      headers: {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": `AWSCognitoIdentityProviderService.${action}`,
      },
      body: JSON.stringify({ ClientId: config.clientId, ...parameters }),
    },
  );
  const body = await response.json();
  if (!response.ok) {
    const code = (body.__type || "").split("#").pop();
    const errors = {
      NotAuthorizedException: "Adresse e-mail ou mot de passe incorrect.",
      UserNotFoundException: "Adresse e-mail ou mot de passe incorrect.",
      UsernameExistsException: "Un compte existe déjà avec cette adresse e-mail.",
      InvalidPasswordException:
        "Le mot de passe doit contenir 12 caractères, une majuscule, une minuscule, un chiffre et un symbole.",
      CodeMismatchException: "Ce code est incorrect. Vérifiez l’e-mail reçu.",
      ExpiredCodeException: "Ce code a expiré. Demandez un nouveau code.",
      UserNotConfirmedException: "Votre adresse e-mail doit être vérifiée avant la connexion.",
      LimitExceededException: "Trop de tentatives. Réessayez dans quelques instants.",
      TooManyRequestsException: "Trop de tentatives. Réessayez dans quelques instants.",
    };
    const error = new Error(
      errors[code] || "Le service de compte est indisponible. Veuillez réessayer.",
    );
    error.code = code;
    throw error;
  }
  return body;
}

export async function signIn(email, password) {
  const result = await accountRequest("InitiateAuth", {
    AuthFlow: "USER_PASSWORD_AUTH",
    AuthParameters: { USERNAME: email, PASSWORD: password },
  });
  if (!result.AuthenticationResult)
    throw new Error(
      "Une vérification supplémentaire est requise. Utilisez l’autre méthode de connexion.",
    );
  sessionStorage.setItem(
    sessionKey,
    JSON.stringify({
      token: result.AuthenticationResult.AccessToken,
      expiresAt: Date.now() + result.AuthenticationResult.ExpiresIn * 1000,
    }),
  );
}
