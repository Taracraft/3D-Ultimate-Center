export type GallerySortMode = "name" | "newest" | "size";
export type GalleryViewMode = "grid" | "list";

type SortableGalleryItem = Readonly<{
  kind: "folder" | "model";
  name: string;
  modified?: number | string;
  size_bytes?: number;
}>;

export function sortGalleryItems<T extends SortableGalleryItem>(
  items: readonly T[],
  mode: GallerySortMode,
): T[] {
  return [...items].sort((left, right) => {
    if (left.kind !== right.kind) return left.kind === "folder" ? -1 : 1;
    if (mode === "newest") return Number(right.modified ?? 0) - Number(left.modified ?? 0);
    if (mode === "size") return Number(right.size_bytes ?? 0) - Number(left.size_bytes ?? 0);
    return left.name.localeCompare(right.name, "de", { sensitivity: "base" });
  });
}
