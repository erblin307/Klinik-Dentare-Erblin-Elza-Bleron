import assert from "node:assert/strict";
import { test } from "node:test";

import de from "./de.ts";
import en from "./en.ts";
import sq from "./sq.ts";

type Tree = { [key: string]: string | Tree };

function leaves(tree: Tree, prefix = ""): Map<string, string> {
  const result = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") result.set(path, value);
    else for (const [p, v] of leaves(value, path)) result.set(p, v);
  }
  return result;
}

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");

test("all languages have the same texts with the same placeholders", () => {
  const reference = leaves(en as unknown as Tree);
  for (const [name, dictionary] of Object.entries({ sq, de })) {
    const texts = leaves(dictionary as unknown as Tree);
    assert.deepEqual([...texts.keys()].sort(), [...reference.keys()].sort(), name);
    for (const [path, text] of texts) {
      assert.ok(text.trim(), `${name}.${path} is empty`);
      assert.equal(placeholders(text), placeholders(reference.get(path)!), `${name}.${path} placeholders`);
    }
  }
});

test("decline words are ones the chat backend understands", () => {
  // backend/apps/chatbot/language.py: _NO_CORE
  assert.deepEqual([en.chat.declineWord, sq.chat.declineWord, de.chat.declineWord], ["no", "jo", "nein"]);
});
