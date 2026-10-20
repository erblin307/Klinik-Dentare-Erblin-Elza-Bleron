import { notFound } from "next/navigation";

// Unknown paths inside a language render the localised not-found page.
export default function CatchAll() {
  notFound();
}
