from pathlib import Path
import importlib.util
import os
import signal
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]/'Slicer-Server'
sys.path.insert(0,str(ROOT))
try:
 spec=importlib.util.spec_from_file_location('app_shutdown_under_test',ROOT/'supervisor_app_service.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
finally:
 sys.path.remove(str(ROOT))

class Child:
 def __init__(self,pid=101,done=False,timeout=False):
  self.pid=pid;self.done=done;self.timeout=timeout;self.signals=[];self.waits=[]
 def poll(self):return 0 if self.done else None
 def send_signal(self,sig):self.signals.append(sig)
 def wait(self,timeout):
  self.waits.append(timeout)
  if self.timeout and len(self.waits)==1:raise subprocess.TimeoutExpired('synthetic',timeout)
  self.done=True;return 0

class ShutdownTests(unittest.TestCase):
 def test_graceful_stop_targets_owner_not_unready_descendant_group(self):
  child=Child()
  with patch.object(module.os,'killpg',create=True) as kill:
   module._stop([child])
  self.assertEqual(child.signals,[signal.SIGTERM]);kill.assert_not_called()
 def test_each_live_owner_receives_one_graceful_signal(self):
  children=[Child(101),Child(102)]
  with patch.object(module.os,'killpg',create=True) as kill:module._stop(children)
  self.assertEqual([c.signals for c in children],[[signal.SIGTERM],[signal.SIGTERM]])
  kill.assert_not_called()
 def test_completed_owner_is_not_signalled(self):
  child=Child(done=True)
  with patch.object(module.os,'killpg',create=True) as kill:module._stop([child])
  self.assertEqual(child.signals,[]);self.assertEqual(child.waits,[]);kill.assert_not_called()
 def test_timeout_retains_forceful_group_cleanup(self):
  child=Child(timeout=True)
  # This is a Linux-only service; model the POSIX signal for Windows unit tests.
  with patch.object(module.signal,'SIGKILL',9,create=True), patch.object(module.os,'killpg',create=True) as kill:module._stop([child])
  self.assertEqual(child.signals,[signal.SIGTERM]);kill.assert_called_once_with(child.pid,9)
  self.assertEqual(child.waits[-1],5)
 def test_empty_process_list_is_safe(self):
  with patch.object(module.os,'killpg',create=True) as kill:module._stop([])
  kill.assert_not_called()



class SourceIntegrationTests(unittest.TestCase):
 def test_options_and_environment_do_not_pass_supervisor_credentials(self):
  with patch.dict(os.environ,{'SUPERVISOR_TOKEN':'synthetic-secret','HASSIO_TOKEN':'synthetic-old'}):
   env=module._environment()
  self.assertNotIn('SUPERVISOR_TOKEN',env)
  self.assertNotIn('HASSIO_TOKEN',env)
  self.assertNotIn('synthetic-secret',str(env))
 def test_app_modules_are_real_context_inputs(self):
  spec=importlib.util.spec_from_file_location('app_context_source_inputs',ROOT/'prepare_context.py')
  prep=importlib.util.module_from_spec(spec);spec.loader.exec_module(prep)
  for name in ('supervisor_app_service.py','supervisor_worker_policy.py'):
   self.assertIn(name,prep.SUPPORT_FILES)
   self.assertIn(name,(ROOT/'Dockerfile').read_text(encoding='utf-8-sig'))
 def test_libseccomp_is_explicit_image_dependency(self):
  import json
  ref=json.loads((ROOT/'TARGET_IMAGE_REFERENCE.json').read_text(encoding='utf-8-sig'))
  self.assertIn('libseccomp2',ref['required_packages'])
  self.assertEqual(ref['required_package_count'],len(ref['required_packages']))
 def test_existing_isolation_validator_is_not_replaced(self):
  source=(ROOT/'container_runtime.py').read_text(encoding='utf-8-sig')
  self.assertIn('return validate(observe())',source)
  self.assertIn('unknown_isolation_profile',source)
  self.assertIn('return verify_applied()',source)

if __name__=='__main__':unittest.main()
