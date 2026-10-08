"""Run actual router/view bodies with only HTTP and HA boundaries replaced."""
from __future__ import annotations
import ast
import asyncio
from collections import OrderedDict
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

COMPONENT=Path(__file__).resolve().parents[1]/'deploy/homeassistant/custom_components/ultimate_3d_studio'


def source_nodes(filename,names,scope=None):
    tree=ast.parse((COMPONENT/filename).read_text())
    body=next(n.body for n in tree.body if isinstance(n,ast.ClassDef) and n.name==scope) if scope else tree.body
    return [n for n in body if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]


def execute(nodes,namespace):
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*nodes],type_ignores=[])),'actual-production-body','exec'),namespace)


class Response:
    def __init__(self,status,payload):self.status=status;self.payload=payload
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    async def json(self,**kwargs):return self.payload


class CancelTransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ns={'SlicerServerError':RuntimeError,'SERVER_PREFIX':'server__','re':re,'SERVER_ENDPOINT':'http://worker','ClientTimeout':lambda **kw:kw,'ClientError':ConnectionError,'_COMPLETED_ARTIFACT_CACHE':OrderedDict(sample=b'cached'),'_COMPLETED_METADATA_CACHE':OrderedDict(sample={'test':True})}
        execute(source_nodes('slicer_backend_router.py',{'native_job_id','SlicerCancellationError'})+source_nodes('slicer_backend_router.py',{'async_cancel_job'},'StudioSlicerBackendRouter'),self.ns)
        self.calls=[]

    async def cancel(self,status=200,payload=None,job_id='server__sample'):
        response=Response(status,payload or {'status':'cancelling','cancel_requested':True})
        def post(*args,**kwargs):self.calls.append((args,kwargs));return response
        return await self.ns['async_cancel_job'](SimpleNamespace(session=SimpleNamespace(post=post)),job_id)

    async def test_success_one_post_and_cache_invalidated(self):
        self.assertEqual((await self.cancel())['status'],'cancelling')
        self.assertEqual(len(self.calls),1);self.assertTrue(self.calls[0][0][0].endswith('/jobs/sample/cancel'))
        self.assertEqual(self.ns['_COMPLETED_ARTIFACT_CACHE'],{});self.assertEqual(self.ns['_COMPLETED_METADATA_CACHE'],{})

    async def test_error_statuses_remain_404_409_without_retry(self):
        for status in (404,409):
            with self.subTest(status=status):
                with self.assertRaises(self.ns['SlicerCancellationError']) as raised:await self.cancel(status,{'error':'job_not_terminal'})
                self.assertEqual(raised.exception.status,status)
        self.assertEqual(len(self.calls),2)

    async def test_invalid_and_unconfirmed_reply_fail_closed(self):
        with self.assertRaises(self.ns['SlicerCancellationError']) as invalid:await self.cancel(job_id='other__sample')
        self.assertEqual(invalid.exception.status,400)
        self.assertEqual(self.calls,[])
        with self.assertRaises(self.ns['SlicerCancellationError']):await self.cancel(payload={'status':'completed','cancel_requested':True})
        self.assertIn('sample',self.ns['_COMPLETED_METADATA_CACHE'])

    async def test_timeout_never_retries_post(self):
        calls=[]
        def post(*args,**kwargs):calls.append(1);raise TimeoutError('timeout')
        with self.assertRaises(self.ns['SlicerCancellationError']):
            await self.ns['async_cancel_job'](SimpleNamespace(session=SimpleNamespace(post=post)),'server__sample')
        self.assertEqual(calls,[1])

    async def test_unconfirmed_group_stop_projects_visible_recovery_error(self):
        ns={'SERVER_PREFIX':'server__','BACKEND_SERVER':'server',
            'project_name_from_server_payload':lambda _payload,identifier:identifier,
            '_engine_result_metrics':lambda *_args:{},'_profile_application':lambda *_args:{}}
        execute(source_nodes('slicer_backend_router.py',{'_server_job'}),ns)
        payload={'job_id':'sample','status':'cancelling','cancel_requested':True,
                 'progress':{'requires_recovery':True,'error':'owned_process_group_still_running'}}
        job=ns['_server_job'](payload)
        self.assertEqual(job['status'],'cancelling');self.assertTrue(job['cancel_requested'])
        self.assertIn('Wiederherstellung',job['error']);self.assertIsNone(job['finished_at'])
        payload['progress']={'error':'progress_error'}
        self.assertEqual(ns['_server_job'](payload)['error'],'progress_error')


class Part:
    def __init__(self,name,content,filename=None):self.name=name;self.content=content;self.filename=filename;self.reads=0
    async def read_chunk(self,size):
        self.reads+=1;chunk=self.content[:size];self.content=self.content[size:];return chunk


class BatchContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.created=[];self.validated=[];self.fail_validate=None;self.fail_create=None
        async def prepare(_hass,name,*_args):
            self.validated.append(name)
            if name==self.fail_validate:raise ValueError('unsafe profile')
            return {'catalog':{},'options':{},'target_printer':{},'material_plan':{'assignments':{},'filaments':[]},'selected_process_profile':{},'project_name':name,'material_source_summary':{},'compatibility_contract':{}}
        async def create(*args,**kwargs):
            self.created.append((args[1],kwargs))
            if args[1]==self.fail_create:raise RuntimeError('offline')
            return {'id':args[1],'status':'queued'}
        self.ns={'HomeAssistantView':object,'API_BASE':'/api/studio','VERSION':'test','Path':Path,'json':json,'Any':object,'MAX_BATCH_BYTES':160_000_000,'SlicerServerConfigurationError':ConnectionError,'SlicerServerError':RuntimeError,'web':SimpleNamespace(json_response=lambda body,status=200:(status,body)),'_prepare_plate_job_contract':prepare,'_batch_material_plan_for_model':lambda plan,_bytes:plan,'StudioSlicerBackendRouter':lambda _hass:SimpleNamespace(async_create_plate_job=create)}
        execute(source_nodes('slicer_queue_views.py',{'BatchBodyTooLarge','_read_batch_part','SlicerBatchCreateView'}),self.ns)

    async def batch(self,count=50,extra=None):
        parts=[Part('studio_plate',b'{}'),Part('material_plan',b'{}')]+[Part(f'files_{i}',b'test-3mf',f'model-{i:02}.3mf') for i in range(count)]+(extra or [])
        values=iter(parts)
        async def next_part():return next(values,None)
        reader=SimpleNamespace(next=next_part)
        request=SimpleNamespace(app={'hass':object()},multipart=AsyncMock(return_value=reader))
        reply=await self.ns['SlicerBatchCreateView']().post(request)
        return reply,parts

    async def test_fifty_files_fully_preflight_then_held_creation(self):
        (status,payload),_=await self.batch()
        self.assertEqual(status,200);self.assertEqual(payload['data']['created'],50);self.assertEqual(payload['data']['failed'],0)
        self.assertEqual(len(self.validated),50);self.assertEqual(len(self.created),50)
        self.assertTrue(all(kwargs['manual_release'] for _,kwargs in self.created))

    async def test_51st_file_rejected_before_read_or_any_job_mutation(self):
        (status,_payload),parts=await self.batch(51)
        self.assertEqual(status,413);self.assertEqual(parts[-1].reads,0);self.assertEqual(self.created,[]);self.assertEqual(self.validated,[])

    async def test_profile_failure_creates_zero_jobs(self):
        self.fail_validate='model-49.3mf'
        (status,_),_=await self.batch()
        self.assertEqual(status,400);self.assertEqual(len(self.validated),50);self.assertEqual(self.created,[])

    async def test_partial_transport_failure_returns_precise_counts(self):
        self.fail_create='model-25.3mf'
        (status,payload),_=await self.batch()
        self.assertEqual(status,200);self.assertEqual(payload['data']['created'],49);self.assertEqual(payload['data']['failed'],1)
        self.assertIn('model-25.3mf',payload['data']['errors'][0])

    async def test_cumulative_and_metadata_limits_are_streamed(self):
        self.ns['MAX_BATCH_BYTES']=10
        (status,payload),_=await self.batch(2)
        self.assertEqual(status,413);self.assertEqual(payload['error'],'batch_payload_too_large');self.assertEqual(self.created,[])
        part=Part('metadata',b'a'*2000000)
        with self.assertRaises(self.ns['BatchBodyTooLarge']):await self.ns['_read_batch_part'](part,1_000_000)
        self.assertLess(part.reads,20)


if __name__=='__main__':unittest.main()
