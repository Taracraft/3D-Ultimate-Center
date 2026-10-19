"""Register this already installed integration through the verified HACS adapter.

No OAuth credentials, download/install call, storage-file editing or Supervisor.
Adapter contract: official HACS 2.0.5 base/repository APIs and stage signals.
"""
from __future__ import annotations
import asyncio
from pathlib import Path

REPOSITORY = 'Taracraft/3D-Ultimate-Center'
SUPPORTED_HACS_VERSION = '2.0.5'

async def async_register_studio_repository(hass):
    from .const import DOMAIN, VERSION
    hacs = hass.data.get('hacs')
    if hacs is None:
        return 'awaiting_hacs_login'
    if str(getattr(getattr(hacs, 'integration', None), 'version', '')) != SUPPORTED_HACS_VERSION:
        return 'unsupported_hacs_version'
    if getattr(getattr(hacs, 'system', None), 'disabled', True) or str(getattr(hacs, 'stage', '')) != 'running':
        return 'awaiting_hacs_ready'
    try:
        async with asyncio.timeout(45):
            repo = hacs.repositories.get_by_full_name(REPOSITORY)
            if repo is None:
                await hacs.async_register_repository(repository_full_name=REPOSITORY, category='integration')
                repo = hacs.repositories.get_by_full_name(REPOSITORY)
            if repo is None:
                return 'repository_not_registered'
            def owns_local_path():
                return (repo.data.domain == DOMAIN and
                        Path(repo.content.path.local).resolve() == Path(__file__).resolve().parent)
            if not await hass.async_add_executor_job(owns_local_path):
                return 'repository_path_mismatch'
            if not repo.data.installed:
                # Same HACS data model used by its own installed-repository handling.
                # This component is already loaded from the verified local path.
                repo.data.installed = True
                repo.data.installed_version = VERSION
                repo.data.new = False
            await hacs.data.async_write()
            return 'registered'
    except Exception:
        return 'repository_registration_failed'

async def async_setup_hacs(hass, entry, enabled):
    if not enabled:
        return
    from .const import DOMAIN
    from homeassistant.core import callback
    from homeassistant.helpers.dispatcher import async_dispatcher_connect
    task = None
    async def perform():
        hass.data.setdefault(DOMAIN, {})['hacs_setup_status'] = await async_register_studio_repository(hass)
    @callback
    def changed(_=None):
        nonlocal task
        if hass.data.get(DOMAIN, {}).get('hacs_setup_status') == 'registered':
            return
        if task is None or task.done():
            task = hass.async_create_task(perform())
    for signal in ('hacs_dispatch_stage', 'hacs_dispatch_status'):
        entry.async_on_unload(async_dispatcher_connect(hass, signal, changed))
    def stop():
        if task is not None and not task.done():
            task.cancel()
    entry.async_on_unload(stop)
    changed()
