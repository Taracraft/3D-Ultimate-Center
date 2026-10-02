"""Constants for 3D-Printer Control Center."""
DOMAIN = "printer_control_center"
NAME = "3D-Printer Control Center"
VERSION = "5.0.0-beta38"

PLATFORMS = ["sensor", "binary_sensor", "light", "button", "select", "switch", "camera"]

CONF_MODE = "connection_mode"
CONF_REGION = "region"
CONF_EMAIL = "email"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_CLOUD_UID = "cloud_uid"
CONF_HOST = "host"
CONF_SERIAL = "serial"
CONF_ACCESS_CODE = "access_code"
CONF_PRINTER_NAME = "printer_name"
CONF_AMS_TYPE = "ams_type"
CONF_SHOW_MANUAL_FW_BUTTON = "show_manual_firmware_update_button"
CONF_TLS_INSECURE = "tls_insecure"

CONF_CAMERA_MODE = "camera_mode"
CONF_CAMERA_ENTITY = "camera_entity"
CONF_CAMERA_URL = "camera_url"

CAMERA_MODE_AUTO = "auto"
CAMERA_MODE_DISABLED = "disabled"
CAMERA_MODE_CHAMBER_IMAGE_6000 = "chamber_image_6000"
CAMERA_MODE_RTSPS_322 = "rtsps_322"
CAMERA_MODE_EXTERNAL_ENTITY = "external_entity"
CAMERA_MODE_EXTERNAL_URL = "external_url"

CAMERA_MODE_OPTIONS = {
    CAMERA_MODE_AUTO: "Automatisch nach Druckermodell",
    CAMERA_MODE_DISABLED: "Keine Kamera",
    CAMERA_MODE_CHAMBER_IMAGE_6000: "Chamber Image / TCP 6000 (A1/P1/A2)",
    CAMERA_MODE_RTSPS_322: "RTSPS / TCP 322 (X1/H2/P2/X2)",
    CAMERA_MODE_EXTERNAL_ENTITY: "Externe Home-Assistant-Kamera-Entity",
    CAMERA_MODE_EXTERNAL_URL: "Externe MJPEG-/Proxy-URL",
}

CAMERA_MODE_OPTIONS_EN = {
    CAMERA_MODE_AUTO: "Auto by printer model",
    CAMERA_MODE_DISABLED: "No camera",
    CAMERA_MODE_CHAMBER_IMAGE_6000: "Chamber Image / TCP 6000 (A1/P1/A2)",
    CAMERA_MODE_RTSPS_322: "RTSPS / TCP 322 (X1/H2/P2/X2)",
    CAMERA_MODE_EXTERNAL_ENTITY: "External Home Assistant camera entity",
    CAMERA_MODE_EXTERNAL_URL: "External MJPEG/proxy URL",
}

CONF_UI_LANGUAGE = "ui_language"
CONF_AUTO_CREATE_DASHBOARDS = "auto_create_dashboards"
UI_LANGUAGE_AUTO = "auto"
UI_LANGUAGE_DE = "de"
UI_LANGUAGE_EN = "en"
UI_LANGUAGE_OPTIONS = {
    UI_LANGUAGE_AUTO: "Automatisch / Automatic (Home Assistant)",
    UI_LANGUAGE_DE: "Deutsch",
    UI_LANGUAGE_EN: "English",
}

MODE_LAN = "lan"
MODE_CLOUD = "cloud"
MODE_HYBRID = "hybrid"

REGION_GLOBAL = "global"
REGION_CHINA = "china"

AMS_AUTO = "auto"
AMS_NONE = "none"
AMS_LITE = "ams_lite"
AMS_ORIGINAL = "ams_original"
AMS_2_PRO = "ams_2_pro"
AMS_HT = "ams_ht"
AMS_BMCU_370 = "bmcu_370"
AMS_4_SLOT_COMPATIBLE = "ams_4_slot_compatible"

AMS_OPTIONS = {
    AMS_AUTO: "Automatisch erkennen",
    AMS_NONE: "Kein AMS",
    AMS_LITE: "AMS lite",
    AMS_ORIGINAL: "AMS (Original / Gen 1)",
    AMS_2_PRO: "AMS 2 Pro",
    AMS_HT: "AMS HT",
    AMS_BMCU_370: "BMCU-370 / BCMU-370 (Drittanbieter)",
    AMS_4_SLOT_COMPATIBLE: "AMS-/BMCU-kompatibel (4 Slots erkannt)",
}

AMS_OPTIONS_EN = {
    AMS_AUTO: "Auto-detect",
    AMS_NONE: "No AMS",
    AMS_LITE: "AMS lite",
    AMS_ORIGINAL: "AMS (Original / Gen 1)",
    AMS_2_PRO: "AMS 2 Pro",
    AMS_HT: "AMS HT",
    AMS_BMCU_370: "BMCU-370 / BCMU-370 (third-party)",
    AMS_4_SLOT_COMPATIBLE: "AMS/BMCU compatible (4 slots detected)",
}

EVENT_MANUAL_FIRMWARE_UPDATE_REQUESTED = (
    "printer_control_center_manual_firmware_update_requested"
)




CONF_AUTO_DISCOVER_IP = "auto_discover_ip"
CONF_DISCOVERY_SUBNETS = "discovery_subnets"
CONF_DISCOVERY_INTERFACE = "discovery_interface"




CONF_DISCOVERY_HOSTS = "discovery_hosts"
CONF_DISCOVERY_PORTS = "discovery_ports"
CONF_SCAN_PROFILE = "scan_profile"
CONF_SCAN_TIMEOUT_MS = "scan_timeout_ms"
CONF_SCAN_WORKERS = "scan_workers"
CONF_SCAN_MAX_HOSTS = "scan_max_hosts"
CONF_SCAN_BROADCAST = "scan_broadcast"
CONF_SCAN_NEIGHBORS = "scan_neighbors"
CONF_SCAN_CONNECTIONS = "scan_connections"
CONF_SCAN_ROUTES = "scan_routes"
CONF_RESCAN_ON_DISCONNECT = "rescan_on_disconnect"

SCAN_QUICK = "quick"
SCAN_BALANCED = "balanced"
SCAN_DEEP = "deep"

SERVICE_SCAN_NETWORK = "scan_network"
SERVICE_INSTALL_DASHBOARDS = "install_dashboards"


FRONTEND_URL_BASE = f"/{DOMAIN}"
FRONTEND_JS_FILENAME = "printer-control-center-cards.js"
FRONTEND_JS_PATH = f"{FRONTEND_URL_BASE}/{FRONTEND_JS_FILENAME}"
FRONTEND_JS_URL = f"{FRONTEND_JS_PATH}?v={VERSION}"
FRONTEND_LOGO_PATH = f"{FRONTEND_URL_BASE}/logo-3d-printer-control-center.png"


SERVICE_REFRESH_TEMPLATES = "refresh_templates"
TEMPLATE_CACHE_SECONDS = 45
TEMPLATE_MAX_FILES = 120
TEMPLATE_MAX_DEPTH = 3
TEMPLATE_PREVIEW_MAX_BYTES = 600_000