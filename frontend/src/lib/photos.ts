// Clinic photography. Put the clinic's own photos in public/photos/ and set
// the paths here; until then the site shows labelled placeholders. Stock
// photos presented as "our clinic" would mislead patients, so none are bundled.

export type PhotoSlot = "hero" | "treatment" | "reception";

export const PHOTOS: Record<PhotoSlot, { src: string | null; width: number; height: number }> = {
  hero: { src: null, width: 1200, height: 1500 },
  treatment: { src: null, width: 1600, height: 1000 },
  reception: { src: null, width: 1200, height: 900 },
};
