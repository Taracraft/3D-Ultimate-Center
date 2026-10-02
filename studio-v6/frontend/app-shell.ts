import { Ultimate3DStudioShellV4 } from "./app-shell-v4.js";

if (!customElements.get("ultimate-3d-studio")) {
  customElements.define("ultimate-3d-studio", Ultimate3DStudioShellV4);
}
