"""Concrete file-archive contract tests using inert fixtures, no engine invocation."""
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_bundle_builder', ROOT/'Slicer-Server/build_engine_bundle.py')
bundle = importlib.util.module_from_spec(spec); spec.loader.exec_module(bundle)

class EngineBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.source = self.base/'source'; self.source.mkdir()
        self.rows = []
        for path, content, role, executable in [('bin/CuraEngine', b'inert test data'*15000, 'engine', True),
             ('resources/definitions/base.def.json', b'{"version":2}', 'profiles', False),
             ('resources/base.json', b'{}', 'resources', False),
             ('licenses/LICENSE', b'Fixture notice, not a real license', 'license', False),
             ('resources/empty', b'', 'resources', False)]:
            p=self.source/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
            self.rows.append(dict(root='payload',source=path,path=path,sha256=bundle.digest(content),bytes=len(content),role=role,executable=executable))
        self.inventory = {'schema':1,'engine':'curaengine','version':'5.0.0-5',
            'upstream_archives':[{'id':'fixture','bytes':123,'sha256':'a'*64}], 'files':self.rows}
        self.roots={'payload':self.source}
    def run_build(self, inventory=None, name='result'):
        return bundle.build(self.inventory if inventory is None else inventory,self.roots,self.base/name)
    def rejects(self, data, code):
        with self.assertRaisesRegex(bundle.BundleError, code):self.run_build(data)
        self.assertFalse((self.base/'result').exists())
    def test_two_binary_archives_deterministic_and_sources_unchanged(self):
        before={p.relative_to(self.source):p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        a=self.run_build(name='a');b=self.run_build(name='b')
        self.assertEqual(a,b);self.assertEqual((self.base/'a/curaengine.tar.gz').read_bytes(),(self.base/'b/curaengine.tar.gz').read_bytes())
        self.assertTrue(a['archive_verified']);self.assertFalse(a['release_approved']);self.assertFalse(a['engine_executed'])
        self.assertEqual(before,{p.relative_to(self.source):p.read_bytes() for p in self.source.rglob('*') if p.is_file()})
        with tarfile.open(self.base/'a/curaengine.tar.gz') as tar:
            self.assertEqual(len(tar.getmembers()),len(self.rows)+1)
            for row in self.rows:self.assertEqual(tar.extractfile(row['path']).read(),before[Path(row['source'])])
    def test_all_three_engine_entrypoints(self):
        for engine,entry in bundle.ENTRIES.items():
            data=deepcopy(self.inventory);data['engine']=engine;data['files'][0]['path']=entry
            r=self.run_build(data,name=engine);self.assertEqual(r['engine'],engine)
    def test_bool_schema_and_sizes_rejected(self):
        for key,value in [('schema',True),('schema',2)]:
            d=deepcopy(self.inventory);d[key]=value
            with self.subTest(key=key,value=value):self.rejects(d,'invalid_schema')
        for value in [True,-1,'2',bundle.MAX_FILE_BYTES+1]:
            d=deepcopy(self.inventory);d['files'][0]['bytes']=value
            with self.subTest(value=value):self.rejects(d,'invalid_size')
    def test_unfixed_version_rejected(self):
        for value in ['latest','main','nightly','1.0\n',True,None]:
            d=deepcopy(self.inventory);d['version']=value
            with self.subTest(value=value):self.rejects(d,'unfixed_version')
    def test_inventory_fields_and_roots_are_exact(self):
        d=deepcopy(self.inventory);d['extra']=True;self.rejects(d,'invalid_inventory')
        with self.assertRaisesRegex(bundle.BundleError,'root_mapping_mismatch'):
            bundle.build(self.inventory,{'other':self.source},self.base/'result')
    def test_paths_absolute_traversal_and_colon_rejected(self):
        for key in ['source','path']:
            for value in ['/absolute','../escape','a/../b','a//b','a\\b','C:/x','a:stream','a\nfile']:
                d=deepcopy(self.inventory);d['files'][1][key]=value
                with self.subTest(key=key,value=value):self.rejects(d,'invalid_path')
    def test_case_and_file_directory_collisions_rejected(self):
        for value in ['resources','RESOURCES/base.json','resources/base.json','bin/CuraEngine/child']:
            d=deepcopy(self.inventory);d['files'][1]['path']=value
            with self.subTest(value=value):self.rejects(d,'conflicting_paths')
    def test_missing_engine_license_resources_or_profiles_rejected(self):
        for role,code in [('engine','invalid_payload'),('license','missing_license'),('profiles','missing_profiles'),('resources','missing_resources')]:
            d=deepcopy(self.inventory);d['files']=[f for f in d['files'] if f['role']!=role]
            with self.subTest(role=role):self.rejects(d,code)
    def test_reserved_manifest_cannot_be_replaced(self):
        d=deepcopy(self.inventory);d['files'][1]['path']=bundle.MANIFEST_NAME;self.rejects(d,'reserved_bundle_path')
    def test_non_engine_executable_not_allowed(self):
        d=deepcopy(self.inventory);d['files'][1]['executable']=True;self.rejects(d,'unexpected_executable')
    def test_wrong_digest_prevents_finished_archive(self):
        d=deepcopy(self.inventory);d['files'][0]['sha256']='0'*64
        with self.assertRaisesRegex(bundle.BundleError,'source_digest_mismatch'):self.run_build(d)
        self.assertFalse((self.base/'result/curaengine.tar.gz').exists())
        self.assertFalse((self.base/'result/BUILD_RESULT.json').exists())
    def test_wrong_size_fails_before_output_creation(self):
        d=deepcopy(self.inventory);d['files'][0]['bytes']+=1;self.rejects(d,'invalid_source_file')
    def test_existing_output_preserved(self):
        p=self.base/'result';p.mkdir();(p/'keep').write_bytes(b'keep')
        with self.assertRaisesRegex(bundle.BundleError,'output_exists'):self.run_build()
        self.assertEqual((p/'keep').read_bytes(),b'keep')
    def test_output_inside_source_rejected(self):
        with self.assertRaisesRegex(bundle.BundleError,'output_inside_source'):
            bundle.build(self.inventory,self.roots,self.source/'result')
    def test_source_symlink_refused(self):
        p=self.source/self.rows[0]['source'];real=self.source/'original';p.rename(real)
        try:p.symlink_to(real)
        except OSError:self.skipTest('symbolic link permission unavailable')
        self.rejects(self.inventory,'linked_local_path')
    def test_source_hardlink_refused(self):
        p=self.source/self.rows[0]['source']
        try:os.link(p,self.source/'hardlink')
        except OSError:self.skipTest('hardlinks unavailable')
        self.rejects(self.inventory,'invalid_source_file')
    def test_source_mutation_during_tar_write_detected(self):
        original=bundle.HashReader.read;changed=False
        def corrupt(reader,n):
            nonlocal changed
            data=original(reader,n)
            if not changed:
                changed=True
                p=self.source/self.rows[0]['source']
                p.write_bytes(b'x'*self.rows[0]['bytes'])
            return data
        with patch.object(bundle.HashReader,'read',corrupt):
            with self.assertRaises(bundle.BundleError):self.run_build()
        self.assertFalse((self.base/'result/BUILD_RESULT.json').exists())
    def test_no_root_paths_in_distributed_manifest(self):
        self.run_build();raw=(self.base/'result'/bundle.MANIFEST_NAME).read_text()
        self.assertNotIn(str(self.source),raw);self.assertNotIn('"source":',raw);self.assertNotIn('"root":',raw)
    def test_archive_corruption_is_detected(self):
        self.run_build();archive=self.base/'result/curaengine.tar.gz';raw=bytearray(archive.read_bytes());raw[len(raw)//2]^=128;archive.write_bytes(raw)
        with self.assertRaises(Exception):bundle.verify(archive,bundle.manifest(self.inventory))
    def test_long_names_and_unicode_are_data_not_paths_to_execute(self):
        d=deepcopy(self.inventory);d['files'][1]['path']='resources/'+('long-segment/'*14)+'Beispiel ä.def.json'
        self.assertTrue(self.run_build(d)['archive_verified'])
    def test_source_origin_metadata_must_be_pinned(self):
        for value in ['',None,'main','A'*64]:
            d=deepcopy(self.inventory);d['upstream_archives'][0]['sha256']=value
            with self.subTest(value=value):self.rejects(d,'invalid_digest')
    def test_byte_count_limits(self):
        with patch.object(bundle,'MAX_FILES',1):self.rejects(self.inventory,'invalid_file_count')
        with patch.object(bundle,'MAX_TOTAL_BYTES',124):self.rejects(self.inventory,'invalid_payload')

if __name__=='__main__':unittest.main()
