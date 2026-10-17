"""Native HA options steps for the restricted Slicer installer; no frontend patch."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.helpers import selector

from .slicer_installer_runtime import ACTIONS, MUTATION_ACTIONS, get_installer_session

CONF_INSTALLER_SETUP = "slicer_installer_setup"
CHOICES = ("install", "preflight", "status", "cancel", "retry", "activate", "rollback", "resume",
           "recover_stage", "recover_retry", "recover_activation", "recover_rollback", "configure_connection", "finish")


class InstallerOptionsFlowMixin:
    """Use one persistent session for reopen/status/cancel and explicit mutations."""

    async def async_step_installer(self, user_input=None):
        session = get_installer_session(self.hass, self.config_entry)
        if session is None:
            return self.async_abort(reason="installer_integration_unavailable")
        self._installer_session = session
        if not session.snapshot()["paired"]:
            self._installer_action = "connect"
            self._installer_task = None
            return await self.async_step_installer_progress()
        return await self.async_step_installer_action()

    async def async_step_installer_action(self, user_input=None):
        session = getattr(self, "_installer_session", None)
        if session is None:
            return self.async_abort(reason="installer_integration_unavailable")
        errors = {}
        if user_input is not None:
            operation = user_input.get("operation")
            if operation == "finish":
                # Do not save an empty options dict or reset printer/account settings.
                return await self.async_step_init()
            if type(operation) is not str or operation not in CHOICES:
                errors["base"] = "installer_invalid_action"
            elif operation in MUTATION_ACTIONS and session.snapshot()["busy"]:
                errors["base"] = "installer_busy"
            else:
                self._installer_action = operation
                self._installer_task = None
                if operation in MUTATION_ACTIONS or operation == "cancel":
                    return await self.async_step_installer_confirm()
                return await self.async_step_installer_progress()
        snapshot = session.snapshot()
        result = snapshot["result"]
        if result.get("ok") is False:
            errors.setdefault("base", "installer_operation_failed")
        elif result.get("state") == "blocked":
            errors.setdefault("base", "installer_host_blocked")
        return self.async_show_form(
            step_id="installer_action",
            data_schema=vol.Schema({vol.Required("operation", default="status"):
                selector.SelectSelector(selector.SelectSelectorConfig(
                    options=list(CHOICES), mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="installer_operation"))}),
            description_placeholders={
                "state": result.get("state", "unknown"),
                "reason": result.get("error") or ", ".join(result.get("reasons", [])) or "-",
                "active": snapshot.get("operation") if snapshot["busy"] else "-",
            },
            errors=errors,
        )

    async def async_step_installer_confirm(self, user_input=None):
        operation = getattr(self, "_installer_action", None)
        if type(operation) is not str or operation not in MUTATION_ACTIONS | {"cancel"}:
            return self.async_abort(reason="installer_integration_unavailable")
        if user_input is not None:
            if user_input.get("confirm") is True:
                return await self.async_step_installer_progress()
            return await self.async_step_installer_action()
        return self.async_show_form(
            step_id="installer_confirm",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            description_placeholders={"operation": operation},
        )

    async def async_step_installer_progress(self, user_input=None):
        session = getattr(self, "_installer_session", None)
        operation = getattr(self, "_installer_action", None)
        if session is None or type(operation) is not str or operation not in ACTIONS:
            return self.async_abort(reason="installer_integration_unavailable")
        task = getattr(self, "_installer_task", None)
        if task is None:
            # FlowManager may cancel this observer when the dialog closes.
            # InstallerSession shields and owns the underlying executor operation.
            task = self._installer_task = self.hass.async_create_task(session.async_run(operation))
        if not task.done():
            return self.async_show_progress(
                step_id="installer_progress", progress_action="installer_working",
                progress_task=task,
            )
        if not task.cancelled():
            task.result()
        next_step = "installer_connection_finish" if operation == "configure_connection" else "installer_action"
        return self.async_show_progress_done(next_step_id=next_step)

    async def async_step_installer_connection_finish(self, user_input=None):
        # The browser submits no address or key; only the pinned, verified offer
        # supplies them. This native flow completion persists and reloads options.
        session = getattr(self, "_installer_session", None)
        if session is None:
            return self.async_abort(reason="installer_integration_unavailable")
        options = await session.async_connection_options(self.config_entry)
        if options is None:
            return await self.async_step_installer_action()
        return self.async_create_entry(title="", data=options)
