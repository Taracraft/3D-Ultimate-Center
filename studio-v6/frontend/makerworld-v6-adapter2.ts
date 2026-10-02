import {
  MakerWorldApi,
  type MakerWorldBrowseResult,
  type MakerWorldDetail,
  type MakerWorldInstance,
  type MakerWorldSavedItem,
} from "./makerworld-api.js";

export class MakerWorldV6Adapter2 {
  readonly #api = new MakerWorldApi();

  browse(terms: readonly string[], navKey: string, offset: number, limit: number): Promise<MakerWorldBrowseResult> {
    return this.#api.browse(terms, navKey, offset, limit);
  }

  detail(designId: string): Promise<MakerWorldDetail> {
    return this.#api.detail(designId);
  }

  download(instance: MakerWorldInstance, format: "3mf" | "stl", fallbackName: string): Promise<File> {
    return this.#api.downloadInstance(instance.id, format, fallbackName);
  }

  save(instance: MakerWorldInstance, folder: string, filename: string, overwrite = false): Promise<MakerWorldSavedItem> {
    return this.#api.saveInstance(instance.id, folder, filename, overwrite);
  }
}