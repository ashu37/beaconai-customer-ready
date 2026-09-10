import test from "node:test";
import assert from "node:assert/strict";
import { buildCampaignFromSelection } from "../src/campaignDraft.js";

const play = { id: "play-1", play_id: "play-1", play_name: "Winback", audience_size: 120 };
const template = { id: "tpl-1", name: "Winback", source: "beacon", subject: "S", previewText: "P", bodyH2: "H", bodyP1: "B", cta: "Shop" };

test("the merchant's destination is carried into the draft", () => {
  // The reported bug: the destination lived in its own state and never reached
  // the object the preview and the handoff render from, so a merchant could type
  // one and still get the shop default — or a missing-link error — in the email.
  const draft = buildCampaignFromSelection(play, template, {}, null, "https://shop.example/collections/restock");
  assert.equal(draft.destinationUrl, "https://shop.example/collections/restock");
});

test("no destination is null, not an empty string", () => {
  // The renderer distinguishes "nothing set" (fall back to the shop default, or
  // refuse) from a value. An empty string would read as a set-but-blank link.
  assert.equal(buildCampaignFromSelection(play, template).destinationUrl, null);
  assert.equal(buildCampaignFromSelection(play, template, {}, null, "").destinationUrl, null);
});

test("copy edits cannot overwrite the destination with a stale one", () => {
  // `edits` is spread over the base draft, so an old destinationUrl left in the
  // edits blob would win over the current field. It must not.
  const draft = buildCampaignFromSelection(
    play, template,
    { subject: "Edited", destinationUrl: "https://stale.example/" },
    null,
    "https://current.example/"
  );
  assert.equal(draft.subject, "Edited", "copy edits still apply");
  assert.equal(draft.destinationUrl, "https://current.example/");
});

test("merchant edits layer over template copy", () => {
  const draft = buildCampaignFromSelection(play, template, { subject: "Mine", bodyP2: "" }, null, "https://x.example/");
  assert.equal(draft.subject, "Mine");
  assert.equal(draft.bodyP2, "", "a deleted support paragraph stays deleted");
});

test("no play or no template means no draft", () => {
  assert.equal(buildCampaignFromSelection(null, template), null);
  assert.equal(buildCampaignFromSelection(play, null), null);
});
