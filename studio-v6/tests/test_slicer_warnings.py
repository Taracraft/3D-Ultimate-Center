"""Tests for slicer warning and metrics functions (HA-independent)."""
from __future__ import annotations


def _build_detailed_warning(plate: dict, original_warning: str | None) -> str | None:
    if not original_warning:
        return None
    
    feature_times = plate.get("feature_type_times", {})
    bridge_seconds = feature_times.get("bridge", 0.0)
    overhang_seconds = feature_times.get("overhang wall", 0.0)
    support_seconds = (
        feature_times.get("support", 0.0) + 
        feature_times.get("support interface", 0.0)
    )
    
    if bridge_seconds <= 0 and overhang_seconds <= 0:
        return original_warning
    
    parts = [original_warning]
    
    if bridge_seconds > 0:
        hours, remainder = divmod(int(bridge_seconds), 3600)
        minutes = remainder // 60
        seconds = remainder % 60
        time_str = f"{hours}h {minutes:02d}m {seconds:02d}s" if hours else f"{minutes}m {seconds:02d}s"
        parts.append(f"Bridge: {time_str}")
    
    if overhang_seconds > 0:
        minutes = int(overhang_seconds) // 60
        seconds = int(overhang_seconds) % 60
        parts.append(f"Overhang: {minutes}m {seconds:02d}s")
    
    objects = plate.get("objects", [])
    floating_objects = []
    
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        obj_name = obj.get("name", "unknown")
        warning_msg = obj.get("warning_message", "") or ""
        
        if "floating" in warning_msg.lower() or "overhang" in warning_msg.lower():
            bbox = obj.get("bbox", {})
            floating_objects.append({
                "name": obj_name,
                "id": obj.get("id"),
                "position": (bbox.get("x", 0), bbox.get("y", 0)),
                "size": (bbox.get("width", 0), bbox.get("depth", 0), bbox.get("height", 0)),
            })
    
    if floating_objects:
        parts.append("\nFloating regions detected:")
        for obj_info in floating_objects:
            x, y = obj_info["position"]
            w, d, h = obj_info["size"]
            parts.append(
                f"  * {obj_info['name']}: "
                f"Position ({x:.1f}, {y:.1f})mm, "
                f"Size {w:.1f}x{d:.1f}x{h:.1f}mm"
            )
    
    if support_seconds <= 0 and (bridge_seconds > 0 or overhang_seconds > 0):
        parts.append(
            "\nWarning: No support structure enabled. "
            "Enable support generation to prevent print failures."
        )
    
    return "\n".join(parts)


def _engine_result_metrics(engine_result: dict, requested_plate_index: int) -> dict:
    def number(value):
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed == parsed else None
    
    raw_plates = engine_result.get("sliced_plates")
    plates = raw_plates if isinstance(raw_plates, list) else []
    plate = None
    for candidate in plates:
        if not isinstance(candidate, dict):
            continue
        try:
            candidate_id = int(candidate.get("id") or 0)
        except (TypeError, ValueError):
            candidate_id = 0
        if candidate_id == requested_plate_index + 1:
            plate = candidate
            break
    if plate is None:
        plate = next((item for item in plates if isinstance(item, dict)), {})
    raw_filaments = plate.get("filaments")
    filaments = raw_filaments if isinstance(raw_filaments, list) else []
    filament_used_g = sum(number(item.get("total_used_g")) or 0.0 for item in filaments if isinstance(item, dict))
    total_prediction = number(plate.get("total_predication"))
    model_prediction = number(plate.get("main_predication"))
    preparation = None
    if total_prediction is not None and model_prediction is not None:
        preparation = max(0.0, total_prediction - model_prediction)
    return {
        "return_code": engine_result.get("return_code"),
        "error_string": engine_result.get("error_string"),
        "layer_height_mm": number(engine_result.get("layer_height")),
        "plate_index": engine_result.get("plate_index"),
        "triangle_count": plate.get("triangle_count"),
        "print_time_seconds": total_prediction,
        "model_time_seconds": model_prediction,
        "preparation_time_seconds": preparation,
        "slice_time_ms": plate.get("sliced_time"),
        "filament_used_g": filament_used_g or None,
        "filament_change_count": plate.get("filament_change_times"),
        "original_warning": plate.get("warning_message") or None,
        "warning": _build_detailed_warning(plate, plate.get("warning_message") or None),
    }


def test_build_detailed_warning_returns_none_when_no_original_warning():
    """Wenn keine Warnung existiert, soll None zurückgegeben werden."""
    plate = {"feature_type_times": {}, "objects": []}
    result = _build_detailed_warning(plate, None)
    assert result is None


def test_build_detailed_warning_returns_original_when_no_bridge_or_overhang():
    """Wenn keine Bridges oder Overhangs vorhanden sind, wird die ursprüngliche Warnung zurückgegeben."""
    plate = {
        "feature_type_times": {},
        "objects": [],
        "warning_message": "Allgemeine Warnung"
    }
    result = _build_detailed_warning(plate, "Allgemeine Warnung")
    assert result == "Allgemeine Warnung"


def test_build_detailed_warning_with_bridge_time():
    """Testet Bridge-Zeitberechnung."""
    plate = {
        "feature_type_times": {"bridge": 5840.0},
        "objects": [],
        "warning_message": "Warning: floating regions detected"
    }
    result = _build_detailed_warning(plate, "Warning: floating regions detected")
    assert "Bridge: 1h 37m 20s" in result
    assert "floating regions detected" in result


def test_build_detailed_warning_with_floating_object():
    """Testet detaillierte Objektwarnung mit Position und Größe."""
    plate = {
        "feature_type_times": {"bridge": 100.0},
        "objects": [
            {
                "name": "v2",
                "id": 5,
                "warning_message": "It seems object v2 has floating regions.",
                "bbox": {"x": 38.0, "y": 8.0, "width": 180.0, "depth": 240.0, "height": 223.5}
            }
        ],
        "warning_message": "Floating regions detected"
    }
    result = _build_detailed_warning(plate, "Floating regions detected")
    assert "Floating regions detected:" in result
    assert "v2" in result
    assert "Position (38.0, 8.0)mm" in result
    assert "Size 180.0x240.0x223.5mm" in result


def test_engine_result_metrics_returns_detailed_warning():
    """Testet dass _engine_result_metrics die detaillierte Warnung verwendet."""
    engine_result = {
        "return_code": 0,
        "error_string": "Success.",
        "layer_height": 0.2,
        "plate_index": 0,
        "sliced_plates": [
            {
                "id": 1,
                "feature_type_times": {"bridge": 5840.0, "overhang wall": 540.0},
                "filaments": [{"id": 1, "total_used_g": 10.5}],
                "total_predication": 300000.0,
                "main_predication": 260000.0,
                "sliced_time": 32000,
                "filament_change_times": 0,
                "triangle_count": 100000,
                "objects": [
                    {
                        "name": "test_object",
                        "id": 1,
                        "warning_message": "Floating region detected",
                        "bbox": {"x": 100.0, "y": 100.0, "width": 50.0, "depth": 50.0, "height": 30.0}
                    }
                ],
                "warning_message": "Warning: floating regions detected"
            }
        ]
    }
    
    result = _engine_result_metrics(engine_result, requested_plate_index=0)
    
    assert "floating regions detected" in result["warning"]
    assert "Bridge: 1h 37m 20s" in result["warning"]
    assert "Overhang: 9m 00s" in result["warning"]
    assert "Position (100.0, 100.0)mm" in result["warning"]
    assert "Size 50.0x50.0x30.0mm" in result["warning"]
