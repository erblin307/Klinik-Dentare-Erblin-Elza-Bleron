import assert from "node:assert/strict";
import { test } from "node:test";

import { PHOTOS, isDemoPhoto } from "./photos.ts";

test("only images in /photos/demo/ count as demo photos", () => {
  assert.ok(isDemoPhoto("/photos/demo/dentist-1.jpg"));
  assert.ok(!isDemoPhoto("/photos/dentists/arta.jpg"));
  assert.ok(!isDemoPhoto("/photos/demo.jpg"));
});

test("the bundled page photos are labelled as demo images", () => {
  for (const { src } of Object.values(PHOTOS)) {
    if (src) assert.ok(isDemoPhoto(src), src);
  }
});
