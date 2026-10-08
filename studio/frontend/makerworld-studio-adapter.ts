import {
  MakerWorldApi,
  type MakerWorldBrowseResult,
  type MakerWorldInstance,
  type MakerWorldSavedItem,
} from "./makerworld-api.js";

export class MakerWorldStudioAdapter extends MakerWorldApi {
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
