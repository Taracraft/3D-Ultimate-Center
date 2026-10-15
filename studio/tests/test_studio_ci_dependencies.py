"""Synthetic version/closure checks; no package download or installation."""
import importlib.util
from pathlib import Path
import pytest
from packaging.markers import default_environment

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("studio_ci_dependencies", ROOT/"tools/studio_ci_dependencies.py")
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)

@pytest.fixture
def graph():
    pins = "\n".join(name+"==1.0" for name in sorted(contract.ROOTS))
    installed = {name: {"version": "1.0", "requires": []} for name in contract.ROOTS}
    env = dict(default_environment(), python_version="3.13", python_full_version="3.13.0", sys_platform="linux")
    return pins, installed, env

def test_complete_exact_versions_pass(graph):
    text, installed, env = graph
    assert contract.verify(text, installed, env)["packages"] == 5

@pytest.mark.parametrize("line", ["aiohttp>=1", "aiohttp==1.*", "aiohttp===1.0",
                                  "aiohttp[test]==1.0", "aiohttp @ https://example.invalid/a.whl"])
def test_ranges_wildcards_extras_and_urls_fail(graph, line):
    text, installed, env = graph
    text = text.replace("aiohttp==1.0", line)
    with pytest.raises(ValueError): contract.verify(text, installed, env)

def test_duplicate_even_inactive_pin_fails(graph):
    text, installed, env = graph
    with pytest.raises(ValueError):
        contract.verify(text+'\naiohttp==1.0; sys_platform == "win32"', installed, env)

@pytest.mark.parametrize("mutation", ["missing", "version"])
def test_installed_drift_fails(graph, mutation):
    text, installed, env = graph
    if mutation == "missing": installed.pop("pytest")
    else: installed["pytest"]["version"] = "2.0"
    with pytest.raises(ValueError): contract.verify(text, installed, env)

@pytest.mark.parametrize("requirement", ["missing>=1", "aiohttp>=2", "aiohttp[test]>=1",
                                        "aiohttp @ https://example.invalid/a.whl"])
def test_missing_or_incompatible_transitive_dependency_fails(graph, requirement):
    text, installed, env = graph
    installed["pytest"]["requires"] = [requirement]
    with pytest.raises(ValueError): contract.verify(text, installed, env)

def test_windows_only_dependency_is_checked_only_on_windows(graph):
    text, installed, env = graph
    text += '\ncolorama==1.0; sys_platform == "win32"'
    installed["pytest"]["requires"] = ['colorama>=1; sys_platform == "win32"']
    assert contract.verify(text, installed, env)["packages"] == 5
    env["sys_platform"] = "win32"
    with pytest.raises(ValueError): contract.verify(text, installed, env)
    installed["colorama"] = {"version": "1.0", "requires": []}
    assert contract.verify(text, installed, env)["packages"] == 6

@pytest.mark.parametrize("key,value", [("python_version","3.12"),("sys_platform","darwin")])
def test_unreviewed_environment_is_rejected(graph,key,value):
    text, installed, env = graph
    env[key]=value
    with pytest.raises(ValueError): contract.verify(text, installed, env)

def test_extra_dependencies_do_not_enter_default_closure(graph):
    text, installed, env = graph
    installed["setuptools"]["requires"] = ['unused>=1; extra == "test"']
    assert contract.verify(text, installed, env)["verified"]

def test_required_root_cannot_be_silently_dropped(graph):
    text, installed, env = graph
    with pytest.raises(ValueError): contract.verify(text.replace("wheel==1.0",""), installed, env)
