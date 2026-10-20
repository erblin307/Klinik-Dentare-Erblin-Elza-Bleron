import Image from "next/image";

import { PHOTOS, type PhotoSlot as Slot } from "@/lib/photos";

import { Icon } from "./Icon";

type Props = {
  slot: Slot;
  alt: string;
  placeholderLabel: string;
  demoLabel: string;
  className?: string;
  sizes: string;
  priority?: boolean;
};

/** A photo (labelled when it is a demo image), or a labelled placeholder. */
export function PhotoSlot({ slot, alt, placeholderLabel, demoLabel, className = "", sizes, priority = false }: Props) {
  const photo = PHOTOS[slot];
  if (photo.src) {
    return (
      <div className={`relative overflow-hidden bg-sand ${className}`}>
        <Image src={photo.src} alt={alt} fill sizes={sizes} priority={priority} className="object-cover" />
        {photo.demo && (
          <span className="absolute bottom-3 left-3 rounded-full bg-ivory/90 px-3 py-1 text-[11px] font-medium tracking-wide text-ink">
            {demoLabel}
          </span>
        )}
      </div>
    );
  }
  return (
    <div
      role="img"
      aria-label={placeholderLabel}
      className={`hatch relative flex items-end overflow-hidden bg-sand ${className}`}
    >
      <span className="m-4 inline-flex items-center gap-2 rounded-full bg-ivory/90 px-3 py-1.5 text-xs text-muted">
        <Icon name="camera" className="h-4 w-4" />
        {placeholderLabel}
      </span>
    </div>
  );
}
