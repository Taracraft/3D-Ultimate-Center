from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN
from .entity import SlicingServerEntity

SENSORS = {
    "server_status": ("Serverstatus", "mdi:server", "info", "status", "unknown"),
    "version": ("Version", "mdi:tag", "info", "version", "unknown"),
    "engine_count": ("Slicing-Engines", "mdi:cog-box", "info", "engine_count", 0),
    "active_jobs": ("Aktive Aufträge", "mdi:progress-wrench", "status", "active_jobs", 0),
    "queued_jobs": ("Wartende Aufträge", "mdi:format-list-numbered", "status", "queued_jobs", 0),
    "last_job_id": ("Letzte Job-ID", "mdi:identifier", "status", "last_job_id", "none"),
    "last_job_status": ("Letzter Auftragsstatus", "mdi:printer-3d", "status", "last_job_status", "none"),
    "last_engine": ("Letzte Slicing-Engine", "mdi:engine", "status", "last_engine", "none"),
    "completed_jobs": ("Abgeschlossene Aufträge", "mdi:check-circle-outline", "diagnostics", "completed_jobs", 0),
    "failed_jobs": ("Fehlgeschlagene Aufträge", "mdi:alert-circle-outline", "diagnostics", "failed_jobs", 0),
    "upload_count": ("Hochgeladene Modelle", "mdi:upload", "diagnostics", "upload_count", 0),
    "output_count": ("Ergebnisdateien", "mdi:file-download-outline", "diagnostics", "output_count", 0),
    "printer_profile_count": ("Druckerprofile", "mdi:printer-3d-nozzle", "diagnostics", "printer_profile_count", 0),
    "disk_usage_mb": ("Speicherbelegung", "mdi:harddisk", "diagnostics", "disk_bytes", 0),
    "last_log_line": ("Letzte Logzeile", "mdi:text-box-outline", "diagnostics", "last_log_line", "none"),
    "last_error": ("Letzter Fehler", "mdi:alert-outline", "diagnostics", "last_error", "none"),
    "worker_journal": ("Worker-Journal", "mdi:server-network", "diagnostics", "worker_journal", "none"),
    "refresh_journal": ("Dispatcher-Journal", "mdi:timer-refresh-outline", "diagnostics", "refresh_journal", "none"),
}

async def async_setup_entry(hass, entry, add):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    add([SlicingSensor(coordinator, entry.entry_id, key, *value) for key, value in SENSORS.items()])
    add([DiagnosticsSensor(coordinator, entry.entry_id)])

class SlicingSensor(SlicingServerEntity, SensorEntity):
    def __init__(self, coordinator, entry_id, key, name, icon, section, field, default):
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self.section = section
        self.field = field
        self.default = default
        self.key = key

    @property
    def native_value(self):
        value = self.coordinator.data.get(self.section, {}).get(self.field, self.default)
        if self.key == "disk_usage_mb":
            return round((value or 0) / 1048576, 1)
        if self.key in {"last_log_line", "last_error", "worker_journal", "refresh_journal"}:
            return str(value or self.default)[:250]
        return self.default if value is None else value

class DiagnosticsSensor(SlicingServerEntity, SensorEntity):
    _attr_name = "Diagnose"
    _attr_icon = "mdi:stethoscope"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_diagnostics"

    @property
    def native_value(self):
        data = self.coordinator.data.get("diagnostics", {})
        status = str(self.coordinator.data.get("status", {}).get("last_job_status") or "").casefold()
        current_error = data.get("last_error") not in (None, "", "none")
        return "warning" if status == "failed" or current_error else "ok"

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data.get("diagnostics", {})
        return {
            "generated_at": data.get("generated_at"),
            "last_log_file": data.get("last_log_file"),
            "worker_journal": data.get("worker_journal"),
            "refresh_journal": data.get("refresh_journal"),
            "recent_jobs": data.get("recent_jobs", []),
        }