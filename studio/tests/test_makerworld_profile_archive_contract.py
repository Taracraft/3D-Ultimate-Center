"""P2 provider manifest and archive integrity, actual code with synthetic bytes."""
import asyncio,json,struct,zipfile
from io import BytesIO
import pytest
from tests.test_makerworld_transfer_contract import modules,setup_runtime,Response,model_archive,invoke

def stored_archive():
    s=BytesIO()
    with zipfile.ZipFile(s,"w",zipfile.ZIP_STORED) as z:
        z.writestr("[Content_Types].xml","<Types/>")
        z.writestr("3D/3dmodel.model","<model><resources/><build/></model>")
        z.writestr("Metadata/project_settings.config",'{"filament_colour":["#000000","#FFFFFF"]}')
    return s.getvalue()

def mutate_member(raw,name,mutation):
    with zipfile.ZipFile(BytesIO(raw)) as z: entry=z.getinfo(name)
    p=entry.header_offset
    filename_length,extra_length=struct.unpack_from("<HH",raw,p+26)
    offset=p+30+filename_length+extra_length
    out=bytearray(raw);mutation(out,offset,entry)
    return bytes(out)

@pytest.mark.parametrize("member",["[Content_Types].xml","3D/3dmodel.model","Metadata/project_settings.config"])
def test_corrupted_member_crc_is_rejected_before_handoff(modules,member):
    raw=mutate_member(stored_archive(),member,lambda out,pos,entry:out.__setitem__(pos,out[pos]^1))
    with pytest.raises(modules[1].MakerWorldTransferError) as e:modules[1].validate_3mf(raw)
    assert e.value.code=="makerworld_invalid_3mf"

def test_unsupported_archive_compression_is_classified(modules):
    out=bytearray(stored_archive())
    with zipfile.ZipFile(BytesIO(out)) as z:entry=z.getinfo("3D/3dmodel.model")
    struct.pack_into("<H",out,entry.header_offset+8,99)
    p=out.index(b"PK\x01\x02")
    while p<len(out)-4 and out[p:p+4]==b"PK\x01\x02":
        fl,el,cl=struct.unpack_from("<HHH",out,p+28)
        if bytes(out[p+46:p+46+fl])==b"3D/3dmodel.model":struct.pack_into("<H",out,p+10,99);break
        p+=46+fl+el+cl
    with pytest.raises(modules[1].MakerWorldTransferError) as e:modules[1].validate_3mf(bytes(out))
    assert e.value.code=="makerworld_invalid_3mf"

@pytest.mark.parametrize("compression",[zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED])
def test_valid_archive_is_byte_identical_including_colors_and_auxiliary_models(modules,compression):
    s=BytesIO()
    with zipfile.ZipFile(s,"w",compression) as z:
        z.writestr("[Content_Types].xml","<Types/>")
        z.writestr("3D/3dmodel.model","<model/>")
        z.writestr("3D/Objects/object_1.model","<model/>")
        z.writestr("Metadata/project_settings.config",'{"filament_colour":["#000000","#FFFFFF"]}')
        z.writestr("Auxiliaries/picture.png",bytes(range(255))*400)
    raw=s.getvalue();assert modules[1].validate_3mf(raw)==raw

@pytest.mark.parametrize("wrapper",["data","result","profile","file"])
@pytest.mark.parametrize("alias",["url","downloadUrl","download_url","signedUrl","signed_url","fileUrl","file_url","presignedUrl","presigned_url"])
def test_provider_envelope_and_url_alias_retain_exact_profile_and_signed_url(modules,monkeypatch,wrapper,alias):
    url="https://makerworld.bblmw.com/a.3mf?x=a%2Fb&x=%2B"
    manifest={wrapper:{"profileId":"1034162562","modelId":"US3575d30b9f913b",alias:url}}
    raw=model_archive()
    runtime,_,session=setup_runtime(modules,monkeypatch,[Response(body=json.dumps(manifest).encode()),Response(body=raw)])
    assert invoke(runtime)==raw
    assert session.calls[-1][0]==url and "Authorization" not in session.calls[-1][1]["headers"]

@pytest.mark.parametrize("body",[
 {"url":"https://makerworld.bblmw.com/a","file":{"url":"https://makerworld.bblmw.com/b"}},
 {"url":"https://makerworld.bblmw.com/a","downloadUrl":"https://makerworld.bblmw.com/b"},
 {"profile":{"url":"https://makerworld.bblmw.com/a"},"result":{"url":"https://makerworld.bblmw.com/b"}},
])
def test_conflicting_manifest_urls_do_not_select_first_or_reach_storage(modules,monkeypatch,body):
    runtime,transfer,session=setup_runtime(modules,monkeypatch,[Response(body=json.dumps(body).encode()),Response(body=model_archive())])
    with pytest.raises(transfer.MakerWorldTransferError) as e:invoke(runtime)
    assert e.value.code=="makerworld_manifest_ambiguous" and len(session.calls)==1

@pytest.mark.parametrize("wrapper",["data","result","profile","file"])
def test_explicit_foreign_design_manifest_is_rejected(modules,monkeypatch,wrapper):
    body={wrapper:{"designId":"999","url":"https://makerworld.bblmw.com/a"}}
    runtime,transfer,session=setup_runtime(modules,monkeypatch,[Response(body=json.dumps(body).encode()),Response(body=model_archive())])
    with pytest.raises(transfer.MakerWorldTransferError) as e:invoke(runtime)
    assert e.value.code=="makerworld_profile_mismatch" and len(session.calls)==1

@pytest.mark.parametrize("raw",[
 b'{"profileId":"WRONG","profileId":"1034162562","url":"https://makerworld.bblmw.com/a"}',
 b'{"url":"https://makerworld.bblmw.com/wrong","url":"https://makerworld.bblmw.com/a"}',
 b'{"data":{"modelId":"WRONG","modelId":"US3575d30b9f913b","url":"https://makerworld.bblmw.com/a"}}',
])
def test_duplicate_json_keys_are_not_silently_overwritten(modules,monkeypatch,raw):
    runtime,transfer,session=setup_runtime(modules,monkeypatch,[Response(body=raw),Response(body=model_archive())])
    with pytest.raises(transfer.MakerWorldTransferError) as e:invoke(runtime)
    assert e.value.code=="makerworld_manifest_invalid" and len(session.calls)==1

def test_repeated_same_signed_url_is_unambiguous_and_media_is_ignored(modules,monkeypatch):
    url="https://makerworld.bblmw.com/a"
    body={"url":url,"data":{"url":url},"images":[{"url":"https://makerworld.bblmw.com/photo"}]}
    raw=stored_archive()
    runtime,_,session=setup_runtime(modules,monkeypatch,[Response(body=json.dumps(body).encode()),Response(body=raw)])
    assert invoke(runtime)==raw and session.calls[-1][0]==url

def test_corrupt_download_closes_both_responses_and_never_returns_success(modules,monkeypatch):
    corrupt=mutate_member(stored_archive(),"3D/3dmodel.model",lambda out,pos,entry:out.__setitem__(pos,out[pos]^1))
    responses=[Response(body=b'{"url":"https://makerworld.bblmw.com/a"}'),Response(body=corrupt)]
    runtime,transfer,session=setup_runtime(modules,monkeypatch,responses)
    with pytest.raises(transfer.MakerWorldTransferError) as e:invoke(runtime)
    assert e.value.code=="makerworld_invalid_3mf" and len(session.calls)==2
    assert all(response.closed for response in responses)
