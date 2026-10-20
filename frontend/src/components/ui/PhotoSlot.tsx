import Image from "next/image";

import { PHOTOS, type PhotoSlot as Slot } from "@/lib/photos";

import { Icon } from "./Icon";

type Props = {
  slot: Slot;
  alt: string;
  placeholderLabel: string;
  className?: string;
  sizes: string;
  priority?: boolean;
};

/** The clinic's own photo, or a clearly labelled placeholder until one is added. */
export function PhotoSlot({ slot, alt, placeholderLabel, className = "", sizes, priority = false }: Props) {
  const photo = PHOTOS[slot];
  if (photo.src) {
    return (
      <div className={`relative overflow-hidden bg-sand ${className}`}>
        <Image src={photo.src} alt={alt} fill sizes={sizes} priority={priority} className="object-cover" />
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
