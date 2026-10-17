from __future__ import annotations
import copy
import ctypes
import errno
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'Slicer-Server'
if not SOURCE.is_dir():
    SOURCE = Path(__file__).resolve().parent


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, SOURCE/file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = load('tested_app_worker_policy', 'supervisor_worker_policy.py')
with patch.dict(sys.modules, {'supervisor_worker_policy': policy}):
    app = load('tested_app_service', 'supervisor_app_service.py')
runtime = load('tested_app_runtime', 'container_runtime.py')


def evaluate(rows, nr, *, arch=0xC000003E, arg0=0):
    accumulator=0;counter=0;budget=2048
    words={0:nr,4:arch,16:arg0 & 0xFFFFFFFF}
    while budget:
        budget-=1
        code,yes,no,value=rows[counter]
        if code==0x20:
            accumulator=words[value];counter+=1
        elif code in (0x15,0x35,0x45):
            matched=(accumulator==value if code==0x15 else
                     accumulator>=value if code==0x35 else bool(accumulator & value))
            counter+=1+(yes if matched else no)
        elif code==0x06:
            return value
        else:
            raise AssertionError('unsupported BPF instruction')
    raise AssertionError('BPF did not terminate')


class AppPolicyTests(unittest.TestCase):
    def test_layout_matches_linux_abi(self):
        self.assertEqual(ctypes.sizeof(policy.Ruleset),24)
        self.assertEqual(ctypes.sizeof(policy.PathRule),12)
        self.assertEqual(ctypes.sizeof(policy.Filter),8)
        self.assertEqual(policy.MIN_LANDLOCK_ABI,6)

    def test_entire_native_syscall_number_range_has_exact_decisions(self):
        rows=policy.filter_instructions()
        for nr in range(512):
            with self.subTest(nr=nr):
                expected=0x50000|errno.EPERM if nr in policy.DENIED_SYSCALLS else (
                    0x50000|errno.ENOSYS if nr==435 else 0x7FFF0000)
                self.assertEqual(evaluate(rows,nr),expected)

    def test_wrong_architecture_is_killed_before_number_interpretation(self):
        for arch in (0,0x40000003,0xC00000B7,0x8000003E,0xFFFFFFFF):
            for nr in (0,1,41,59,435):
                with self.subTest(arch=arch,nr=nr):
                    self.assertEqual(evaluate(policy.filter_instructions(),nr,arch=arch),0x80000000)

    def test_x32_or_signed_invalid_numbers_are_killed(self):
        for nr in (0x40000000,0x40000029,0x80000000,0xFFFFFFFF):
            self.assertEqual(evaluate(policy.filter_instructions(),nr),0x80000000)

    def test_clone_all_namespace_flags_rejected_but_threads_allowed(self):
        for bit in range(32):
            flags=1<<bit
            expected=0x50000|errno.EPERM if flags & policy.CLONE_NAMESPACE_FLAGS else 0x7FFF0000
            with self.subTest(bit=bit):
                self.assertEqual(evaluate(policy.filter_instructions(),56,arg0=flags),expected)
        self.assertEqual(evaluate(policy.filter_instructions(),56,arg0=0x3D0F00),0x7FFF0000)

    def test_all_network_and_alternate_fd_routes_explicitly_denied(self):
        for nr in list(range(41,56))+[288,299,307,425,426,427,438,101,310,311,321]:
            self.assertIn(nr,policy.DENIED_SYSCALLS)

    def test_write_grants_never_include_executable_or_private_roots(self):
        self.assertFalse(policy.WRITE_TREE & policy.FS_EXECUTE)
        for sensitive in ('/data','/data/private','/run','/ssl','/etc','/opt','/engine','/usr'):
            self.assertNotIn(sensitive,policy.WRITE_PATHS)
        self.assertNotIn('/ssl',policy.READ_ONLY_PATHS)
        self.assertNotIn('/run',policy.READ_ONLY_PATHS)
        self.assertEqual(set(policy.WRITE_PATHS),{'/data/state','/data/profiles','/tmp','/dev/shm'})

    def test_base_requires_specific_uid_and_every_capability_set_zero(self):
        valid={'uids':[65532]*4,'caps':{k:0 for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')},
               'no_new_privileges':1,'seccomp':2,'seccomp_filters':2,'threads':1}
        policy._require_base(valid,single_threaded=True)
        for key in valid['caps']:
            value=copy.deepcopy(valid);value['caps'][key]=1
            with self.subTest(cap=key),self.assertRaises(policy.PolicyError):
                policy._require_base(value,single_threaded=True)
        for uids in ([0]*4,[1]*4,[65532,0,65532,65532],[65532]*3):
            value=copy.deepcopy(valid);value['uids']=uids
            with self.subTest(uids=uids),self.assertRaises(policy.PolicyError):
                policy._require_base(value,single_threaded=True)
        value=copy.deepcopy(valid);value['threads']=2
        with self.assertRaises(policy.PolicyError):policy._require_base(value,single_threaded=True)
        policy._require_base(value,single_threaded=False)
        value=copy.deepcopy(valid);value['seccomp']=0
        with self.assertRaises(policy.PolicyError):policy._require_base(value,single_threaded=True)

    def test_unknown_profile_never_uses_compose_or_app(self):
        with patch.dict(os.environ,{'STUDIO_RUNTIME_ISOLATION':'unexpected'}), \
                patch.object(runtime,'observe') as observed:
            with self.assertRaisesRegex(runtime.IsolationError,'unknown_isolation_profile'):
                runtime.require_isolation()
            observed.assert_not_called()

    def test_explicit_app_branch_needs_real_probe_and_never_falls_back(self):
        with patch.dict(os.environ,{'STUDIO_RUNTIME_ISOLATION':policy.PROFILE}), \
                patch.dict(sys.modules,{'supervisor_worker_policy':policy}), \
                patch.object(runtime,'observe') as observed, \
                patch.object(policy,'verify_applied',side_effect=policy.PolicyError('denied')):
            with self.assertRaisesRegex(runtime.IsolationError,'denied'):runtime.require_isolation()
            observed.assert_not_called()

    def test_default_compose_contract_is_still_called(self):
        with patch.dict(os.environ,{},clear=True),patch.object(runtime,'observe',return_value={'test':True}), \
                patch.object(runtime,'validate',return_value='compose') as checked:
            self.assertEqual(runtime.require_isolation(),'compose')
            checked.assert_called_once_with({'test':True})

    def test_explicit_app_profile_returns_only_verified_result(self):
        proof={'kernel_guards_observed':True}
        with patch.dict(os.environ,{'STUDIO_RUNTIME_ISOLATION':policy.PROFILE}), \
                patch.dict(sys.modules,{'supervisor_worker_policy':policy}), \
                patch.object(policy,'verify_applied',return_value=proof):
            self.assertIs(runtime.require_isolation(),proof)


class AppConfigurationTests(unittest.TestCase):
    def valid(self):
        return {'api_secret':'A'*48,'certfile':'server.crt','keyfile':'server.key'}

    def parse(self,value):
        return app.parse_options(json.dumps(value).encode())

    def test_minimal_options_roundtrip(self):
        self.assertEqual(self.parse(self.valid()),self.valid())

    def test_missing_extra_and_wrong_container_types_rejected(self):
        for value in (None,[],True,{},dict(self.valid(),unexpected=True)):
            with self.subTest(value=type(value)),self.assertRaises(app.AppConfigurationError):self.parse(value)
        for key in self.valid():
            value=self.valid();value.pop(key)
            with self.subTest(missing=key),self.assertRaises(app.AppConfigurationError):self.parse(value)

    def test_secret_grammar_and_bounds(self):
        for secret in ('','A'*31,'A'*257,'A'*31+' ','A'*31+'\n','A'*31+'ä',None,True,32):
            value=self.valid();value['api_secret']=secret
            with self.subTest(kind=type(secret)),self.assertRaises(app.AppConfigurationError):self.parse(value)
        for size in (32,256):
            value=self.valid();value['api_secret']='A'*size
            self.assertEqual(self.parse(value),value)

    def test_tls_paths_cannot_escape_standard_ssl_mount(self):
        for field in ('certfile','keyfile'):
            for name in ('','..','../x','/ssl/x','x/y','x\\y','x:1','a'*129,None,1,'-a'):
                value=self.valid();value[field]=name
                with self.subTest(field=field,name=name),self.assertRaises(app.AppConfigurationError):self.parse(value)
        value=self.valid();value['keyfile']=value['certfile']
        with self.assertRaises(app.AppConfigurationError):self.parse(value)

    def test_invalid_json_duplicate_keys_and_limits(self):
        for raw in (b'',b'\xff',b'{',b'a'*16385,b'{"api_secret":"x","api_secret":"y"}'):
            with self.subTest(length=len(raw)),self.assertRaises(app.AppConfigurationError):app.parse_options(raw)

    def test_worker_environment_does_not_inherit_operator_secrets(self):
        with patch.dict(os.environ,{'SUPERVISOR_TOKEN':'synthetic-only','API_SECRET':'synthetic-only','PYTHONPATH':'untrusted'}):
            env=app._environment()
        self.assertNotIn('SUPERVISOR_TOKEN',env)
        self.assertNotIn('API_SECRET',env)
        self.assertNotIn('PYTHONPATH',env)
        self.assertEqual(env['STUDIO_RUNTIME_ISOLATION'],policy.PROFILE)

    def test_api_private_paths_and_no_exec_after_sealing(self):
        source=(SOURCE/'supervisor_app_service.py').read_text(encoding='utf-8-sig')
        self.assertIn("runpy.run_path(sys.argv[0], run_name='__main__')",source)
        self.assertNotIn('os.exec',source)
        self.assertIn("PRIVATE/'api-config.json'",source)
        self.assertNotIn('/tmp/studio-api-config.json',source)
        self.assertIn('close_fds=True',source)


if __name__=='__main__':
    unittest.main()
