# Website photos

| File | Used for | Shape | Recommended size |
| ---- | -------- | ----- | ---------------- |
| `hero` | home page, top | 4:5 (arched) | 1200 × 1500 |
| `treatment` | home page, wide | 21:9 | 2400 × 1030 |
| `reception` | about page | 4:3 | 1200 × 900 |
| dentist portraits | dentist profiles | 4:5 (arched) | 1000 × 1250 |

Page photos are set in `src/lib/photos.ts`; a dentist's portrait is set in
the Django admin (Dentist → Photo, e.g. `/photos/dentists/arta.jpg`).

Everything in `demo/` consists of **demo images**, always shown with a
"Demo photo" label. Put the clinic's own photos outside `demo/` (e.g.
`photos/dentists/`) and point to them. Use real photos of the clinic and
team, with the consent of everyone shown.
