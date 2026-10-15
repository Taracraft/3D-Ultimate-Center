"""Constants for Ultimate 3D Studio."""

import json
from pathlib import Path

from homeassistant.const import Platform

DOMAIN = "ultimate_3d_studio"
DATA_TOOLPATH_CACHE = "ultimate_3d_studio_toolpath_cache"
NAME = "Ultimate 3D Studio"
# The integration manifest is the only package-version authority.
VERSION = str(json.loads(Path(__file__).with_name("manifest.json").read_text(encoding="utf-8"))["version"])
API_BASE = "/api/ultimate_3d_studio/v1"

CONF_INSTANCE_NAME = "instance_name"
DEFAULT_INSTANCE_NAME = "3D Studio Test"

CONF_LAN_ENABLED = "lan_enabled"
CONF_PRINTER_NAME = "printer_name"
CONF_HOST = "host"
CONF_SERIAL = "serial"
CONF_ACCESS_CODE = "access_code"
CONF_TLS_INSECURE = "tls_insecure"

CONF_SLICER_ENABLED = "slicer_enabled"
CONF_SLICER_BASE_URL = "slicer_base_url"
CONF_SLICER_API_SECRET = "slicer_api_secret"

CONF_CLOUD_ENABLED = "cloud_enabled"
CONF_CLOUD_REGION = "cloud_region"
CONF_CLOUD_EMAIL = "cloud_email"
CONF_CLOUD_ACCESS_TOKEN = "cloud_access_token"
CONF_CLOUD_REFRESH_TOKEN = "cloud_refresh_token"
CONF_CLOUD_UID = "cloud_uid"
CONF_CLOUD_PROFILE_SYNC = "cloud_profile_sync"

REGION_GLOBAL = "global"
REGION_CHINA = "china"
DEFAULT_CLOUD_PROFILE_SYNC = True

DEFAULT_PRINTER_NAME = "Bambu Lab Drucker"
DEFAULT_TLS_INSECURE = True
MQTT_PORT = 8883
MQTT_USERNAME = "bblp"

DATA_RUNTIMES = "runtimes"
DATA_VIEWS_REGISTERED = "views_registered"
DATA_CLOUD_PROFILE_SYNC = "cloud_profile_sync_runtime"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
]
