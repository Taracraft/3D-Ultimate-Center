"""Native setup routing: Supervisor app, external server or explicitly provisioned host."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.helpers import selector
from homeassistant.helpers.http import KEY_AUTHENTICATED, current_request

from .slicer_supervisor_app import get_supervisor_session

SUPERVISOR_CHOICES = ("status", "install", "back")


class SlicerInstallationFlowMixin:
    """Do not interpret a missing Core mount as failure of every installation path."""

    async def async_step_slicer_installation(self, user_input=None):
        return self.async_show_menu(
            step_id="slicer_installation",
            menu_options=["slicer_supervisor", "slicer_external", "slicer_host_legacy"],
        )

    async def async_step_slicer_external(self, user_input=None):
        # Preserve the native server URL/secret form and every existing option.
        # No discovery credentials are trusted or stored automatically.
        return await self.async_step_init()

    async def async_step_slicer_host_legacy(self, user_input=None):
        # Explicit opt-in to the existing pinned Unix host contract, no fallback.
        return await self.async_step_installer()

    async def async_step_slicer_supervisor(self, user_input=None):
        if not hasattr(self, "_supervisor_session"):
            self._supervisor_session = get_supervisor_session(self.hass, self.config_entry)
        session = self._supervisor_session
        if user_input is None:
            self._supervisor_action = "status"
            self._supervisor_task = None
            self._supervisor_confirmed = False
            return await self.async_step_slicer_supervisor_progress()
        operation = user_input.get("operation") if type(user_input) is dict else None
        if operation == "back":
            return await self.async_step_slicer_installation()
        if type(operation) is not str or operation not in SUPERVISOR_CHOICES:
            return self._supervisor_form("app_operation_failed")
        if session.busy:
            return self._supervisor_form("app_busy")
        self._supervisor_action = operation
        self._supervisor_task = None
        self._supervisor_confirmed = False
        if operation == "install":
            return await self.async_step_slicer_supervisor_confirm()
        return await self.async_step_slicer_supervisor_progress()

    async def async_step_slicer_supervisor_confirm(self, user_input=None):
        if getattr(self, "_supervisor_action", None) != "install":
            return self.async_abort(reason="installer_integration_unavailable")
        if user_input is not None:
            if type(user_input) is dict and user_input.get("confirm") is True:
                self._supervisor_confirmed = True
                return await self.async_step_slicer_supervisor_progress()
            return self._supervisor_form()
        return self.async_show_form(
            step_id="slicer_supervisor_confirm",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
        )

    async def async_step_slicer_supervisor_progress(self, user_input=None):
        session = getattr(self, "_supervisor_session", None)
        operation = getattr(self, "_supervisor_action", None)
        if session is None or operation not in {"status", "install"}:
            return self.async_abort(reason="installer_integration_unavailable")
        task = getattr(self, "_supervisor_task", None)
        if task is None:
            # Native OptionsFlow does not populate context.user_id. Trust only
            # HA's authenticated request object, never a submitted flow field.
            request = current_request.get()
            user = (request.get("hass_user") if request is not None
                    and request.get(KEY_AUTHENTICATED) is True else None)
            task = self._supervisor_task = self.hass.async_create_task(session.async_run(
                operation, getattr(user, "id", None),
                confirmed=getattr(self, "_supervisor_confirmed", False),
            ))
        if not task.done():
            return self.async_show_progress(
                step_id="slicer_supervisor_progress", progress_action="supervisor_app_working",
                progress_task=task,
            )
        if not task.cancelled():
            # Consume only the sanitized projection returned by the session.
            self._supervisor_observed = task.result()
        return self.async_show_progress_done(next_step_id="slicer_supervisor_result")

    async def async_step_slicer_supervisor_result(self, user_input=None):
        return self._supervisor_form()

    def _supervisor_form(self, error=None):
        session = getattr(self, "_supervisor_session", None)
        if session is None:
            return self.async_abort(reason="installer_integration_unavailable")
        result = getattr(self, "_supervisor_observed", None) or session.snapshot()["result"]
        options = ["status", "back"]
        if result.get("ok") is True and result.get("state") == "not_installed" and not session.busy:
            options.insert(1, "install")
        errors = {}
        reason = error or result.get("error")
        if reason:
            errors["base"] = "supervisor_" + reason
        return self.async_show_form(
            step_id="slicer_supervisor",
            data_schema=vol.Schema({vol.Required("operation", default="status"):
                selector.SelectSelector(selector.SelectSelectorConfig(
                    options=options, mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="supervisor_app_operation"))}),
            description_placeholders={"state": result.get("state", "blocked")},
            errors=errors,
        )
