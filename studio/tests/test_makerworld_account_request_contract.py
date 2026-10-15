"""P2 account/browse/detail contract; synthetic HTTP only, no external requests."""
import asyncio
import json
from types import SimpleNamespace
import pytest
from aiohttp import ClientConnectionError
from tests.test_makerworld_transfer_contract import modules, Response, Session, setup_runtime, model_archive

class JsonResponse(Response):
    async def json(self, **kwargs):
        self.read_calls += 1
        return json.loads(self.body)

def runtime_with(modules, monkeypatch, responses):
    runtime, transfer, session = setup_runtime(modules, monkeypatch, responses)
    monkeypatch.setattr(modules[0], "async_get_clientsession", lambda _: session)
    return runtime, session

@pytest.mark.parametrize("status", [401,403,429,302,307])
@pytest.mark.parametrize("operation", ["search", "later-search", "browse", "detail"])
def test_account_denial_is_classified_once_before_body_parse(modules, monkeypatch, status, operation):
    responses = [JsonResponse(status, b'{"message":"SYNTHETIC-SENSITIVE-URL"}') for _ in range(3)]
    runtime, session = runtime_with(modules, monkeypatch, responses)
    async def run():
        if operation == "search": return await runtime._search_page("part", 0, 60)
        if operation == "later-search": return await runtime._search_page("part", 60, 60)
        if operation == "browse": return await runtime.async_browse()
        return await runtime._json("design-service/design/123", {})
    with pytest.raises(modules[0].MakerWorldError) as caught:
        asyncio.run(run())
    assert getattr(caught.value, "upstream_status", None) == status
    assert "SENSITIVE" not in str(caught.value)
    assert len(session.calls) == 1
    assert responses[0].read_calls == 0
    assert session.calls[0][1].get("allow_redirects") is False

@pytest.mark.parametrize("header", [True, False])
def test_json_limit_counts_actual_bytes(modules, monkeypatch, header):
    response = JsonResponse(body=b'{"content":"' + b"x"*100 + b'"}', length=113 if header else None)
    runtime, session = runtime_with(modules, monkeypatch, [response])
    monkeypatch.setattr(modules[0], "_MAX_JSON_BYTES", 64)
    with pytest.raises(modules[0].MakerWorldError, match="zul"):
        asyncio.run(runtime._json("design-service/design/123", {}))
    assert response.closed and len(session.calls) == 1

@pytest.mark.parametrize("body", [b"<html>PRIVATE</html>", b"\xff", b"{"])
def test_invalid_json_has_stable_sanitized_error(modules, monkeypatch, body):
    runtime, session = runtime_with(modules, monkeypatch, [JsonResponse(body=body)])
    with pytest.raises(modules[0].MakerWorldError) as caught:
        asyncio.run(runtime._json("design-service/design/123", {}))
    assert "PRIVATE" not in str(caught.value)
    assert getattr(caught.value, "code", None) == "makerworld_json_invalid"
    assert len(session.calls) == 1

@pytest.mark.parametrize("failure", [TimeoutError("PRIVATE-URL"), ClientConnectionError("PRIVATE-URL")])
def test_request_failure_is_sanitized_and_not_retried(modules, monkeypatch, failure):
    runtime, session = runtime_with(modules, monkeypatch, [JsonResponse(failure=failure) for _ in range(3)])
    with pytest.raises(modules[0].MakerWorldError) as caught:
        asyncio.run(runtime._search_page("part", 60, 60))
    assert "PRIVATE" not in str(caught.value)
    assert len(session.calls) == 1

def test_unsupported_endpoint_can_use_documented_fallback(modules, monkeypatch):
    good = {"data":{"hits":[{"designId":123,"title":"Fixture","downloadCount":1}]}}
    runtime, session = runtime_with(modules, monkeypatch, [JsonResponse(404,b"<html/>"),JsonResponse(body=json.dumps(good).encode())])
    result = asyncio.run(runtime._search_page("part",0,60))
    assert result[0][0]["id"] == "123" and len(session.calls) == 2
    assert all(options["allow_redirects"] is False for _,options in session.calls)

def test_exact_json_limit_and_unchanged_payload(modules, monkeypatch):
    raw=b'{"result":123}'
    runtime, session = runtime_with(modules, monkeypatch, [JsonResponse(body=raw,length=len(raw))])
    monkeypatch.setattr(modules[0], "_MAX_JSON_BYTES",len(raw))
    assert asyncio.run(runtime._json("design-service/design/123",{})) == {"result":123}

@pytest.mark.parametrize("region", ["invalid", "GLOBAL", "../china"])
def test_invalid_region_does_not_silently_use_global_account(modules, monkeypatch, region):
    runtime, _, session = setup_runtime(modules, monkeypatch, [],region=region)
    with pytest.raises(modules[0].MakerWorldError):
        runtime._account()
    assert not session.calls

from unittest.mock import AsyncMock
from tests.test_makerworld_transfer_contract import load, COMPONENT

def detail_module(modules, monkeypatch):
    return load(modules[0].__name__.rsplit(".", 1)[0]+".makerworld_detail", COMPONENT/"makerworld_detail.py",monkeypatch)

@pytest.mark.parametrize("status", [401,403,429,302,307,None])
def test_primary_detail_does_not_repeat_classified_failure(modules,monkeypatch,status):
    runtime, _ = runtime_with(modules,monkeypatch,[])
    detail=detail_module(modules,monkeypatch)
    failure=modules[0].MakerWorldRequestError("fixture_account_failure","sanitized",status)
    runtime._json=AsyncMock(side_effect=failure)
    with pytest.raises(modules[0].MakerWorldRequestError) as caught:
        asyncio.run(detail.async_load_detail(runtime,"123"))
    assert caught.value is failure and runtime._json.await_count==1

@pytest.mark.parametrize("status", [401,403,429])
@pytest.mark.parametrize("operation", ["_load_comments","_load_recommendations"])
def test_optional_detail_stops_endpoint_sequence_on_account_failure(modules,monkeypatch,status,operation):
    runtime, _ = runtime_with(modules,monkeypatch,[])
    detail=detail_module(modules,monkeypatch)
    failure=modules[0].MakerWorldRequestError("fixture_account_failure","sanitized",status)
    runtime._json=AsyncMock(side_effect=failure)
    with pytest.raises(modules[0].MakerWorldRequestError):
        asyncio.run(getattr(detail,operation)(runtime,"123"))
    assert runtime._json.await_count==1

@pytest.mark.parametrize("status", [401,403,429])
def test_recommendation_fallback_stops_after_account_failure(modules,monkeypatch,status):
    runtime, _ = runtime_with(modules,monkeypatch,[])
    detail=detail_module(modules,monkeypatch)
    runtime.async_browse=AsyncMock(side_effect=modules[0].MakerWorldRequestError("fixture_account_failure","sanitized",status))
    result=asyncio.run(detail._fallback_recommendations(runtime,{"id":"123","tags":["fixture"],"title":"Synthetic Fixture"}))
    assert result==[] and runtime.async_browse.await_count==1

def test_successful_primary_detail_survives_optional_account_failure_without_fanout(modules,monkeypatch):
    runtime, _ = runtime_with(modules,monkeypatch,[])
    detail=detail_module(modules,monkeypatch)
    failure=modules[0].MakerWorldRequestError("fixture_account_failure","sanitized",401)
    good={"data":{"id":123,"title":"Fixture","instances":[]}}
    runtime._json=AsyncMock(side_effect=[good,failure,failure])
    result=asyncio.run(detail.async_load_detail(runtime,"123"))
    assert result["title"]=="Fixture"
    assert result["comments"]==[] and result["recommendations"]==[]
    assert runtime._json.await_count==3
