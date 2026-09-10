import test from "node:test";
import assert from "node:assert/strict";
import { SIGN_IN_STATE, signInState } from "../src/signInState.js";

const shop = "acme.myshopify.com";

test("connected is not signed in", () => {
  // The trap: a store stays connected long after a session expires. Only the
  // session decides whether this browser can load anything.
  const view = signInState({ session: { authenticated: false }, viewingShop: shop, checked: true });
  assert.equal(view.state, SIGN_IN_STATE.signedOut);
  assert.equal(view.needsSignIn, true);
  assert.match(view.message, /Sign in with Shopify/);
});

test("a failed session lookup is signed out, not assumed fine", () => {
  const view = signInState({ session: null, viewingShop: shop, checked: true });
  assert.equal(view.needsSignIn, true);
});

test("signed in to a different store gets its own message", () => {
  const view = signInState({
    session: { authenticated: true, shopDomain: "other.myshopify.com" },
    viewingShop: shop, checked: true,
  });
  assert.equal(view.state, SIGN_IN_STATE.wrongShop);
  assert.equal(view.needsSignIn, true);
  assert.match(view.message, /different store/);
});

test("nothing is claimed before the check completes", () => {
  const view = signInState({ session: null, viewingShop: shop, checked: false });
  assert.equal(view.state, SIGN_IN_STATE.checking);
  assert.equal(view.needsSignIn, false, "no sign-in prompt flashes while we do not know");
});

test("a matching session is signed in", () => {
  const view = signInState({
    session: { authenticated: true, shopDomain: shop }, viewingShop: shop, checked: true,
  });
  assert.equal(view.state, SIGN_IN_STATE.signedIn);
  assert.equal(view.needsSignIn, false);
});
