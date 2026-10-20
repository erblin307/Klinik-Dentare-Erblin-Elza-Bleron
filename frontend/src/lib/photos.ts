// Clinic photography. Photos live in public/photos/. Images that are not
// photos of the clinic itself must keep `demo: true`, which shows a visible
// "Demo photo" label. With `src: null` a labelled placeholder is shown.

export type PhotoSlot = "hero" | "treatment" | "reception";

export const PHOTOS: Record<PhotoSlot, { src: string | null; demo: boolean }> = {
  hero: { src: "/photos/hero.jpg", demo: true },
  treatment: { src: "/photos/treatment.jpg", demo: true },
  reception: { src: "/photos/reception.jpg", demo: true },
};
