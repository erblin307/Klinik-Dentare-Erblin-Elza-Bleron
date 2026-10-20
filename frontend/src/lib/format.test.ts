import assert from "node:assert/strict";
import { test } from "node:test";

import { clinicDate, clinicWeekday, formatDate, formatPrice, formatTime, initials, interpolate, weekdayName } from "./format.ts";

test("weekdays use the backend numbering (Monday = 0) in every language", () => {
  assert.equal(weekdayName(0, "en"), "Monday");
  assert.equal(weekdayName(6, "de"), "Sonntag");
  assert.equal(weekdayName(0, "sq").toLowerCase(), "e hënë");
});

test("times are shown in the clinic's time zone, not the visitor's", () => {
  const iso = "2030-01-07T09:00:00+01:00"; // 08:00 UTC
  assert.equal(formatTime(iso, "en", "Europe/Tirane"), "09:00");
  assert.equal(formatTime(iso, "de", "UTC"), "08:00");
  assert.equal(formatTime(iso, "en", "America/New_York"), "03:00");
});

test("dates are localised", () => {
  assert.equal(formatDate("2030-01-07", "en", "Europe/Tirane"), "Monday, 7 January 2030");
  assert.equal(formatDate("2030-01-07", "sq", "Europe/Tirane"), "e hënë, 7 janar 2030");
  assert.equal(formatDate("2030-01-07", "de", "Europe/Tirane"), "Montag, 7. Januar 2030");
  assert.match(formatDate("2030-01-07T23:30:00Z", "en", "Europe/Tirane"), /Tuesday, 8 January/);
});

test("prices use the clinic's currency, or null when priced after consultation", () => {
  assert.equal(formatPrice("45.00", "EUR", "de"), "45\u00a0€"); // non-breaking space
  assert.equal(formatPrice("45.50", "EUR", "en"), "€45.50");
  assert.equal(formatPrice(null, "EUR", "en"), null);
});

test("clinic calendar date and weekday follow the clinic's time zone", () => {
  const now = new Date("2030-01-06T23:30:00Z"); // Sunday in UTC, Monday in Tirane
  assert.equal(clinicDate("Europe/Tirane", 0, now), "2030-01-07");
  assert.equal(clinicDate("UTC", 0, now), "2030-01-06");
  assert.equal(clinicDate("Europe/Tirane", 1, now), "2030-01-08");
  assert.equal(clinicWeekday("Europe/Tirane", now), 0);
  assert.equal(clinicWeekday("UTC", now), 6);
});

test("initials and interpolation", () => {
  assert.equal(initials("Dr. Arta Krasniqi"), "AK");
  assert.equal(initials("Elza"), "E");
  assert.equal(interpolate("Hello {name}, {missing}", { name: "Ana" }), "Hello Ana, {missing}");
});
