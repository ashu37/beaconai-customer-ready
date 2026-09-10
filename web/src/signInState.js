// Is this browser signed in to the store it is showing?
//
// Separate from "is the store connected", because conflating them is what left a
// merchant stranded: an integration stays connected long after a session
// expires, so the page reported "Connected", hid the Shopify action, and every
// protected request failed with no route back in.
//
// Connected describes the STORE. Signed in describes THIS BROWSER. Only the
// second decides whether the app can load anything.

export const SIGN_IN_STATE = {
  checking: "checking",
  signedIn: "signed_in",
  signedOut: "signed_out",
  wrongShop: "wrong_shop",
};

export const SIGN_IN_MESSAGE = {
  signedOut: "Your session has expired or this browser hasn't signed in yet. Sign in with Shopify to load your campaigns.",
  wrongShop: "You're signed in to a different store. Sign in with Shopify to switch to this one.",
};

/**
 * @param {object|null} session   the /session response, or null if it failed
 * @param {string} viewingShop    the shop the app is currently showing
 * @param {boolean} checked       whether the session lookup has completed
 */
export function signInState({ session, viewingShop, checked }) {
  if (!checked) return { state: SIGN_IN_STATE.checking, needsSignIn: false, message: null };

  if (!session?.authenticated) {
    return { state: SIGN_IN_STATE.signedOut, needsSignIn: true, message: SIGN_IN_MESSAGE.signedOut };
  }
  // Signed in, but to something else. Loading this shop's data would fail, and
  // "connected" would still be true — so it needs its own message.
  if (viewingShop && session.shopDomain !== viewingShop) {
    return { state: SIGN_IN_STATE.wrongShop, needsSignIn: true, message: SIGN_IN_MESSAGE.wrongShop };
  }
  return { state: SIGN_IN_STATE.signedIn, needsSignIn: false, message: null, shopDomain: session.shopDomain };
}
