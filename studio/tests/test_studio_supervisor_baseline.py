"""Regression tests for Supervisor's missing outer seccomp filter.

These tests inspect generated policy and lifecycle calls without installing a
filter in the test runner. Real enforcement is tested in a separate container.
"""
from pathlib import Path
import ast
import errno
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'Slicer-Server'
SPEC = importlib.util.spec_from_file_location('baseline_candidate', ROOT/'supervisor_worker_policy.py')
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


def evaluate(rows, number, arg0=0, arch=0xC000003E):
    acc=0; pc=0
    words={0:number,4:arch,16:arg0 & 0xffffffff}
    for _ in range(4096):
        code,yes,no,value=rows[pc]
        if code == 0x20:
            acc=words[value];pc+=1
        elif code in (0x15,0x35,0x45):
            condition=(acc == value if code == 0x15 else acc >= value if code == 0x35 else bool(acc & value))
            pc+=1+(yes if condition else no)
        elif code == 0x06:
            return value
        else:
            raise AssertionError('Unknown policy instruction')
    raise AssertionError('Policy did not terminate')


class BaselineTests(unittest.TestCase):
    @staticmethod
    def resolver(name):
        return {'read':0,'write':1,'open':2,'clock_gettime':228,'clone':56,'clone3':435}.get(name,-1)

    def test_default_deny_all_unlisted_native_calls(self):
        rows=policy.baseline_filter_instructions(self.resolver)
        for nr in range(512):
            expected=0x7fff0000 if nr in {0,1,2,56,228} else 0x50000 | (errno.ENOSYS if nr == 435 else errno.EPERM)
            with self.subTest(nr=nr):
                self.assertEqual(evaluate(rows,nr),expected)

    def test_missing_new_and_privileged_calls_remain_denied(self):
        rows=policy.baseline_filter_instructions(self.resolver)
        for nr in (101,165,166,172,173,175,176,246,248,249,250,272,298,304,308,321,323,425,426,427,438,440,999,65535):
            self.assertEqual(evaluate(rows,nr),0x50000|errno.EPERM)
        for name in ('mount','unshare','setns','keyctl','bpf','init_module','io_uring_setup','process_vm_readv'):
            self.assertNotIn(name,policy.BASE_SYSCALL_NAMES)

    def test_x32_and_wrong_architecture_are_not_interpreted(self):
        rows=policy.baseline_filter_instructions(self.resolver)
        for arch in (0,0x40000003,0xc00000b7):
            self.assertEqual(evaluate(rows,0,arch=arch),0x80000000)
        for nr in (0x40000000,0x40000001,0xffffffff):
            self.assertEqual(evaluate(rows,nr),0x80000000)

    def test_clone_namespaces_blocked_threads_preserved(self):
        rows=policy.baseline_filter_instructions(self.resolver)
        self.assertEqual(evaluate(rows,56,arg0=0x3d0f00),0x7fff0000)
        for bit in range(32):
            expected=0x50000|errno.EPERM if (1<<bit)&policy.CLONE_NAMESPACE_FLAGS else 0x7fff0000
            self.assertEqual(evaluate(rows,56,arg0=1<<bit),expected)

    def test_bad_syscall_resolver_is_rejected(self):
        with self.assertRaises(policy.PolicyError):
            policy.baseline_filter_instructions(lambda _:1)
        def invalid(name):
            return self.resolver(name) if name in {'clone','clone3'} else True
        with self.assertRaises(policy.PolicyError):
            policy.baseline_filter_instructions(invalid)

    def test_landlock_can_add_restrictions_after_baseline(self):
        expected={'landlock_create_ruleset':444,'landlock_add_rule':445,'landlock_restrict_self':446}
        for name in expected:
            self.assertIn(name,policy.BASE_SYSCALL_NAMES)
        rows=policy.baseline_filter_instructions(lambda name: expected.get(name,self.resolver(name)))
        for nr in expected.values():
            self.assertEqual(evaluate(rows,nr),0x7fff0000)

    def test_worker_metadata_changes_are_denied(self):
        for nr in (90,91,92,93,94,132,188,189,190,197,198,199,235,260,261,268,280,452):
            self.assertEqual(evaluate(policy.filter_instructions(),nr),0x50000|errno.EPERM)

    def test_worker_cannot_change_other_process_limits_or_affinity(self):
        for nr in (142,144,203,302):
            self.assertEqual(evaluate(policy.filter_instructions(),nr,arg0=0),0x7fff0000)
            for other in (1,17,65532,0xffffffff):
                self.assertEqual(evaluate(policy.filter_instructions(),nr,arg0=other),0x50000|errno.EPERM)

    def test_all_entry_roles_install_their_own_baseline(self):
        tree=ast.parse((ROOT/'supervisor_app_service.py').read_text(encoding='utf-8-sig'))
        for role in ('start','api','worker','initialize'):
            function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==role)
            calls=[n.func.id for n in ast.walk(function) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
            with self.subTest(role=role):
                self.assertIn('install_process_baseline',calls)

    def test_worker_base_still_requires_kernel_filter_not_a_flag(self):
        value={'uids':[65532]*4,'caps':{k:0 for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')},
               'no_new_privileges':1,'seccomp':0,'seccomp_filters':0,'threads':1}
        with self.assertRaises(policy.PolicyError):
            policy._require_base(value,single_threaded=True)


if __name__=='__main__':
    unittest.main()
