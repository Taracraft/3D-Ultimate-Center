/** A checked observation of byte equality, never permission to remove files. */
export type GalleryDuplicateGroup = Readonly<{
  sha256: string;
  size_bytes: number;
  paths: readonly string[];
  independent_copies: number;
  hardlink_aliases: number;
  redundant_content_bytes: number;
}>;

export type GalleryDuplicateReport = Readonly<{
  complete: true;
  scope: "byte_identical_models_in_folder";
  folder: string;
  recursive: true;
  read_only: true;
  files_examined: number;
  files_hashed: number;
  bytes_hashed: number;
  skipped_links: number;
  groups: readonly GalleryDuplicateGroup[];
  duplicate_groups: number;
  disk_space_savings_verified: false;
  deletion_authorized: false;
}>;

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : null;
}

function count(value: unknown, maximum = 20_000): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 && value <= maximum;
}

export function galleryRelativePath(value: unknown, allowRoot = false): value is string {
  if (typeof value !== "string" || value.length > 4096) return false;
  if (!value) return allowRoot;
  return !/[\\:\u0000-\u001f\u007f]/.test(value)
    && value.split("/").every((part) => part !== "" && part !== "." && part !== "..");
}

export function parseGalleryDuplicateReport(value: unknown, folder: string): GalleryDuplicateReport {
  const fail = (): never => { throw new Error("Die Duplikatprüfung hat keinen vollständigen, passenden Nachweis geliefert."); };
  const data = record(value);
  const maxBytes = 2 * 1024 ** 3;
  if (!galleryRelativePath(folder, true) || !data
      || data.complete !== true || data.read_only !== true || data.recursive !== true
      || data.scope !== "byte_identical_models_in_folder" || data.folder !== folder
      || data.disk_space_savings_verified !== false || data.deletion_authorized !== false
      || !count(data.files_examined) || !count(data.files_hashed)
      || data.files_hashed > data.files_examined || !count(data.bytes_hashed, maxBytes)
      || !count(data.skipped_links) || !count(data.duplicate_groups, 10_000)
      || !Array.isArray(data.groups) || data.groups.length !== data.duplicate_groups) return fail();
  const seen = new Set<string>();
  const groups: GalleryDuplicateGroup[] = [];
  let matchedBytes = 0;
  for (const raw of data.groups) {
    const group = record(raw);
    if (!group || typeof group.sha256 !== "string" || !/^[0-9a-f]{64}$/.test(group.sha256)
        || !count(group.size_bytes, maxBytes) || !Array.isArray(group.paths)
        || group.paths.length < 2 || group.paths.length > 20_000
        || !count(group.independent_copies) || group.independent_copies < 1
        || !count(group.hardlink_aliases)
        || group.independent_copies + group.hardlink_aliases !== group.paths.length
        || !count(group.redundant_content_bytes, maxBytes)
        || group.redundant_content_bytes !== (group.independent_copies - 1) * group.size_bytes) return fail();
    const paths: string[] = [];
    for (const name of group.paths) {
      if (!galleryRelativePath(name) || !/\.(stl|3mf|obj)$/i.test(name)
          || (folder && !name.startsWith(folder + "/")) || seen.has(name)) return fail();
      seen.add(name);
      if (seen.size > data.files_hashed) return fail();
      paths.push(name);
    }
    matchedBytes += paths.length * group.size_bytes;
    if (matchedBytes > data.bytes_hashed) return fail();
    groups.push({ sha256: group.sha256, size_bytes: group.size_bytes, paths,
      independent_copies: group.independent_copies, hardlink_aliases: group.hardlink_aliases,
      redundant_content_bytes: group.redundant_content_bytes });
  }
  return { complete: true, scope: "byte_identical_models_in_folder", folder,
    recursive: true, read_only: true, files_examined: data.files_examined,
    files_hashed: data.files_hashed, bytes_hashed: data.bytes_hashed,
    skipped_links: data.skipped_links, groups, duplicate_groups: groups.length,
    disk_space_savings_verified: false, deletion_authorized: false };
}
