import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from argparse import Namespace

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/workflow.py'
spec=importlib.util.spec_from_file_location('workflow',SCRIPT)
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)

def args(stage='smoke',**kwargs):
    values=dict(stage=stage,repo=Path('/tmp/unused-microduck-workflow-test'),execute=False,
                asset_permission_confirmed=False,num_envs=None,iterations=None,seed=42,checkpoint=None,onnx=None)
    values.update(kwargs);return Namespace(**values)

class WorkflowTests(unittest.TestCase):
    def test_default_plan_never_calls_process(self):
        with patch.object(w.subprocess,'run') as run,patch.object(w.subprocess,'check_output') as read:
            self.assertEqual(w.run(args()),0);run.assert_not_called();read.assert_not_called()
    def test_setup_requires_asset_permission_before_process(self):
        with patch.object(w.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'permission'):w.run(args('setup',execute=True))
            run.assert_not_called()
    def test_setup_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d,patch.object(w.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'new checkout'):w.run(args('setup',repo=Path(d),execute=True,asset_permission_confirmed=True))
            run.assert_not_called()
    def test_export_requires_exact_checkpoint(self):
        with self.assertRaisesRegex(ValueError,'checkpoint'):w.run(args('export'))
    def test_export_requires_explicit_output(self):
        with self.assertRaisesRegex(ValueError,'onnx'):w.run(args('export',checkpoint=Path('my.pt')))
    def test_mismatched_revision_rejected(self):
        with patch.object(w.subprocess,'check_output',return_value='deadbeef\n'):
            with self.assertRaisesRegex(ValueError,'mismatch'):w.checked_repo(Path('/tmp'))
    def test_modified_upstream_rejected(self):
        with patch.object(w.subprocess,'check_output',side_effect=[w.UPSTREAM['commit'],' M file.py']):
            with self.assertRaisesRegex(ValueError,'changed'):w.checked_repo(Path('/tmp'))
    def test_custom_env_count_and_iterations_preserved(self):
        command=w.make_plan(args('train',num_envs=512,iterations=1200,seed=9))[0][1]
        for flag,value in [('--env.scene.num-envs','512'),('--agent.max-iterations','1200'),('--agent.seed','9')]:
            self.assertEqual(command[command.index(flag)+1],value)
        self.assertIn('--frozen',command);self.assertNotIn('--hf-jobs',command)
    def test_export_uses_upstream_exporter_no_hand_conversion(self):
        command=w.make_plan(args('export',checkpoint=Path('my.pt'),onnx=Path('my.onnx')))[0][1]
        self.assertIn('scripts/export.py',command)
        self.assertEqual(command[command.index('--num-envs')+1],'1')
    def test_failed_execution_never_marked_completed(self):
        with tempfile.TemporaryDirectory() as d,patch.object(w,'ROOT',Path(d)),patch.object(w,'checked_repo'),patch.object(w.subprocess,'run',side_effect=w.subprocess.CalledProcessError(1,['uv'])):
            with self.assertRaises(w.subprocess.CalledProcessError):w.run(args(execute=True))
            record=w.json.loads(next((Path(d)/'artifacts/commands').glob('*.json')).read_text())
            self.assertFalse(record['completed']);self.assertFalse(record['physical_trial_authorized'])

if __name__=='__main__':unittest.main()
