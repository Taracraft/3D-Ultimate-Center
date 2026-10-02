import {
  MakerWorldApi,
  type MakerWorldBrowseResult,
  type MakerWorldInstance,
  type MakerWorldSavedItem,
} from "./makerworld-api.js";

declare module "./makerworld-api.js" {
  interface MakerWorldApi {
    browse(terms: readonly string[], navKey?: string, offset?: number, limit?: number): Promise<MakerWorldBrowseResult>;
    downloadInstance(instance: MakerWorldInstance, format: "3mf" | "stl", fallbackName: string): Promise<File>;
    saveInstance(instance: MakerWorldInstance, folder: string, filename: string, overwrite?: boolean): Promise<MakerWorldSavedItem>;
  }
}

export class MakerWorldV6Adapter extends MakerWorldApi {
  override browse(
    queryOrTerms: string | readonly string[] = [],
    navKey = "Trending",
    offset = 0,
    limit = 24,
  ): Promise<MakerWorldBrowseResult> {
    const query = typeof queryOrTerms === "string" ? queryOrTerms : queryOrTerms.join(" ");
    return super.browse(query, navKey, offset, limit);
  }

  override downloadInstance(
    instanceOrId: MakerWorldInstance | string,
    format: "3mf" | "stl",
    fallbackName: string,
  ): Promise<File> {
    const id = typeof instanceOrId === "string" ? instanceOrId : instanceOrId.id;
    return super.downloadInstance(id, format, fallbackName);
  }

  override saveInstance(
    instanceOrId: MakerWorldInstance | string,
    folder: string,
    filename: string,
    overwrite = false,
  ): Promise<MakerWorldSavedItem> {
    const id = typeof instanceOrId === "string" ? instanceOrId : instanceOrId.id;
    return super.saveInstance(id, folder, filename, overwrite);
  }
}