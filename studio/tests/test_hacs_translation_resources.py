"""HACS must ship the language files consumed by Home Assistant."""
from pathlib import Path
import json
from string import Formatter
import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio"


def _leaves(value, prefix=""):
    if isinstance(value, dict):
        return {key: leaf for name, child in value.items()
                for key, leaf in _leaves(child, f"{prefix}.{name}" if prefix else name).items()}
    assert isinstance(value, str) and value.strip(), f"Invalid translation at {prefix}"
    return {prefix: value}


@pytest.mark.parametrize("language", ["de", "en"])
def test_installable_language_resource_covers_strings(language):
    canonical = _leaves(json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8-sig")))
    resource = COMPONENT / "translations" / f"{language}.json"
    assert resource.is_file(), f"HA loads translations/{language}.json, not strings.json"
    translated = _leaves(json.loads(resource.read_text(encoding="utf-8-sig")))
    assert translated.keys() == canonical.keys()


@pytest.mark.parametrize("language", ["de", "en"])
def test_language_resource_preserves_runtime_placeholders(language):
    canonical = _leaves(json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8-sig")))
    translated = _leaves(json.loads((COMPONENT / "translations" / f"{language}.json").read_text(encoding="utf-8-sig")))
    def fields(text):
        return sorted(field for _, field, _, _ in Formatter().parse(text) if field is not None)
    for key, value in canonical.items():
        assert fields(translated[key]) == fields(value), key
