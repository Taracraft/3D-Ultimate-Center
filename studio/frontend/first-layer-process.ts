import { firstLayerParameters } from "./primitive-geometry.js";
import type { SliceProcessOverrides } from "./plate-slice-api.js";

/** A single physical layer; material temperatures stay with the selected filament. */
export function firstLayerProcessOptions(nozzle: number, current: SliceProcessOverrides): SliceProcessOverrides {
  const { height, lineWidth } = firstLayerParameters(nozzle);
  return {
    ...current,
    layer_height_mm: height,
    first_layer_height_mm: height,
    initial_layer_line_width_mm: lineWidth,
    line_width_mm: lineWidth,
    outer_wall_line_width_mm: lineWidth,
    inner_wall_line_width_mm: lineWidth,
    infill_direction_deg: 135,
    initial_layer_speed_mm_s: 25,
    initial_layer_infill_speed_mm_s: 30,
    adhesion_mode: "none",
    support_mode: "off",
    walls: 1,
    bottom_shell_layers: 1,
    top_shell_layers: 0,
    // One bottom layer fills only the sparse diagnostic geometry. The model
    // height equals this first layer; mesh caps are not extra printed layers.
    infill_percent: 0,
    layer_height_ranges: [],
  };
}
