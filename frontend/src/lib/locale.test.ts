import assert from "node:assert/strict";
import { test } from "node:test";

import { DEFAULT_LOCALE, isLocale, negotiateLocale } from "./locale.ts";

test("picks the best supported language from Accept-Language", () => {
  assert.equal(negotiateLocale("de-AT,de;q=0.9,en;q=0.5"), "de");
  assert.equal(negotiateLocale("fr-FR,fr;q=0.9,en-GB;q=0.8,sq;q=0.7"), "en");
  assert.equal(negotiateLocale("sq-XK"), "sq");
  assert.equal(negotiateLocale("en;q=0.2,de;q=0.8"), "de");
});

test("falls back to the default language", () => {
  assert.equal(negotiateLocale(null), DEFAULT_LOCALE);
  assert.equal(negotiateLocale("fr,it;q=0.5"), DEFAULT_LOCALE);
  assert.equal(negotiateLocale("de;q=0"), DEFAULT_LOCALE);
  assert.equal(negotiateLocale(";;;"), DEFAULT_LOCALE);
});

test("recognises supported locales only", () => {
  assert.ok(isLocale("sq") && isLocale("en") && isLocale("de"));
  assert.ok(!isLocale("fr") && !isLocale("EN") && !isLocale(""));
});
