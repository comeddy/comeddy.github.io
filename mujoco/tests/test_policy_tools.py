"""Local synthetic ONNX only; python -m unittest discover -s tests -p test_policy_tools.py."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

CODE = Path(__file__).resolve().parents[1] / "static" / "code"
sys.path.insert(0, str(CODE))
import check_policy as check
import bundle_policy as bundle

HAS_ONNX = all(importlib.util.find_spec(name) for name in ("numpy", "onnx", "onnxruntime"))
if HAS_ONNX:
    import numpy as np
    import onnx
    from onnx import TensorProto, helper, numpy_helper


def provenance():
    return {"source_refs": {"https://github.com/pollen-robotics/microduck_rl": "a" * 40,
                            "https://github.com/pollen-robotics/microduck": "b" * 40},
            "task_id": "Synthetic-Test-Only", "checkpoint_sha256": "c" * 64,
            "exporter": "mjlab_microduck.export", "official_exporter_used": False,
            "checkpoint_validated_by_user": False}


def model_bytes(input_shape=(1, 61), output_shape=(1, 14), kind="linear", dtype=None):
    dtype = TensorProto.FLOAT if dtype is None else dtype
    inputs = [helper.make_tensor_value_info("obs", dtype, input_shape)]
    outputs = [helper.make_tensor_value_info("action", TensorProto.FLOAT, output_shape)]
    if kind in {"constant", "nonfinite"}:
        values = np.zeros((1, 14), dtype=np.float32)
        if kind == "nonfinite":
            values[0, 4] = np.nan
        nodes = [helper.make_node("Constant", [], ["action"],
                                  value=numpy_helper.from_array(values))]
        initializers = []
    else:
        weights = np.zeros((61, 14), dtype=np.float32)
        weights[6:20] = np.eye(14, dtype=np.float32)
        nodes = [helper.make_node("MatMul", ["obs", "weights"],
                                  ["pre" if kind == "relu" else "action"])]
        if kind == "relu":
            nodes.append(helper.make_node("Relu", ["pre"], ["action"]))
        initializers = [numpy_helper.from_array(weights, "weights")]
    graph = helper.make_graph(nodes, "synthetic-smoke-fixture", inputs, outputs, initializers)
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=8)
    return model.SerializeToString()


class StandardLibraryTests(unittest.TestCase):
    def test_import_and_help_without_optional_packages(self):
        for script in ["check_policy.py", "bundle_policy.py"]:
            result = subprocess.run([sys.executable, "-S", str(CODE / script), "--help"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("usage:", result.stdout)

    def test_missing_dependency_message(self):
        with mock.patch.dict(sys.modules, {"onnx": None}):
            with self.assertRaisesRegex(check.PolicyError, "optional packages"):
                check.dependencies()

    def test_strict_json(self):
        for data in [b'{"x": NaN}', b'{"x": Infinity}', b'{"x": -Infinity}',
                     b'{"x": 1e999}', b'{"x": 1,"x": 2}', b'[] garbage', b'\xff']:
            with self.subTest(data=data), self.assertRaises(check.PolicyError):
                check.strict_json(data)
        self.assertEqual(check.strict_json(b'{"x": [0, 1.25]}'), {"x": [0, 1.25]})

    def test_unsafe_relative_paths(self):
        for name in ["../outside", "a/../b", "/tmp/outside", "a//b", "a/./b", "a/",
                     "C:/outside", "a\\b", "./a", "", ".", "..", "a\nfile", 123]:
            with self.subTest(name=name), self.assertRaises(check.PolicyError):
                bundle.safe_relative(name)
        self.assertEqual(str(bundle.safe_relative("run-1/report.json")), "run-1/report.json")

    def test_member_reader_refuses_symlink_parent_and_leaf(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "outside").mkdir()
            (root / "outside" / "secret").write_text("must not read")
            (root / "bundle").mkdir()
            (root / "bundle" / "link").symlink_to(root / "outside", target_is_directory=True)
            (root / "bundle" / "leaf").symlink_to(root / "outside" / "secret")
            for name in ["link/secret", "leaf"]:
                with self.subTest(name=name), self.assertRaises(OSError):
                    bundle.read_member(root / "bundle", name)

    def test_read_limits_and_special_files(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "file"
            path.write_bytes(b"12345")
            with self.assertRaises(check.PolicyError):
                check.read_regular(path, 4)
            fifo = Path(temp) / "fifo"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(check.PolicyError, "regular file"):
                check.read_regular(fifo)

    def test_provenance_requires_pinned_refs_and_booleans(self):
        for field, value in [("checkpoint_sha256", "checkpoint.pt"), ("exporter", "hand-export"),
                             ("official_exporter_used", "true"),
                             ("checkpoint_validated_by_user", 1), ("task_id", "")]:
            record = provenance()
            record[field] = value
            with self.subTest(field=field), self.assertRaises(check.PolicyError):
                bundle.check_provenance(record)
        for refs in [{}, {"https://github.com/org/repo": "main"},
                     {"file:///tmp/source": "a" * 40}]:
            record = provenance()
            record["source_refs"] = refs
            with self.subTest(refs=refs), self.assertRaises(check.PolicyError):
                bundle.check_provenance(record)


@unittest.skipUnless(HAS_ONNX, "Optional onnx, onnxruntime and numpy are required")
class SyntheticPolicyTests(unittest.TestCase):
    def test_valid_model_reports_real_statistics(self):
        data = model_bytes()
        result = check.validate_bytes(data, samples=8, seed=4)
        self.assertTrue(result["passed"])
        self.assertEqual(result["policy_sha256"], check.sha256(data))
        self.assertEqual(result["samples"], 8)
        self.assertLess(result["output_min"], 0)
        self.assertGreater(result["output_max"], 0)
        self.assertGreaterEqual(result["latency_ms"]["min"], 0)
        self.assertGreaterEqual(result["latency_ms"]["max"], result["latency_ms"]["mean"])
        self.assertEqual(len(result["per_action_min"]), 14)
        self.assertFalse(result["physical_trial_authorized"])
        self.assertFalse(result["normalizer_verified"])
        repeated = check.validate_bytes(data, samples=8, seed=4)
        self.assertEqual(result["per_action_max"], repeated["per_action_max"])

    def test_plausible_seeded_inputs(self):
        inputs = check.synthetic_inputs(np, 12, 22)
        self.assertEqual(inputs.shape, (12, 1, 61))
        self.assertEqual(inputs.dtype, np.float32)
        self.assertTrue(np.isfinite(inputs).all())
        np.testing.assert_allclose(np.linalg.norm(inputs[:, 0, 3:6], axis=1), 1, atol=1e-6)
        np.testing.assert_array_equal(inputs, check.synthetic_inputs(np, 12, 22))
        self.assertFalse(np.array_equal(inputs, check.synthetic_inputs(np, 12, 23)))

    def test_malformed_input_shape(self):
        for shape in [(1, 60), (2, 61), (61,), (1, 1, 61), ("batch", 61), (1, None)]:
            with self.subTest(shape=shape), self.assertRaisesRegex(check.PolicyError, "input.*shape"):
                check.validate_bytes(model_bytes(input_shape=shape))

    def test_malformed_output_shape(self):
        for shape in [(1, 13), (2, 14), (14,), ("batch", 14)]:
            with self.subTest(shape=shape), self.assertRaisesRegex(check.PolicyError, "output.*shape"):
                check.validate_bytes(model_bytes(output_shape=shape))

    def test_float32_required(self):
        with self.assertRaisesRegex(check.PolicyError, "input must be float32"):
            check.validate_bytes(model_bytes(dtype=TensorProto.DOUBLE))
        model = onnx.load_model_from_string(model_bytes())
        model.graph.output[0].type.tensor_type.elem_type = TensorProto.DOUBLE
        with self.assertRaisesRegex(check.PolicyError, "output must be float32"):
            check.validate_bytes(model.SerializeToString())

    def test_exactly_one_input_and_output(self):
        for label in ["input", "output"]:
            model = onnx.load_model_from_string(model_bytes())
            getattr(model.graph, label).append(helper.make_tensor_value_info("extra", TensorProto.FLOAT, [1]))
            with self.subTest(label=label), self.assertRaisesRegex(check.PolicyError, "exactly one"):
                check.validate_bytes(model.SerializeToString())

    def test_nonfinite_inference(self):
        for bad in [np.nan, np.inf, -np.inf]:
            model = onnx.load_model_from_string(model_bytes(kind="nonfinite"))
            values = np.ones((1, 14), dtype=np.float32)
            values[0, 0] = bad
            model.graph.node[0].attribute[0].t.CopyFrom(numpy_helper.from_array(values))
            with self.subTest(bad=bad), self.assertRaisesRegex(check.PolicyError, "nonfinite"):
                check.validate_bytes(model.SerializeToString())

    def test_constant_zero_and_nonzero_vectors_rejected(self):
        for values in [np.zeros((1, 14), dtype=np.float32), np.arange(14, dtype=np.float32).reshape(1, 14)]:
            model = onnx.load_model_from_string(model_bytes(kind="constant"))
            model.graph.node[0].attribute[0].t.CopyFrom(numpy_helper.from_array(values))
            with self.assertRaisesRegex(check.PolicyError, "Constant-output") as raised:
                check.validate_bytes(model.SerializeToString())
            self.assertFalse(raised.exception.report["passed"])
            self.assertTrue(raised.exception.report["constant_output"])

    def test_zero_actions_for_some_inputs_are_allowed(self):
        result = check.validate_bytes(model_bytes(kind="relu"), samples=16)
        self.assertTrue(result["passed"])
        self.assertEqual(result["output_min"], 0)
        self.assertGreater(result["output_max"], 0)

    def test_external_initializer_rejected_before_runtime(self):
        model = onnx.load_model_from_string(model_bytes())
        tensor = model.graph.initializer[0]
        tensor.data_location = TensorProto.EXTERNAL
        tensor.external_data.add(key="location", value="../../must-not-read.bin")
        for location in [TensorProto.EXTERNAL, TensorProto.DEFAULT]:
            tensor.data_location = location
            with mock.patch("onnxruntime.InferenceSession") as runtime:
                with self.assertRaisesRegex(check.PolicyError, "External tensor"):
                    check.validate_bytes(model.SerializeToString())
                runtime.assert_not_called()

    def test_external_attribute_and_function_tensors_rejected(self):
        model = onnx.load_model_from_string(model_bytes(kind="constant"))
        tensor = model.graph.node[0].attribute[0].t
        tensor.data_location = TensorProto.EXTERNAL
        tensor.external_data.add(key="location", value="missing.bin")
        with self.assertRaisesRegex(check.PolicyError, "External tensor"):
            check.validate_bytes(model.SerializeToString())
        function = helper.make_function("fixture", "Unused", [], ["action"],
                                        list(model.graph.node), [helper.make_opsetid("", 17)])
        outer = onnx.load_model_from_string(model_bytes())
        outer.functions.append(function)
        with self.assertRaisesRegex(check.PolicyError, "External tensor"):
            check.validate_bytes(outer.SerializeToString())

    def test_invalid_protobuf(self):
        with self.assertRaises(check.PolicyError):
            check.validate_bytes(b"not ONNX")

    def test_probe_bounds(self):
        for kwargs in [{"samples": 1}, {"samples": 1025}, {"samples": True},
                       {"seed": -1}, {"seed": 2**32}, {"seed": False}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(check.PolicyError):
                check.validate_bytes(model_bytes(), **kwargs)


@unittest.skipUnless(HAS_ONNX, "Optional onnx, onnxruntime and numpy are required")
class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = self.root / "source.onnx"
        self.policy.write_bytes(model_bytes())
        self.evaluation = self.root / "evaluation-input.json"
        self.report = self.root / "simulation.md"
        self.report.write_text("Synthetic test fixture only; no robot/simulator evaluation performed.\n")
        self.record = {"schema_version": 1, "simulation": {
            "status": "not_run", "task_id": provenance()["task_id"],
            "checkpoint_sha256": provenance()["checkpoint_sha256"],
            "policy_sha256": check.sha256(self.policy.read_bytes()), "reports": ["simulation.md"]},
            "notes": "Unit test record; not a real simulation result."}
        self.output = self.root / "bundle"
        self.write_evaluation()

    def write_evaluation(self):
        self.evaluation.write_bytes(check.json_bytes(self.record))

    def create(self, output=None):
        return bundle.create_bundle(self.policy, output or self.output, self.evaluation,
                                    provenance(), samples=4)

    def update_checksums(self):
        files = sorted(p for p in self.output.rglob("*") if p.is_file() and p.name != bundle.CHECKSUMS)
        (self.output / bundle.CHECKSUMS).write_text("".join(
            f"{check.sha256(p.read_bytes())}  {p.relative_to(self.output).as_posix()}\n" for p in files))

    def read_manifest(self):
        return json.loads((self.output / bundle.MANIFEST).read_text())

    def mutate_manifest(self, manifest):
        (self.output / bundle.MANIFEST).write_bytes(check.json_bytes(manifest))
        self.update_checksums()

    def test_round_trip_with_all_statuses_without_success_gate(self):
        for status in ["passed", "failed", "not_run"]:
            self.record["simulation"]["status"] = status
            self.write_evaluation()
            output = self.root / status
            result = self.create(output)
            self.assertEqual(result["simulation_status_user_reported"], status)
            self.assertEqual(result["file_count"], 6)
            self.assertTrue(result["verified"])
            self.assertTrue(all(result[key] is False for key in bundle.SAFETY))
            self.assertEqual((output / "policy.onnx").read_bytes(), self.policy.read_bytes())
            self.assertEqual((output / "evidence/simulation.md").read_bytes(), self.report.read_bytes())
            result2 = bundle.verify_bundle(output, expected_manifest_sha256=result["manifest_sha256"])
            self.assertEqual(result, result2)

    def test_verification_without_optional_packages(self):
        self.create()
        result = subprocess.run([sys.executable, "-S", str(CODE / "bundle_policy.py"),
                                 "verify", str(self.output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["verified"])

    def test_refuse_overwrite_existing_directory_file_and_symlink(self):
        for kind in ["directory", "file", "symlink"]:
            output = self.root / kind
            if kind == "directory":
                output.mkdir()
            elif kind == "file":
                output.write_text("untouched")
            else:
                output.symlink_to(self.root / "not-present")
            with self.subTest(kind=kind), self.assertRaisesRegex(check.PolicyError, "refusing overwrite"):
                self.create(output)
        self.assertEqual((self.root / "file").read_text(), "untouched")

    def test_tampered_policy_report_and_provenance(self):
        for name in ["policy.onnx", "evidence/simulation.md", bundle.MANIFEST, bundle.SMOKE]:
            output = self.root / name.replace("/", "-")
            self.create(output)
            with (output / name).open("ab") as stream:
                stream.write(b"tampered")
            with self.subTest(name=name), self.assertRaisesRegex(check.PolicyError, "SHA256 mismatch"):
                bundle.verify_bundle(output)

    def test_manifest_digest_anchor_detects_rewritten_provenance(self):
        result = self.create()
        manifest = self.read_manifest()
        manifest["provenance"]["official_exporter_used"] = True
        self.mutate_manifest(manifest)
        with self.assertRaisesRegex(check.PolicyError, "independently retained"):
            bundle.verify_bundle(self.output, expected_manifest_sha256=result["manifest_sha256"])

    def test_recomputed_hashes_cannot_authorize_hardware(self):
        self.create()
        for key in bundle.SAFETY:
            manifest = self.read_manifest()
            manifest["safety"] = dict(bundle.SAFETY)
            manifest["safety"][key] = True
            self.mutate_manifest(manifest)
            with self.subTest(key=key), self.assertRaisesRegex(check.PolicyError, "must remain false"):
                bundle.verify_bundle(self.output)

    def test_tampered_provenance_schema_and_checkpoint_binding(self):
        self.create()
        original = self.read_manifest()
        for field, value in [("checkpoint_sha256", "d" * 64), ("official_exporter_used", 1),
                             ("source_refs", {"https://github.com/org/repo": "main"})]:
            manifest = copy.deepcopy(original)
            manifest["provenance"][field] = value
            self.mutate_manifest(manifest)
            with self.subTest(field=field), self.assertRaises(check.PolicyError):
                bundle.verify_bundle(self.output)

    def test_manifest_path_traversal_is_rejected_even_with_new_checksum(self):
        self.create()
        original = self.read_manifest()
        for path in ["../outside", "/tmp/outside", "nested/../../outside", "C:/outside"]:
            manifest = copy.deepcopy(original)
            manifest["files"][path] = "a" * 64
            self.mutate_manifest(manifest)
            with self.subTest(path=path), self.assertRaisesRegex(check.PolicyError, "Unsafe relative"):
                bundle.verify_bundle(self.output)

    def test_checksum_path_traversal_is_rejected_before_read(self):
        self.create()
        (self.output / bundle.CHECKSUMS).write_text(f"{'a' * 64}  ../outside\n")
        with self.assertRaisesRegex(check.PolicyError, "Unsafe relative"):
            bundle.verify_bundle(self.output)

    def test_symlink_in_bundle_and_symlink_bundle_root(self):
        self.create()
        alias = self.root / "alias"
        alias.symlink_to(self.output, target_is_directory=True)
        with self.assertRaisesRegex(check.PolicyError, "not a symlink"):
            bundle.verify_bundle(alias)
        leaf = self.output / "evidence/simulation.md"
        leaf.unlink()
        leaf.symlink_to(self.report)
        with self.assertRaisesRegex(check.PolicyError, "no symlinks"):
            bundle.verify_bundle(self.output)

    def test_extra_missing_and_duplicate_checksum_files(self):
        self.create()
        checksum = self.output / bundle.CHECKSUMS
        original = checksum.read_bytes()
        checksum.write_bytes(original + original.splitlines(keepends=True)[0])
        with self.assertRaisesRegex(check.PolicyError, "Duplicate"):
            bundle.verify_bundle(self.output)
        checksum.write_bytes(original)
        extra = self.output / "extra.txt"
        extra.write_text("unexpected")
        with self.assertRaisesRegex(check.PolicyError, "inventory"):
            bundle.verify_bundle(self.output)
        extra.unlink()
        (self.output / bundle.SMOKE).unlink()
        with self.assertRaisesRegex(check.PolicyError, "inventory"):
            bundle.verify_bundle(self.output)

    def test_evaluation_bindings_and_status_are_required(self):
        original = copy.deepcopy(self.record)
        for field, value in [("task_id", "Other"), ("checkpoint_sha256", "d" * 64),
                             ("policy_sha256", "e" * 64), ("status", "success"),
                             ("reports", []), ("reports", ["../outside"]),
                             ("reports", ["simulation.md", "simulation.md"])]:
            self.record = copy.deepcopy(original)
            self.record["simulation"][field] = value
            self.write_evaluation()
            with self.subTest(field=field, value=value), self.assertRaises(check.PolicyError):
                self.create()
            self.assertFalse(self.output.exists())
        self.record = copy.deepcopy(original)
        del self.record["simulation"]["status"]
        self.write_evaluation()
        with self.assertRaises(check.PolicyError):
            self.create()

    def test_missing_empty_and_symlink_evidence(self):
        self.report.unlink()
        with self.assertRaises(OSError):
            self.create()
        self.report.touch()
        with self.assertRaisesRegex(check.PolicyError, "Empty"):
            self.create()
        self.report.unlink()
        self.report.symlink_to(self.policy)
        with self.assertRaises(OSError):
            self.create()
        self.assertFalse(self.output.exists())

    def test_nested_evidence_copy(self):
        (self.root / "run").mkdir()
        (self.root / "run/metrics.json").write_text('{"episodes": 3, "reward": 1.5}')
        self.record["simulation"]["reports"] = ["run/metrics.json"]
        self.write_evaluation()
        self.create()
        self.assertTrue((self.output / "evidence/run/metrics.json").is_file())

    def test_nonfinite_evaluation_json_and_sidecar(self):
        for bad in ["NaN", "Infinity", "1e999"]:
            self.write_evaluation()
            self.evaluation.write_text(self.evaluation.read_text().replace(
                '"schema_version": 1', f'"schema_version": {bad}'))
            with self.subTest(bad=bad), self.assertRaises(check.PolicyError):
                self.create()
        (self.root / "bad.json").write_text('{"reward": NaN}')
        self.record["simulation"]["reports"] = ["bad.json"]
        self.write_evaluation()
        with self.assertRaisesRegex(check.PolicyError, "Nonfinite"):
            self.create()

    def test_nonfinite_bundle_json_with_recomputed_checksum(self):
        self.create()
        path = self.output / bundle.MANIFEST
        path.write_text(path.read_text().replace('"schema_version": 1', '"schema_version": 1e999'))
        self.update_checksums()
        with self.assertRaisesRegex(check.PolicyError, "finite"):
            bundle.verify_bundle(self.output)

    def test_cli_create_check_and_failure_exit_codes(self):
        check_command = [sys.executable, str(CODE / "check_policy.py"), str(self.policy), "--samples", "4"]
        report = self.root / "smoke.json"
        result = subprocess.run([*check_command, "--report", str(report)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["passed"])
        before = report.read_bytes()
        result = subprocess.run([*check_command, "--report", str(report)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stderr)["passed"])
        self.assertEqual(report.read_bytes(), before)
        command = [sys.executable, str(CODE / "bundle_policy.py"), "create", str(self.policy),
                   str(self.output), "--evaluation", str(self.evaluation),
                   "--task-id", provenance()["task_id"], "--checkpoint-sha256", "c" * 64,
                   "--source-ref", "https://github.com/org/repo@" + "a" * 40,
                   "--official-exporter-used", "--checkpoint-validated-by-user", "--samples", "4"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["deployed"])
        manifest = self.read_manifest()
        self.assertTrue(manifest["provenance"]["official_exporter_used"])
        self.assertTrue(manifest["provenance"]["checkpoint_validated_by_user"])
        self.assertFalse(manifest["safety"]["normalizer_verified"])
        self.policy.write_bytes(model_bytes(kind="constant"))
        result = subprocess.run(check_command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Constant-output", json.loads(result.stderr)["error"])


if __name__ == "__main__":
    unittest.main()
