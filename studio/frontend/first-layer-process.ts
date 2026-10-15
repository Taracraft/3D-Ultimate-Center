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
    // The solid bottom layer fills the whole sheet. Sparse grid infill does
    // not support 100 percent in Bambu Studio and is unnecessary here.
    infill_percent: 0,
    layer_height_ranges: [],
  };
}
