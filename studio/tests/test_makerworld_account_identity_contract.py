"""Account-scoped pagination and exact profile binding; synthetic I/O only."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from tests.test_makerworld_transfer_contract import modules, load, COMPONENT, setup_runtime, Response, Session, model_archive

def context(modules, monkeypatch, responses=()):
    runtime, transfer, session = setup_runtime(modules, monkeypatch, responses)
    monkeypatch.setattr(modules[0], "async_get_clientsession", lambda _: session)
    return runtime, transfer, session, runtime.hass.config_entries.async_entries("ultimate_3d_studio")[0]

def payload(model="US3575d30b9f913b", profile="profile-A", instance="instance-A", design="123"):
    return {"data":{"designId":design,"modelId":model,"title":"Synthetic fixture",
        "instances":[{"instanceId":instance,"profileId":profile,"designId":design,"title":"Fixture profile"}]}}

def adapter_for(modules, monkeypatch):
    return load(modules[0].__name__.rsplit(".",1)[0]+".makerworld_download", COMPONENT/"makerworld_download.py", monkeypatch)

@pytest.mark.parametrize("change", ["credential","region","logout"])
def test_cached_search_requires_current_account(modules, monkeypatch, change):
    runtime, _, _, entry = context(modules,monkeypatch)
    calls=[]
    async def fake(term,offset,limit):
        calls.append((entry.options.copy(),offset))
        return [{"id":str(len(calls)),"tags":[]}],"fixture",False
    runtime._search_page=fake
    async def run():
        assert (await runtime.async_browse(query="part"))["items"][0]["id"]=="1"
        if change=="credential": entry.options["cloud_access_token"]="SECOND-SYNTHETIC"
        if change=="region": entry.options["cloud_region"]="china"
        if change=="logout":
            entry.options.clear()
            with pytest.raises(modules[0].MakerWorldError):
                await runtime.async_browse(query="part")
            return
        assert (await runtime.async_browse(query="part"))["items"][0]["id"]=="2"
    asyncio.run(run())
    assert len(calls)==(1 if change=="logout" else 2)

def test_account_change_during_search_discards_old_response(modules,monkeypatch):
    runtime, _, _, entry=context(modules,monkeypatch)
    entered=asyncio.Event(); release=asyncio.Event()
    async def fake(*args):
        entered.set();await release.wait()
        return [{"id":"OLD"}],"fixture",False
    runtime._search_page=fake
    async def run():
        task=asyncio.create_task(runtime.async_browse(query="part"))
        await entered.wait();entry.options["cloud_access_token"]="SECOND-SYNTHETIC";release.set()
        with pytest.raises(modules[0].MakerWorldRequestError) as error: await task
        assert error.value.code=="makerworld_account_changed"
    asyncio.run(run())

def test_parallel_search_does_not_skip_upstream_page(modules,monkeypatch):
    runtime, _, _, _=context(modules,monkeypatch)
    calls=[]
    async def fake(term,offset,limit):
        calls.append(offset);await asyncio.sleep(0)
        return [{"id":str(i)} for i in range(offset,offset+60)],"fixture",True
    runtime._search_page=fake
    async def run():
        await asyncio.gather(runtime.async_browse(query="part",limit=24),runtime.async_browse(query="part",limit=24))
        next_page=await runtime.async_browse(query="part",offset=60,limit=24)
        assert [x["id"] for x in next_page["items"]]==[str(i) for i in range(60,84)]
    asyncio.run(run());assert calls==[0,60]

def test_cached_result_is_not_mutable_by_consumer(modules,monkeypatch):
    runtime, _, _, _=context(modules,monkeypatch)
    runtime._search_page=AsyncMock(return_value=([{"id":"1","tags":["original"]}],"fixture",False))
    async def run():
        first=await runtime.async_browse(query="part")
        first["items"][0]["tags"].append("changed");first["items"][0]["id"]="changed"
        second=await runtime.async_browse(query="part")
        assert second["items"]==[{"id":"1","tags":["original"]}]
    asyncio.run(run())

def test_cancelled_page_releases_lock_without_advancing(modules,monkeypatch):
    runtime, _, _, _=context(modules,monkeypatch)
    entered=asyncio.Event();calls=[]
    async def fake(term,offset,limit):
        calls.append(offset)
        if len(calls)==1: entered.set();await asyncio.Event().wait()
        return [{"id":"1"}],"fixture",False
    runtime._search_page=fake
    async def run():
        task=asyncio.create_task(runtime.async_browse(query="part"));await entered.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        result=await asyncio.wait_for(runtime.async_browse(query="part"),2)
        assert result["items"][0]["id"]=="1"
    asyncio.run(run());assert calls==[0,0]

@pytest.mark.parametrize("foreign", [
 {"data":{"designId":"999","modelId":"ForeignModel","title":"Wrong"}},
 {"data":{"designId":"123","title":"Right","recommendations":[{"designId":"999","modelId":"ForeignModel","title":"Wrong"}]}},
])
def test_model_resolution_never_uses_foreign_design_or_recommendation(modules,monkeypatch,foreign):
    runtime,_,_,_=context(modules,monkeypatch)
    runtime._json=AsyncMock(return_value=foreign)
    with pytest.raises(modules[0].MakerWorldError):
        asyncio.run(runtime._resolve_model_id("123",""))

def test_profile_binding_uses_selected_design_and_real_profile_id(modules,monkeypatch):
    runtime,_,_,_=context(modules,monkeypatch)
    adapter=adapter_for(modules,monkeypatch)
    adapter.remember_design_payload(payload(),"123",runtime=runtime)
    runtime.async_download_instance=AsyncMock(return_value=b"fixture")
    assert asyncio.run(adapter.async_download_instance(runtime,"instance-A"))==b"fixture"
    runtime.async_download_instance.assert_awaited_once_with("instance-A",design_id="123",profile_id="profile-A",model_id="US3575d30b9f913b")

@pytest.mark.parametrize("change",["credential","region","logout"])
def test_profile_binding_cannot_survive_account_change(modules,monkeypatch,change):
    runtime,_,_,entry=context(modules,monkeypatch)
    adapter=adapter_for(modules,monkeypatch)
    adapter.remember_design_payload(payload(),"123",runtime=runtime)
    if change=="credential": entry.options["cloud_access_token"]="SECOND-SYNTHETIC"
    if change=="region": entry.options["cloud_region"]="china"
    if change=="logout": entry.options.clear()
    runtime.async_download_instance=AsyncMock(return_value=b"unexpected")
    with pytest.raises(modules[0].MakerWorldError):
        asyncio.run(adapter.async_download_instance(runtime,"instance-A"))
    runtime.async_download_instance.assert_not_awaited()

def test_profile_binding_is_not_shared_between_runtime_instances(modules,monkeypatch):
    first,_,_,_=context(modules,monkeypatch)
    second,_,_,_=context(modules,monkeypatch)
    adapter=adapter_for(modules,monkeypatch)
    adapter.remember_design_payload(payload(),"123",runtime=first)
    second.async_download_instance=AsyncMock()
    with pytest.raises(modules[0].MakerWorldError):
        asyncio.run(adapter.async_download_instance(second,"instance-A"))
    second.async_download_instance.assert_not_awaited()

@pytest.mark.parametrize("field,value",[("design_id","999"),("profile_id","wrong"),("model_id","OtherModel")])
def test_explicit_download_rejects_cross_bound_identity_before_network(modules,monkeypatch,field,value):
    runtime,_,session,_=context(modules,monkeypatch)
    adapter=adapter_for(modules,monkeypatch);adapter.remember_design_payload(payload(),"123",runtime=runtime)
    kwargs={"design_id":"123","profile_id":"profile-A","model_id":"US3575d30b9f913b"};kwargs[field]=value
    runtime._signed_download=AsyncMock(return_value=b"unexpected")
    with pytest.raises(modules[0].MakerWorldError):
        asyncio.run(runtime.async_download_instance("instance-A",**kwargs))
    runtime._signed_download.assert_not_awaited();assert session.calls==[]

@pytest.mark.parametrize("envelope",["data","result","profile","file"])
def test_nested_manifest_conflict_cannot_reach_storage(modules,monkeypatch,envelope):
    body={envelope:{"profileId":"wrong","url":"https://makerworld.bblmw.com/a.3mf"}}
    runtime,transfer,session,_=context(modules,monkeypatch,[Response(body=json.dumps(body).encode()),Response(body=model_archive())])
    adapter=adapter_for(modules,monkeypatch);adapter.remember_design_payload(payload(),"123",runtime=runtime)
    with pytest.raises(transfer.MakerWorldTransferError) as error:
        asyncio.run(runtime.async_download_instance("instance-A",design_id="123",profile_id="profile-A",model_id="US3575d30b9f913b"))
    assert error.value.code=="makerworld_profile_mismatch" and len(session.calls)==1

def test_download_account_change_between_manifest_and_storage_stops(modules,monkeypatch):
    runtime,transfer,_,entry=context(modules,monkeypatch)
    adapter=adapter_for(modules,monkeypatch);adapter.remember_design_payload(payload(),"123",runtime=runtime)
    class Switch(Response):
        async def __aexit__(self,*args):
            await super().__aexit__(*args);entry.options["cloud_access_token"]="SECOND-SYNTHETIC"
    session=Session([Switch(body=b'{"url":"https://makerworld.bblmw.com/a.3mf"}'),Response(body=model_archive())])
    monkeypatch.setattr(transfer,"async_get_clientsession",lambda _:session)
    with pytest.raises(modules[0].MakerWorldRequestError) as error:
        asyncio.run(runtime.async_download_instance("instance-A",design_id="123",profile_id="profile-A",model_id="US3575d30b9f913b"))
    assert error.value.code=="makerworld_account_changed" and len(session.calls)==1

def test_complete_detail_cannot_return_data_after_account_switch(modules,monkeypatch):
    runtime,_,_,entry=context(modules,monkeypatch)
    detail=load(modules[0].__name__.rsplit(".",1)[0]+".makerworld_detail",COMPONENT/"makerworld_detail.py",monkeypatch)
    async def primary(path,params):
        if "design-service/design/" in path:return payload()
        entry.options["cloud_access_token"]="SECOND-SYNTHETIC"
        raise modules[0].MakerWorldRequestError("fixture","fixture",401)
    runtime._json=primary
    with pytest.raises(modules[0].MakerWorldRequestError) as error:
        asyncio.run(runtime.async_detail("123"))
    assert error.value.code=="makerworld_account_changed"
    assert runtime._request_account.get() is None

def test_unresolved_download_loads_selected_detail_then_exact_profile(modules,monkeypatch):
    runtime,_,session,_=context(modules,monkeypatch,[Response(body=b'{"url":"https://makerworld.bblmw.com/a.3mf"}'),Response(body=model_archive())])
    runtime._json=AsyncMock(return_value=payload())
    assert asyncio.run(runtime.async_download_instance("instance-A",design_id="123",profile_id="profile-A"))==model_archive()
    assert runtime._json.await_count==1
    assert session.calls[0][1]["params"]=={"model_id":"US3575d30b9f913b"}

def test_foreign_profile_is_not_bound_to_selected_design(modules,monkeypatch):
    runtime,_,_,_=context(modules,monkeypatch)
    adapter=adapter_for(modules,monkeypatch)
    value=payload()
    value["data"]["instances"][0]["designId"]="999"
    assert adapter.remember_design_payload(value,"123",runtime=runtime)==0
    runtime.async_download_instance=AsyncMock()
    with pytest.raises(modules[0].MakerWorldError):
        asyncio.run(adapter.async_download_instance(runtime,"instance-A"))
    runtime.async_download_instance.assert_not_awaited()


@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_instance_with_conflicting_profile_never_creates_a_binding(modules, monkeypatch, reverse):
    runtime, _, _, _ = context(modules, monkeypatch)
    adapter = adapter_for(modules, monkeypatch)
    before = dict(runtime._profile_bindings)
    value = payload()
    other = dict(value["data"]["instances"][0])
    other["profileId"] = "profile-B"
    value["data"]["instances"].append(other)
    if reverse:
        value["data"]["instances"].reverse()
    with pytest.raises(modules[0].MakerWorldError):
        adapter.remember_design_payload(value, "123", runtime=runtime)
    assert all(key[0] != "123" for key in runtime._profile_bindings)
    assert dict(runtime._profile_bindings) == before


def test_invalid_detail_refresh_revokes_the_previous_design_binding(modules, monkeypatch):
    runtime, _, _, _ = context(modules, monkeypatch)
    adapter = adapter_for(modules, monkeypatch)
    assert adapter.remember_design_payload(payload(), "123", runtime=runtime) == 1
    with pytest.raises(modules[0].MakerWorldError):
        adapter.remember_design_payload({"data":{"designId":"999","title":"Foreign"}}, "123", runtime=runtime)
    runtime.async_download_instance = AsyncMock()
    with pytest.raises(modules[0].MakerWorldError):
        asyncio.run(adapter.async_download_instance(runtime, "instance-A"))
    runtime.async_download_instance.assert_not_awaited()


def test_repeated_identical_profile_binding_is_unambiguous(modules, monkeypatch):
    runtime, _, _, _ = context(modules, monkeypatch)
    adapter = adapter_for(modules, monkeypatch)
    value = payload()
    value["data"]["instances"].append(dict(value["data"]["instances"][0]))
    assert adapter.remember_design_payload(value, "123", runtime=runtime) == 1
    runtime.async_download_instance = AsyncMock(return_value=b"fixture")
    assert asyncio.run(adapter.async_download_instance(runtime, "instance-A")) == b"fixture"
    runtime.async_download_instance.assert_awaited_once_with("instance-A", design_id="123", profile_id="profile-A", model_id="US3575d30b9f913b")
