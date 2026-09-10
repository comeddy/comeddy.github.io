import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('package',Path(__file__).resolve().parents[1]/'scripts/package_workshop.py')
pkg=importlib.util.module_from_spec(spec);spec.loader.exec_module(pkg)

class DistributionTests(unittest.TestCase):
    def test_inventory_detects_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pkg.write_stage_inventory(root,{'index.html':b'original'})
            (root/'index.html').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'mismatch'):pkg.validate_stage(root)
    def test_inventory_rejects_extra_stale_file(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pkg.write_stage_inventory(root,{'index.html':b'original'})
            (root/'old-private.txt').write_text('must not survive a rebuild')
            with self.assertRaisesRegex(ValueError,'mismatch'):pkg.validate_stage(root)
    def test_staging_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pkg.write_stage_inventory(root,{'index.html':b'original'})
            (root/'link').symlink_to(root/'index.html')
            with self.assertRaisesRegex(ValueError,'symlink'):pkg.validate_stage(root)
    def test_inventory_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'Unsafe'):pkg.write_stage_inventory(Path(d),{'../leak':b'x'})
    def test_upstream_model_not_publishable(self):
        with tempfile.TemporaryDirectory() as d,patch.object(pkg,'ROOT',Path(d)):
            (Path(d)/'static').mkdir();(Path(d)/'static/robot.stl').write_bytes(b'asset')
            with self.assertRaisesRegex(ValueError,'must not'):pkg.source_files()
    def test_nested_artifacts_excluded(self):
        with tempfile.TemporaryDirectory() as d,patch.object(pkg,'ROOT',Path(d)):
            root=Path(d);(root/'docs/artifacts').mkdir(parents=True)
            (root/'docs/artifacts/private.json').write_text('{}');(root/'docs/public.md').write_text('public')
            self.assertEqual([p.relative_to(root).as_posix() for p in pkg.source_files()],['docs/public.md'])
    def test_source_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d,patch.object(pkg,'ROOT',Path(d)):
            root=Path(d);(root/'docs').mkdir();(root/'outside.txt').write_text('private')
            (root/'docs/link.txt').symlink_to(root/'outside.txt')
            with self.assertRaisesRegex(ValueError,'Symlinks'):pkg.source_files()
    def test_inventory_valid(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pkg.write_stage_inventory(root,{'index.html':b'ok','static/readme.md':b'local'})
            self.assertEqual(pkg.validate_stage(root),2)

if __name__=='__main__':unittest.main()
