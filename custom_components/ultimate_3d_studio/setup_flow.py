"""Small guided setup steps; each save does what its form says."""
from __future__ import annotations
from functools import partial
import voluptuous as vol
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.const import CONF_PASSWORD
from .const import (
    CONF_LAN_ENABLED, CONF_PRINTER_NAME, CONF_HOST, CONF_SERIAL, CONF_ACCESS_CODE,
    CONF_TLS_INSECURE, DEFAULT_TLS_INSECURE, DEFAULT_PRINTER_NAME,
    CONF_SLICER_ENABLED, CONF_SLICER_BASE_URL, CONF_SLICER_API_SECRET,
    CONF_CLOUD_ENABLED, CONF_CLOUD_PROFILE_SYNC, CONF_CLOUD_EMAIL, CONF_CLOUD_REGION,
    CONF_CLOUD_ACCESS_TOKEN, CONF_CLOUD_REFRESH_TOKEN, CONF_CLOUD_UID,
    REGION_GLOBAL, REGION_CHINA,
)
from .slicer_connection_settings import normalize_slicer_base_url, validate_slicer_api_secret, SlicerConnectionSettingsError
from .slicer_connection_probe import async_probe_slicer_connection, SlicerConnectionProbeError
from .bambu_cloud_auth import BambuCloudAuth, BambuCloudAuthError, VerificationCodeRequired
from .setup_seed import read_setup_seed
from .setup_mqtt import probe_mqtt, MqttSetupError

CONF_DASHBOARD_AUTO = 'dashboard_auto'
PASSWORD = selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))

class GuidedSetupMixin:
    _guided_options = None
    _guided_continuous = False
    _guided_candidates = None
    _guided_pending = None

    async def _guided_current(self):
        if self._guided_options is None:
            entry = getattr(self, 'config_entry', None)
            self._guided_options = ({**entry.data, **entry.options} if entry else {})
            if not entry:
                seed = await self.hass.async_add_executor_job(read_setup_seed, self.hass.config.config_dir)
                self._guided_options.update(seed)
        return self._guided_options

    def _guided_store(self, values):
        self._guided_options.update(values)
        self._guided_changes = {**(getattr(self, '_guided_changes', None) or {}), **values}

    def _guided_result(self):
        entry = getattr(self, 'config_entry', None)
        if entry is None:
            return dict(self._guided_options)
        return {**entry.data, **entry.options, **(getattr(self, '_guided_changes', None) or {})}

    async def _guided_next(self, step):
        if self._guided_continuous:
            return await getattr(self, 'async_step_' + step)()
        return self.async_create_entry(title='', data=self._guided_result())

    async def async_step_setup_printer(self, user_input=None):
        cfg = await self._guided_current()
        draft = getattr(self, '_guided_printer_draft', None) or {}
        errors = {}
        if user_input is not None:
            enabled = user_input.get(CONF_LAN_ENABLED, False) is True
            chosen = str(user_input.get('discovered_printer', 'manual'))
            candidate = (self._guided_candidates or {}).get(chosen, {})
            values = {
                CONF_LAN_ENABLED: enabled,
                CONF_PRINTER_NAME: str(user_input.get(CONF_PRINTER_NAME, '')).strip() or candidate.get('name') or DEFAULT_PRINTER_NAME,
                CONF_HOST: str(user_input.get(CONF_HOST, '')).strip() or candidate.get('host') or str(cfg.get(CONF_HOST, '')).strip(),
                CONF_SERIAL: str(user_input.get(CONF_SERIAL, '')).strip() or candidate.get('serial') or str(cfg.get(CONF_SERIAL, '')).strip(),
                CONF_ACCESS_CODE: str(user_input.get(CONF_ACCESS_CODE) or draft.get(CONF_ACCESS_CODE) or cfg.get(CONF_ACCESS_CODE, '')).strip(),
                CONF_TLS_INSECURE: user_input.get(CONF_TLS_INSECURE, cfg.get(CONF_TLS_INSECURE, DEFAULT_TLS_INSECURE)) is True,
            }
            if enabled:
                errors = {key: 'required' for key in (CONF_HOST,CONF_SERIAL,CONF_ACCESS_CODE) if not values[key]}
            self._guided_printer_draft = values
            if enabled and not errors and user_input.get('verify_mqtt', False):
                try:
                    await self.hass.async_add_executor_job(partial(probe_mqtt, values[CONF_HOST], values[CONF_SERIAL],
                        values[CONF_ACCESS_CODE], values[CONF_TLS_INSECURE]))
                except MqttSetupError as exc:
                    errors['base'] = str(exc)
            if not errors:
                self._guided_store(values)
                self._guided_printer_draft = None
                return await self._guided_next('setup_slicer')
        if self._guided_candidates is None:
            from .discovery import discover
            try:
                found = await self.hass.async_add_executor_job(discover)
                self._guided_candidates = {str(i): p.as_dict() for i,p in enumerate(found)}
            except OSError:
                self._guided_candidates = {}
        shown = {**cfg, **(getattr(self, '_guided_printer_draft', None) or {})}
        fields = {vol.Required(CONF_LAN_ENABLED, default=bool(shown.get(CONF_LAN_ENABLED, self._guided_continuous))): bool}
        if self._guided_candidates:
            fields[vol.Optional('discovered_printer', default='manual')] = selector.SelectSelector(selector.SelectSelectorConfig(
                options=[{'value':'manual','label':'Manuell / Manual'}]+[
                    {'value':key,'label':str(p.get('name') or 'Bambu')+' ('+str(p.get('host',''))+')'} for key,p in self._guided_candidates.items()],
                mode=selector.SelectSelectorMode.DROPDOWN))
        fields[vol.Required('verify_mqtt', default=True)] = bool
        fields.update({
            vol.Optional(CONF_PRINTER_NAME, default=str(shown.get(CONF_PRINTER_NAME, DEFAULT_PRINTER_NAME))): str,
            vol.Optional(CONF_HOST, default=str(shown.get(CONF_HOST, ''))): str,
            vol.Optional(CONF_SERIAL, default=str(shown.get(CONF_SERIAL, ''))): str,
            vol.Optional(CONF_ACCESS_CODE): PASSWORD,
            vol.Required(CONF_TLS_INSECURE, default=bool(shown.get(CONF_TLS_INSECURE, DEFAULT_TLS_INSECURE))): bool,
        })
        return self.async_show_form(step_id='setup_printer', data_schema=vol.Schema(fields), errors=errors,
            description_placeholders={'code_status':'vorhanden / present' if shown.get(CONF_ACCESS_CODE) else 'nicht vorhanden / missing',
                                      'discovery_count':str(len(self._guided_candidates))})

    async def async_step_setup_slicer(self, user_input=None):
        cfg = await self._guided_current()
        errors = {}
        if user_input is not None:
            enabled = user_input.get(CONF_SLICER_ENABLED, False) is True
            values = {CONF_SLICER_ENABLED:enabled,
                CONF_SLICER_BASE_URL:str(user_input.get(CONF_SLICER_BASE_URL, cfg.get(CONF_SLICER_BASE_URL,''))).strip(),
                CONF_SLICER_API_SECRET:str(user_input.get(CONF_SLICER_API_SECRET) or cfg.get(CONF_SLICER_API_SECRET,''))}
            if enabled:
                try:
                    values[CONF_SLICER_BASE_URL] = normalize_slicer_base_url(values[CONF_SLICER_BASE_URL])
                    validate_slicer_api_secret(values[CONF_SLICER_API_SECRET])
                    if user_input.get('verify_connection', True):
                        await async_probe_slicer_connection(async_get_clientsession(self.hass),
                            values[CONF_SLICER_BASE_URL], values[CONF_SLICER_API_SECRET])
                except (SlicerConnectionSettingsError, SlicerConnectionProbeError) as exc:
                    errors['base'] = str(exc)
            if not errors:
                self._guided_store(values)
                return await self._guided_next('setup_account')
        return self.async_show_form(step_id='setup_slicer', data_schema=vol.Schema({
            vol.Required(CONF_SLICER_ENABLED, default=bool(cfg.get(CONF_SLICER_ENABLED, False))):bool,
            vol.Optional(CONF_SLICER_BASE_URL, default=str(cfg.get(CONF_SLICER_BASE_URL,''))):str,
            vol.Optional(CONF_SLICER_API_SECRET):PASSWORD,
            vol.Required('verify_connection',default=True):bool,
        }), errors=errors, description_placeholders={
            'secret_status':'vorbereitet / present' if cfg.get(CONF_SLICER_API_SECRET) else 'nicht vorhanden / missing'})

    async def async_step_setup_account(self, user_input=None):
        cfg = await self._guided_current()
        errors = {}
        if user_input is not None:
            enabled = user_input.get(CONF_CLOUD_ENABLED, False) is True
            values = {CONF_CLOUD_ENABLED:enabled,
                CONF_CLOUD_PROFILE_SYNC:user_input.get(CONF_CLOUD_PROFILE_SYNC,False) is True,
                CONF_CLOUD_EMAIL:str(user_input.get(CONF_CLOUD_EMAIL,cfg.get(CONF_CLOUD_EMAIL,''))).strip(),
                CONF_CLOUD_REGION:str(user_input.get(CONF_CLOUD_REGION,cfg.get(CONF_CLOUD_REGION,REGION_GLOBAL)))}
            password = str(user_input.get(CONF_PASSWORD) or '')
            if enabled and (password or not cfg.get(CONF_CLOUD_ACCESS_TOKEN)):
                if not values[CONF_CLOUD_EMAIL] or not password:
                    errors['base'] = 'invalid_auth'
                else:
                    auth = BambuCloudAuth(async_get_clientsession(self.hass), values[CONF_CLOUD_REGION])
                    try:
                        tokens = await auth.async_login_password(values[CONF_CLOUD_EMAIL],password)
                    except VerificationCodeRequired:
                        self._guided_pending = values
                        return await self.async_step_setup_code()
                    except BambuCloudAuthError:
                        errors['base'] = 'invalid_auth'
                    except Exception:
                        errors['base'] = 'cannot_connect'
                    else:
                        values.update({CONF_CLOUD_ACCESS_TOKEN:tokens.access_token,CONF_CLOUD_REFRESH_TOKEN:tokens.refresh_token,CONF_CLOUD_UID:tokens.uid})
                    finally:
                        password = ''
            if not errors:
                self._guided_store(values)
                return await self._guided_next('setup_dashboard')
        return self.async_show_form(step_id='setup_account',data_schema=vol.Schema({
            vol.Required(CONF_CLOUD_ENABLED,default=bool(cfg.get(CONF_CLOUD_ENABLED,False))):bool,
            vol.Optional(CONF_CLOUD_EMAIL,default=str(cfg.get(CONF_CLOUD_EMAIL,''))):str,
            vol.Optional(CONF_PASSWORD):PASSWORD,
            vol.Required(CONF_CLOUD_REGION,default=str(cfg.get(CONF_CLOUD_REGION,REGION_GLOBAL))):selector.SelectSelector(selector.SelectSelectorConfig(options=[REGION_GLOBAL,REGION_CHINA],mode=selector.SelectSelectorMode.DROPDOWN)),
            vol.Required(CONF_CLOUD_PROFILE_SYNC,default=bool(cfg.get(CONF_CLOUD_PROFILE_SYNC,False))):bool,
        }),errors=errors)

    async def async_step_setup_code(self,user_input=None):
        if self._guided_pending is None:
            return self.async_abort(reason='cloud_login_expired')
        errors={}
        if user_input is not None:
            values=self._guided_pending
            auth=BambuCloudAuth(async_get_clientsession(self.hass),values[CONF_CLOUD_REGION])
            try:
                tokens=await auth.async_login_code(values[CONF_CLOUD_EMAIL],str(user_input.get('verification_code','')).strip())
            except BambuCloudAuthError:
                errors['base']='invalid_auth'
            except Exception:
                errors['base']='cannot_connect'
            else:
                cfg=await self._guided_current()
                self._guided_store(values)
                self._guided_store({CONF_CLOUD_ACCESS_TOKEN:tokens.access_token,CONF_CLOUD_REFRESH_TOKEN:tokens.refresh_token,CONF_CLOUD_UID:tokens.uid})
                self._guided_pending=None
                return await self._guided_next('setup_dashboard')
        return self.async_show_form(step_id='setup_code',data_schema=vol.Schema({vol.Required('verification_code'):str}),errors=errors)

    async def async_step_setup_dashboard(self,user_input=None):
        cfg=await self._guided_current()
        if user_input is not None:
            self._guided_store({CONF_DASHBOARD_AUTO:user_input.get(CONF_DASHBOARD_AUTO,True) is True,
                'hacs_repository_auto':user_input.get('hacs_repository_auto',True) is True})
            title = str(cfg.get('instance_name') or 'Ultimate 3D Studio') if self._guided_continuous else ''
            return self.async_create_entry(title=title,data=self._guided_result())
        return self.async_show_form(step_id='setup_dashboard',data_schema=vol.Schema({
            vol.Required(CONF_DASHBOARD_AUTO,default=bool(cfg.get(CONF_DASHBOARD_AUTO,True))):bool,
            vol.Required('hacs_repository_auto',default=bool(cfg.get('hacs_repository_auto',True))):bool}))
