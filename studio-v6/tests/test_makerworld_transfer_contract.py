"""Actual download implementation, synthetic responses, no network or printer I/O."""
from __future__ import annotations

import asyncio
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock
import zipfile

import pytest
from aiohttp import ClientConnectionError

COMPONENT = Path(__file__).resolve().parents[1] / 'deploy/homeassistant/custom_components/ultimate_3d_studio_v6'


def load(name, path, monkeypatch):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def modules(monkeypatch):
    name = 'studio_makerworld_download_contract_tests'
    package = ModuleType(name)
    package.__path__ = [str(COMPONENT)]
    monkeypatch.setitem(sys.modules, name, package)
    for key in ['homeassistant', 'homeassistant.helpers', 'homeassistant.core']:
        if key not in sys.modules:
            value = ModuleType(key)
            value.__path__ = []
            monkeypatch.setitem(sys.modules, key, value)
    monkeypatch.setattr(sys.modules['homeassistant.core'], 'HomeAssistant', object, raising=False)
    client = ModuleType('homeassistant.helpers.aiohttp_client')
    client.async_get_clientsession = lambda _: None
    monkeypatch.setitem(sys.modules, client.__name__, client)
    constants = ModuleType(name + '.const')
    for key, value in {
        'CONF_CLOUD_ACCESS_TOKEN': 'cloud_access_token',
        'CONF_CLOUD_REGION': 'cloud_region',
        'DOMAIN': 'ultimate_3d_studio_v6',
        'REGION_CHINA': 'china',
        'REGION_GLOBAL': 'global',
        'VERSION': '6.0.0-test',
    }.items():
        setattr(constants, key, value)
    monkeypatch.setitem(sys.modules, constants.__name__, constants)
    runtime = load(name + '.makerworld_runtime', COMPONENT / 'makerworld_runtime.py', monkeypatch)
    transfer = load(name + '.makerworld_transfer', COMPONENT / 'makerworld_transfer.py', monkeypatch)
    return runtime, transfer


def model_archive(extra=None):
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr('3D/3dmodel.model', '<model><resources/><build/></model>')
        archive.writestr('Metadata/project_settings.config', '{"filament_colour":["#000000","#FFFFFF"]}')
        for name, value in (extra or {}).items():
            member = zipfile.ZipInfo(name)
            member.filename = name
            member.orig_filename = name
            archive.writestr(member, value)
    return stream.getvalue()


class Response:
    def __init__(self, status=200, body=b'', length=None, failure=None):
        self.status, self.body = status, body
        self.content_length = length
        self.content = self
        self.read_calls = 0
        self.failure = failure
        self.closed = False

    async def __aenter__(self):
        if self.failure:
            raise self.failure
        return self

    async def __aexit__(self, *_):
        self.closed = True

    async def iter_chunked(self, _size):
        self.read_calls += 1
        midpoint = len(self.body) // 2
        yield self.body[:midpoint]
        yield self.body[midpoint:]


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((str(url), kwargs))
        return next(self.responses)


def setup_runtime(modules, monkeypatch, responses, region='global'):
    runtime_module, transfer = modules
    session = Session(responses)
    monkeypatch.setattr(transfer, 'async_get_clientsession', lambda _: session)

    async def executor(function, *args):
        return function(*args)

    entry = SimpleNamespace(data={}, options={'cloud_access_token': 'SYNTHETIC-PRIVATE', 'cloud_region': region})
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_entries=lambda _: [entry]),
                           async_add_executor_job=executor, data={})
    runtime = runtime_module.MakerWorldRuntime(hass)
    runtime._legacy_download = AsyncMock(side_effect=AssertionError('No legacy fallback is allowed'))
    return runtime, transfer, session


def invoke(runtime):
    return asyncio.run(runtime.async_download_instance('3840497', design_id='3376079',
                        profile_id='1034162562', model_id='US3575d30b9f913b'))


@pytest.mark.parametrize('status,code', [
    (401, 'makerworld_account_unauthorized'), (403, 'makerworld_profile_forbidden'),
    (404, 'makerworld_profile_not_found'), (429, 'makerworld_rate_limited'),
    (500, 'makerworld_upstream_error'), (302, 'makerworld_unexpected_redirect'),
])
def test_manifest_denial_is_classified_before_body_parse_and_never_falls_back(modules, monkeypatch, status, code):
    response = Response(status, b'<html>SENSITIVE expired-signed-url</html>')
    runtime, transfer, session = setup_runtime(modules, monkeypatch, [response])
    with pytest.raises(transfer.MakerWorldTransferError) as error:
        invoke(runtime)
    assert error.value.code == code and error.value.upstream_status == status
    assert 'SENSITIVE' not in str(error.value) and 'SYNTHETIC-PRIVATE' not in str(error.value)
    assert len(session.calls) == 1 and response.read_calls == 0 and response.closed
    runtime._legacy_download.assert_not_called()


@pytest.mark.parametrize('region,host', [('global', 'api.bambulab.com'), ('china', 'api.bambulab.cn')])
def test_success_retains_exact_profile_url_archive_and_credentials_boundary(modules, monkeypatch, region, host):
    signed = 'https://s3.us-west-2.amazonaws.com/model.3mf?key=a%2Fb%2Bc&sig=%2B%2F%3D&x=1&x=2'
    archive = model_archive({'3D/Objects/part.model': '<model/>', 'Metadata/plate_1.json': '{"plate":1}'})
    first = Response(body=json.dumps({'url': signed}).encode())
    second = Response(body=archive)
    runtime, _, session = setup_runtime(modules, monkeypatch, [first, second], region)
    result = invoke(runtime)
    assert result == archive and len(session.calls) == 2
    manifest_url, manifest_options = session.calls[0]
    assert manifest_url == f'https://{host}/v1/iot-service/api/user/profile/1034162562'
    assert manifest_options['params'] == {'model_id': 'US3575d30b9f913b'}
    assert manifest_options['headers']['Authorization'] == 'Bearer SYNTHETIC-PRIVATE'
    url, options = session.calls[1]
    assert url == signed
    assert 'Authorization' not in options['headers']
    assert all(not settings['allow_redirects'] for _, settings in session.calls)
    assert first.closed and second.closed
    runtime._legacy_download.assert_not_called()


@pytest.mark.parametrize('status', [401, 403, 404, 429, 307])
def test_storage_errors_do_not_retry_manifest_or_legacy(modules, monkeypatch, status):
    first = Response(body=b'{"url":"https://makerworld.bblmw.com/model.3mf?sig=PRIVATE"}')
    runtime, transfer, session = setup_runtime(modules, monkeypatch, [first, Response(status)])
    with pytest.raises(transfer.MakerWorldTransferError) as error:
        invoke(runtime)
    assert error.value.upstream_status == status
    if status in {401, 403}:
        assert error.value.code == 'makerworld_signed_download_denied'
    assert len(session.calls) == 2 and 'PRIVATE' not in str(error.value)
    runtime._legacy_download.assert_not_called()


@pytest.mark.parametrize('failure,code', [
    (TimeoutError('private-url'), 'makerworld_download_timeout'),
    (ClientConnectionError('secret-url'), 'makerworld_download_connection'),
])
def test_network_errors_remain_sanitized_without_retry(modules, monkeypatch, failure, code):
    runtime, transfer, session = setup_runtime(modules, monkeypatch, [Response(failure=failure)])
    with pytest.raises(transfer.MakerWorldTransferError) as error:
        invoke(runtime)
    assert error.value.code == code and 'url' not in str(error.value)
    assert len(session.calls) == 1
    runtime._legacy_download.assert_not_called()


def test_cancellation_is_not_translated_or_retried(modules, monkeypatch):
    runtime, _, session = setup_runtime(modules, monkeypatch, [Response(failure=asyncio.CancelledError())])
    with pytest.raises(asyncio.CancelledError):
        invoke(runtime)
    assert len(session.calls) == 1
    runtime._legacy_download.assert_not_called()


@pytest.mark.parametrize('value', [
    '', 'http://makerworld.bblmw.com/m.3mf', 'https://127.0.0.1/x',
    'https://makerworld.bblmw.com.evil.example/x', 'https://u:p@makerworld.bblmw.com/x',
    'https://makerworld.bblmw.com:8080/x', 'https://makerworld.bblmw.com/x#fragment',
    'https://makerworld.bblmw.com/x\n', 'https://makerworld.bblmw.com\\evil/x',
    'https://makerworld.bblmw.com:bad/x',
])
def test_unsafe_signed_urls_are_rejected_without_another_request(modules, monkeypatch, value):
    runtime, transfer, session = setup_runtime(modules, monkeypatch, [Response(body=json.dumps({'url': value}).encode())])
    with pytest.raises(transfer.MakerWorldTransferError) as error:
        invoke(runtime)
    assert error.value.code == 'makerworld_download_url_invalid'
    assert len(session.calls) == 1


@pytest.mark.parametrize('payload', [b'<html>success?</html>', b'\xff', b'{'])
def test_invalid_manifest_cannot_reach_file_or_legacy(modules, monkeypatch, payload):
    runtime, transfer, session = setup_runtime(modules, monkeypatch, [Response(body=payload)])
    with pytest.raises(transfer.MakerWorldTransferError) as error:
        invoke(runtime)
    assert error.value.code == 'makerworld_manifest_invalid' and len(session.calls) == 1


@pytest.mark.parametrize('key', ['profile_id', 'profileId', 'model_id', 'modelId'])
def test_mismatched_manifest_identity_is_not_used(modules, monkeypatch, key):
    body = json.dumps({key: 'wrong', 'url': 'https://makerworld.bblmw.com/a'}).encode()
    runtime, transfer, session = setup_runtime(modules, monkeypatch, [Response(body=body)])
    with pytest.raises(transfer.MakerWorldTransferError) as error:
        invoke(runtime)
    assert error.value.code == 'makerworld_profile_mismatch' and len(session.calls) == 1


@pytest.mark.parametrize('header', [True, False])
def test_manifest_size_limit_prevents_download(modules, monkeypatch, header):
    runtime, transfer, session = setup_runtime(modules, monkeypatch, [Response(body=b'x'*80, length=80 if header else None)])
    monkeypatch.setattr(transfer, 'MAX_MANIFEST_BYTES', 64)
    with pytest.raises(transfer.MakerWorldTransferError) as error:
        invoke(runtime)
    assert error.value.code == 'makerworld_response_too_large' and len(session.calls) == 1


@pytest.mark.parametrize('header', [True, False])
def test_download_size_limit_stops_before_archive_validation(modules, monkeypatch, header):
    responses = [Response(body=b'{"url":"https://makerworld.bblmw.com/a"}'),
                 Response(body=b'x'*80, length=80 if header else None)]
    runtime, transfer, session = setup_runtime(modules, monkeypatch, responses)
    monkeypatch.setattr(transfer, 'MAX_DOWNLOAD_BYTES', 64)
    with pytest.raises(transfer.MakerWorldTransferError) as error:
        invoke(runtime)
    assert error.value.code == 'makerworld_response_too_large' and len(session.calls) == 2


@pytest.mark.parametrize('archive', [b'<html/>', b'PK\x03\x04broken', b''])
def test_fake_archives_are_not_returned_as_import_success(modules, monkeypatch, archive):
    responses = [Response(body=b'{"url":"https://makerworld.bblmw.com/a"}'), Response(body=archive)]
    runtime, transfer, _ = setup_runtime(modules, monkeypatch, responses)
    with pytest.raises(transfer.MakerWorldTransferError) as error:
        invoke(runtime)
    assert error.value.code == 'makerworld_invalid_3mf'


@pytest.mark.parametrize('name', ['../escape', '/absolute', '3D/../../escape', 'C:/escape', 'a\\b', 'a//b', 'a/./b'])
def test_unsafe_archive_members_are_rejected(modules, name):
    transfer = modules[1]
    with pytest.raises(transfer.MakerWorldTransferError, match='3MF'):
        transfer.validate_3mf(model_archive({name: 'unsafe'}))


def test_nonmodel_zip_is_not_a_success(modules):
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('picture.png', b'not a model')
    with pytest.raises(modules[1].MakerWorldTransferError):
        modules[1].validate_3mf(stream.getvalue())


def test_archive_budgets_are_not_disabled(modules, monkeypatch):
    transfer = modules[1]
    monkeypatch.setattr(transfer, 'MAX_ARCHIVE_ENTRIES', 1)
    with pytest.raises(transfer.MakerWorldTransferError):
        transfer.validate_3mf(model_archive())
    monkeypatch.setattr(transfer, 'MAX_ARCHIVE_ENTRIES', 10000)
    monkeypatch.setattr(transfer, 'MAX_EXPANDED_BYTES', 1)
    with pytest.raises(transfer.MakerWorldTransferError):
        transfer.validate_3mf(model_archive())


def test_incomplete_identity_has_no_network_side_effect(modules, monkeypatch):
    runtime, _, session = setup_runtime(modules, monkeypatch, [])
    with pytest.raises(modules[0].MakerWorldError, match='zugeordnet'):
        asyncio.run(runtime.async_download_instance('3840497'))
    assert session.calls == []
    runtime._legacy_download.assert_not_called()


@pytest.mark.parametrize('profile', ['../escape', 'with spaces', 'x'*91])
def test_invalid_explicit_profile_is_never_truncated_or_substituted(modules, monkeypatch, profile):
    runtime, _, session = setup_runtime(modules, monkeypatch, [])
    with pytest.raises(modules[0].MakerWorldError):
        asyncio.run(runtime.async_download_instance('3840497', profile_id=profile, design_id='3376079'))
    assert session.calls == []


def test_actual_entrypoint_never_hides_primary_failure_behind_legacy_success(modules, monkeypatch):
    runtime, transfer, _ = setup_runtime(modules, monkeypatch, [])
    primary = transfer.MakerWorldTransferError('makerworld_account_unauthorized', '401 primary', upstream_status=401)
    runtime._signed_download = AsyncMock(side_effect=primary)
    runtime._legacy_download = AsyncMock(return_value=model_archive())
    with pytest.raises(transfer.MakerWorldTransferError) as caught:
        invoke(runtime)
    assert caught.value is primary
    runtime._signed_download.assert_awaited_once()
    runtime._legacy_download.assert_not_called()


def test_legacy_cache_adapter_uses_same_signed_contract(modules, monkeypatch):
    runtime, transfer, session = setup_runtime(modules, monkeypatch, [Response(401, b'<html/>')])
    package = runtime.__class__.__module__.rsplit('.', 1)[0]
    adapter = load(package+'.makerworld_download', COMPONENT/'makerworld_download.py', monkeypatch)
    adapter._INSTANCE_MODEL_IDS['1034162562'] = 'US3575d30b9f913b'
    with pytest.raises(transfer.MakerWorldTransferError) as caught:
        asyncio.run(adapter.async_download_instance(runtime, '1034162562'))
    assert caught.value.code == 'makerworld_account_unauthorized'
    assert len(session.calls) == 1
    runtime._legacy_download.assert_not_called()
