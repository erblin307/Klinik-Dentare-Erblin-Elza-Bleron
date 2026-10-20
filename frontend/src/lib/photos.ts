// Website photography (files in public/photos/). Anything in /photos/demo/ is
// not a photo of the clinic itself and is always shown with a visible
// "Demo photo" label. With `src: null` a labelled placeholder is shown.

export type PhotoSlot = "hero" | "treatment" | "reception";

export const PHOTOS: Record<PhotoSlot, { src: string | null }> = {
  hero: { src: "/photos/demo/hero.jpg" },
  treatment: { src: "/photos/demo/treatment.jpg" },
  reception: { src: "/photos/demo/reception.jpg" },
};

export function isDemoPhoto(src: string): boolean {
  return src.startsWith("/photos/demo/");
}
