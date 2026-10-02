from tests.test_v6_numeric_override_confirmation import application


def test_numeric_proof_preserves_values_and_marks_conflicts():
    job = {"process_overrides": {"selected_process_profile": {"profile_id": "p", "contract_sha256": "h", "settings": {"layer_height": "0.2"}}, "layer_height_mm": 0.12}, "material_plan": {"filaments": [{"selected_profile": {"id": "f"}}]}}
    runtime = {"selected_process_profile": {"applied": True, "profile_id": "p", "contract_sha256": "h"}, "process_settings": {"layer_height": "0.12"}, "filaments": [{"selected_profile_id": "f"}]}
    meta = {"gcode_profile_settings": {"layer_height": "0.12"}}
    row = application(job, runtime, meta)["process"]["numeric_value_proof"][0]
    assert row["profile_value"] == "0.2"
    assert row["requested_value"] == 0.12
    assert row["applied_value"] == "0.12"
    assert row["gcode_value"] == "0.12"
    assert row["overridden"] is True
    assert row["status"] == "confirmed"
    meta["gcode_profile_settings"]["layer_height"] = "0.2"
    assert application(job, runtime, meta)["process"]["numeric_value_proof"][0]["status"] == "mismatch"
    runtime["selected_process_profile"]["contract_sha256"] = "wrong"
    row = application(job, runtime, None)["process"]["numeric_value_proof"][0]
    assert row["applied_value"] is None
    assert row["status"] == "unverified"


def test_missing_numeric_values_are_never_fabricated():
    rows = application({}, {}, None)["process"]["numeric_value_proof"]
    assert len(rows) == 3
    for row in rows:
        assert all(row[key] is None for key in ("profile_value", "requested_value", "applied_value", "gcode_value"))
        assert row["status"] == "unverified"
        assert row["overridden"] is False



def test_additional_process_values_require_both_runtime_and_artifact_evidence():
    settings = {"outer_wall_line_width": .42, "support_interface_top_layers": 3, "bridge_speed": 25}
    job = {"process_overrides": {"selected_process_profile": {"profile_id": "p", "contract_sha256": "h", "settings": settings}}, "material_plan": {"filaments": [{"selected_profile": {"id": "f"}}]}}
    runtime = {"filaments": [{"selected_profile_id": "f"}], "selected_process_profile": {"applied": True, "profile_id": "p", "contract_sha256": "h"}, "process_settings": {"outer_wall_line_width": "0.42", "support_interface_top_layers": "3", "bridge_speed": ["25"]}}
    meta = {"gcode_profile_settings": {"outer_wall_line_width": "0.42", "support_interface_top_layers": "3", "bridge_speed": "25"}}
    rows = {row["key"]: row for row in application(job, runtime, meta)["process"]["numeric_value_proof"]}
    for key in settings:
        assert rows[key]["status"] == "confirmed"
    del runtime["process_settings"]["bridge_speed"]
    meta["gcode_profile_settings"]["outer_wall_line_width"] = "0.5"
    rows = {row["key"]: row for row in application(job, runtime, meta)["process"]["numeric_value_proof"]}
    assert rows["bridge_speed"]["status"] == "unverified"
    assert rows["outer_wall_line_width"]["status"] == "mismatch"
