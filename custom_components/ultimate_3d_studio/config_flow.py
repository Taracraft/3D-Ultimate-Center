"""Config and options flows for Ultimate 3D Studio."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .bambu_cloud_auth import (
    BambuCloudAuth,
    BambuCloudAuthError,
    BambuCloudTokens,
    VerificationCodeRequired,
)
from .const import (
    CONF_ACCESS_CODE,
    CONF_CLOUD_ACCESS_TOKEN,
    CONF_CLOUD_EMAIL,
    CONF_CLOUD_ENABLED,
    CONF_CLOUD_PROFILE_SYNC,
    CONF_CLOUD_REFRESH_TOKEN,
    CONF_CLOUD_REGION,
    CONF_CLOUD_UID,
    CONF_HOST,
    CONF_INSTANCE_NAME,
    CONF_LAN_ENABLED,
    CONF_PRINTER_NAME,
    CONF_SERIAL,
    CONF_SLICER_API_SECRET,
    CONF_SLICER_BASE_URL,
    CONF_SLICER_ENABLED,
    CONF_TLS_INSECURE,
    DEFAULT_CLOUD_PROFILE_SYNC,
    DEFAULT_INSTANCE_NAME,
    DEFAULT_PRINTER_NAME,
    DEFAULT_TLS_INSECURE,
    DOMAIN,
    REGION_CHINA,
    REGION_GLOBAL,
)

from .slicer_connection_probe import (
    SlicerConnectionProbeError,
    async_probe_slicer_connection,
)
from .slicer_connection_settings import (
    SlicerConnectionSettingsError,
    normalize_slicer_base_url,
    validate_slicer_api_secret,
)

from .slicer_installer_flow import CONF_INSTALLER_SETUP, InstallerOptionsFlowMixin
from .slicer_installation_flow import SlicerInstallationFlowMixin

_LOGGER = logging.getLogger(__name__)
CONF_VERIFICATION_CODE = "verification_code"
CONF_SLICER_TEST_CONNECTION = "slicer_connection_test"
CONF_CLOUD_REAUTHENTICATE = "cloud_reauthenticate"


class Ultimate3DStudioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create the single isolated Studio runtime entry."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            instance_name = str(
                user_input.get(CONF_INSTANCE_NAME, DEFAULT_INSTANCE_NAME)
            ).strip() or DEFAULT_INSTANCE_NAME
            return self.async_create_entry(
                title=instance_name,
                data={CONF_INSTANCE_NAME: instance_name},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_INSTANCE_NAME,
                    default=DEFAULT_INSTANCE_NAME,
                ): str,
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return Ultimate3DStudioOptionsFlow()


class Ultimate3DStudioOptionsFlow(SlicerInstallationFlowMixin, InstallerOptionsFlowMixin, config_entries.OptionsFlow):
    """Configure direct printer and Bambu account access."""

    def __init__(self) -> None:
        self._pending_options: dict[str, Any] | None = None
        self._pending_email = ""
        self._pending_region = REGION_GLOBAL
        self._pending_cloud_reauthentication = False
        self._tested_slicer_options: dict[str, Any] | None = None
        self._slicer_test_status = "nicht geprüft"

    def _current(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    def _base_options(
        self,
        user_input: dict[str, Any],
        current: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            CONF_LAN_ENABLED: bool(user_input.get(CONF_LAN_ENABLED, current.get(CONF_LAN_ENABLED, False))),
            CONF_PRINTER_NAME: (
                str(user_input.get(CONF_PRINTER_NAME, current.get(CONF_PRINTER_NAME, ""))).strip()
                or DEFAULT_PRINTER_NAME
            ),
            CONF_HOST: str(user_input.get(CONF_HOST, current.get(CONF_HOST, ""))).strip(),
            CONF_SERIAL: str(user_input.get(CONF_SERIAL, current.get(CONF_SERIAL, ""))).strip(),
            CONF_ACCESS_CODE: str(user_input.get(CONF_ACCESS_CODE) or current.get(CONF_ACCESS_CODE, "")).strip(),
            CONF_TLS_INSECURE: bool(
                user_input.get(CONF_TLS_INSECURE, current.get(CONF_TLS_INSECURE, DEFAULT_TLS_INSECURE))
            ),
            CONF_SLICER_ENABLED: bool(
                user_input.get(
                    CONF_SLICER_ENABLED,
                    current.get(CONF_SLICER_ENABLED, False),
                )
            ),
            CONF_SLICER_BASE_URL: str(
                user_input.get(
                    CONF_SLICER_BASE_URL,
                    current.get(CONF_SLICER_BASE_URL, ""),
                )
            ).strip(),
            # Password selectors never prefill or re-expose persisted secrets.
            CONF_SLICER_API_SECRET: str(
                user_input.get(CONF_SLICER_API_SECRET)
                or current.get(CONF_SLICER_API_SECRET, "")
            ),
            CONF_CLOUD_ENABLED: bool(user_input.get(CONF_CLOUD_ENABLED, current.get(CONF_CLOUD_ENABLED, False))),
            CONF_CLOUD_PROFILE_SYNC: bool(
                user_input.get(
                    CONF_CLOUD_PROFILE_SYNC,
                    current.get(CONF_CLOUD_PROFILE_SYNC, DEFAULT_CLOUD_PROFILE_SYNC),
                )
            ),
            CONF_CLOUD_REGION: str(
                user_input.get(CONF_CLOUD_REGION, current.get(CONF_CLOUD_REGION, REGION_GLOBAL))
            ),
            CONF_CLOUD_EMAIL: str(
                user_input.get(CONF_CLOUD_EMAIL, current.get(CONF_CLOUD_EMAIL, ""))
            ).strip(),
            CONF_CLOUD_ACCESS_TOKEN: str(
                current.get(CONF_CLOUD_ACCESS_TOKEN, "")
            ).strip(),
            CONF_CLOUD_REFRESH_TOKEN: str(
                current.get(CONF_CLOUD_REFRESH_TOKEN, "")
            ).strip(),
            CONF_CLOUD_UID: str(current.get(CONF_CLOUD_UID, "")).strip(),
        }

    @staticmethod
    def _with_tokens(
        options: dict[str, Any],
        tokens: BambuCloudTokens,
        *,
        preserve_profile_sync: bool = False,
    ) -> dict[str, Any]:
        return {
            **options,
            CONF_CLOUD_ACCESS_TOKEN: tokens.access_token,
            CONF_CLOUD_REFRESH_TOKEN: tokens.refresh_token,
            CONF_CLOUD_UID: tokens.uid,
            CONF_CLOUD_ENABLED: True,
            CONF_CLOUD_PROFILE_SYNC: (
                options.get(CONF_CLOUD_PROFILE_SYNC, DEFAULT_CLOUD_PROFILE_SYNC)
                if preserve_profile_sync else True
            ),
        }

    def _reauthentication_options(self, email: str, region: str) -> dict[str, Any]:
        """Keep the latest unrelated options when a login attempt completes."""
        current = self._current()
        return {
            **self.config_entry.options,
            CONF_CLOUD_EMAIL: email,
            CONF_CLOUD_REGION: region,
            CONF_CLOUD_PROFILE_SYNC: current.get(
                CONF_CLOUD_PROFILE_SYNC, DEFAULT_CLOUD_PROFILE_SYNC
            ),
        }

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        if type(user_input) is dict and user_input.get(CONF_CLOUD_REAUTHENTICATE) is True:
            return await self.async_step_cloud_reauthenticate()
        if type(user_input) is dict and user_input.get(CONF_INSTALLER_SETUP) is True:
            return await self.async_step_slicer_installation()
        current = self._tested_slicer_options or self._current()
        errors: dict[str, str] = {}
        connection_test_requested = bool(
            user_input and user_input.get(CONF_SLICER_TEST_CONNECTION, False)
        )

        if user_input is not None:
            options = self._base_options(user_input, current)
            lan_enabled = bool(options[CONF_LAN_ENABLED])
            cloud_enabled = bool(options[CONF_CLOUD_ENABLED])
            cloud_sync = bool(options[CONF_CLOUD_PROFILE_SYNC])
            password = str(user_input.get(CONF_PASSWORD, "")).strip()
            email = str(options[CONF_CLOUD_EMAIL]).strip()
            existing_token = str(options[CONF_CLOUD_ACCESS_TOKEN]).strip()

            if options[CONF_SLICER_ENABLED]:
                try:
                    options[CONF_SLICER_BASE_URL] = normalize_slicer_base_url(
                        options[CONF_SLICER_BASE_URL]
                    )
                except SlicerConnectionSettingsError as error:
                    errors[CONF_SLICER_BASE_URL] = str(error)
                try:
                    validate_slicer_api_secret(options[CONF_SLICER_API_SECRET])
                except SlicerConnectionSettingsError:
                    errors[CONF_SLICER_API_SECRET] = "invalid_slicer_secret"

            if lan_enabled:
                if not options[CONF_HOST]:
                    errors[CONF_HOST] = "required"
                if not options[CONF_SERIAL]:
                    errors[CONF_SERIAL] = "required"
                if not options[CONF_ACCESS_CODE]:
                    errors[CONF_ACCESS_CODE] = "required"

            if connection_test_requested and not errors:
                self._tested_slicer_options = options
                current = options
                if not options[CONF_SLICER_ENABLED]:
                    errors["base"] = "slicer_not_configured"
                else:
                    try:
                        check = await async_probe_slicer_connection(
                            async_get_clientsession(self.hass),
                            options[CONF_SLICER_BASE_URL],
                            options[CONF_SLICER_API_SECRET],
                        )
                    except SlicerConnectionProbeError as error:
                        errors["base"] = str(error)
                        self._slicer_test_status = "fehlgeschlagen"
                    else:
                        self._slicer_test_status = (
                            f"bereit (Server {check['server_version']})"
                        )

            if cloud_enabled and cloud_sync and not connection_test_requested:
                if password and not email:
                    errors[CONF_CLOUD_EMAIL] = "required"
                elif password and not errors:
                    auth = BambuCloudAuth(
                        async_get_clientsession(self.hass),
                        str(options[CONF_CLOUD_REGION]),
                    )
                    try:
                        tokens = await auth.async_login_password(email, password)
                    except VerificationCodeRequired:
                        self._pending_options = options
                        self._pending_email = email
                        self._pending_region = str(options[CONF_CLOUD_REGION])
                        return await self.async_step_cloud_code()
                    except BambuCloudAuthError:
                        _LOGGER.exception("Studio Bambu account login failed")
                        errors["base"] = "invalid_auth"
                    except Exception:
                        _LOGGER.exception("Unexpected Studio Bambu account login error")
                        errors["base"] = "cannot_connect"
                    else:
                        return self.async_create_entry(
                            title="",
                            data=self._with_tokens(options, tokens),
                        )
                elif not existing_token:
                    if not email:
                        errors[CONF_CLOUD_EMAIL] = "required"
                    errors[CONF_PASSWORD] = "required"

            if not errors and not connection_test_requested:
                return self.async_create_entry(title="", data=options)

        token_configured = bool(
            str(current.get(CONF_CLOUD_ACCESS_TOKEN, "")).strip()
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_LAN_ENABLED,
                    default=bool(current.get(CONF_LAN_ENABLED, False)),
                ): bool,
                vol.Optional(
                    CONF_PRINTER_NAME,
                    default=str(
                        current.get(CONF_PRINTER_NAME, DEFAULT_PRINTER_NAME)
                    ),
                ): str,
                vol.Optional(
                    CONF_HOST,
                    default=str(current.get(CONF_HOST, "")),
                ): str,
                vol.Optional(
                    CONF_SERIAL,
                    default=str(current.get(CONF_SERIAL, "")),
                ): str,
                vol.Optional(CONF_ACCESS_CODE): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                    )
                ),
                vol.Required(
                    CONF_TLS_INSECURE,
                    default=bool(
                        current.get(
                            CONF_TLS_INSECURE,
                            DEFAULT_TLS_INSECURE,
                        )
                    ),
                ): bool,
                vol.Required(
                    CONF_SLICER_ENABLED,
                    default=bool(current.get(CONF_SLICER_ENABLED, False)),
                ): bool,
                vol.Optional(
                    CONF_SLICER_BASE_URL,
                    default=str(current.get(CONF_SLICER_BASE_URL, "")),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.URL,
                    )
                ),
                vol.Optional(CONF_SLICER_API_SECRET): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                    )
                ),
                vol.Optional(CONF_INSTALLER_SETUP, default=False): bool,
                vol.Optional(CONF_CLOUD_REAUTHENTICATE, default=False): bool,
                vol.Optional(
                    CONF_SLICER_TEST_CONNECTION,
                    default=False,
                ): bool,
                vol.Required(
                    CONF_CLOUD_ENABLED,
                    default=bool(
                        current.get(CONF_CLOUD_ENABLED, token_configured)
                    ),
                ): bool,
                vol.Required(
                    CONF_CLOUD_PROFILE_SYNC,
                    default=bool(
                        current.get(
                            CONF_CLOUD_PROFILE_SYNC,
                            DEFAULT_CLOUD_PROFILE_SYNC,
                        )
                    ),
                ): bool,
                vol.Required(
                    CONF_CLOUD_REGION,
                    default=str(
                        current.get(CONF_CLOUD_REGION, REGION_GLOBAL)
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[REGION_GLOBAL, REGION_CHINA],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="cloud_region",
                    )
                ),
                vol.Optional(
                    CONF_CLOUD_EMAIL,
                    default=str(current.get(CONF_CLOUD_EMAIL, "")),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.EMAIL,
                    )
                ),
                vol.Optional(CONF_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                    )
                ),
            }),
            description_placeholders={
                "cloud_token_status": (
                    "vorhanden" if token_configured else "nicht vorhanden"
                ),
                "lan_code_status": (
                    "vorhanden"
                    if bool(current.get(CONF_ACCESS_CODE))
                    else "nicht vorhanden"
                ),
                "slicer_connection_status": self._slicer_test_status,
                "slicer_secret_status": (
                    "vorhanden"
                    if bool(current.get(CONF_SLICER_API_SECRET))
                    else "nicht vorhanden"
                ),
            },
            errors=errors,
        )

    async def async_step_cloud_reauthenticate(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Renew authorization without changing unrelated integration options."""
        current = self._current()
        errors: dict[str, str] = {}
        email = str(current.get(CONF_CLOUD_EMAIL, "")).strip()
        region = str(current.get(CONF_CLOUD_REGION, REGION_GLOBAL))
        # A new password attempt invalidates any earlier verification challenge.
        self._pending_options = None
        self._pending_email = ""
        self._pending_cloud_reauthentication = False
        if user_input is not None:
            email_input = user_input.get(CONF_CLOUD_EMAIL, "")
            password_input = user_input.get(CONF_PASSWORD, "")
            email = email_input.strip() if isinstance(email_input, str) else ""
            password = password_input if isinstance(password_input, str) else ""
            region = user_input.get(CONF_CLOUD_REGION, region)
            if (not email or not password or not isinstance(region, str)
                    or region not in {REGION_GLOBAL, REGION_CHINA}):
                errors["base"] = "invalid_auth"
            else:
                options = {
                    CONF_CLOUD_EMAIL: email,
                    CONF_CLOUD_REGION: region,
                }
                auth = BambuCloudAuth(async_get_clientsession(self.hass), region)
                try:
                    tokens = await auth.async_login_password(email, password)
                except VerificationCodeRequired:
                    self._pending_options = options
                    self._pending_email = email
                    self._pending_region = region
                    self._pending_cloud_reauthentication = True
                    return await self.async_step_cloud_code()
                except BambuCloudAuthError:
                    errors["base"] = "invalid_auth"
                except Exception:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title="",
                        data=self._with_tokens(
                            self._reauthentication_options(email, region), tokens,
                            preserve_profile_sync=True,
                        ),
                    )
                finally:
                    password = ""
                    password_input = ""
        return self.async_show_form(
            step_id="cloud_reauthenticate",
            data_schema=vol.Schema({
                vol.Required(CONF_CLOUD_EMAIL, default=email): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
                ),
                vol.Required(CONF_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Required(CONF_CLOUD_REGION, default=region): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[REGION_GLOBAL, REGION_CHINA],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            errors=errors,
        )

    async def async_step_cloud_code(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        if self._pending_options is None or not self._pending_email:
            return self.async_abort(reason="cloud_login_expired")

        errors: dict[str, str] = {}
        if user_input is not None:
            code = str(user_input.get(CONF_VERIFICATION_CODE, "")).strip()
            auth = BambuCloudAuth(
                async_get_clientsession(self.hass),
                self._pending_region,
            )
            try:
                tokens = await auth.async_login_code(
                    self._pending_email,
                    code,
                )
            except BambuCloudAuthError:
                _LOGGER.exception("Studio Bambu verification-code login failed")
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected Studio verification-code error")
                errors["base"] = "cannot_connect"
            else:
                login_options = (
                    self._reauthentication_options(self._pending_email, self._pending_region)
                    if self._pending_cloud_reauthentication else self._pending_options
                )
                options = self._with_tokens(
                    login_options, tokens,
                    preserve_profile_sync=self._pending_cloud_reauthentication,
                )
                self._pending_options = None
                self._pending_email = ""
                self._pending_cloud_reauthentication = False
                return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="cloud_code",
            data_schema=vol.Schema({
                vol.Required(CONF_VERIFICATION_CODE): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                    )
                )
            }),
            errors=errors,
        )
