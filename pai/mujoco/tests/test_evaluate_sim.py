"""CPU-only evaluator tests. No robot assets, CUDA, or trained policy loaded."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import hashlib
import io
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

CODE = Path(__file__).resolve().parents[1] / "static" / "code"
sys.path.insert(0, str(CODE))
import evaluate_sim as ev

HAS_ONNX = all(importlib.util.find_spec(name) for name in ("numpy", "onnx", "onnxruntime"))
if HAS_ONNX:
    import numpy as np
    import onnx
    import onnxruntime as ort
    from onnx import TensorProto, helper, numpy_helper


def frame(x=0, vx=0.1, gravity=(0, 0, -1), **kwargs):
    return ev.Frame((x, 0, 0.15), (vx, 0, 0), (0, 0, 0), gravity, **kwargs)


class HelperTests(unittest.TestCase):
    def test_import_and_help_without_site_packages(self):
        proc = subprocess.run([sys.executable, "-S", str(CODE / "evaluate_sim.py"), "--help"],
                              text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--repo", proc.stdout)
        proc = subprocess.run([sys.executable, "-S", "-c",
                               f"import sys; sys.path.insert(0, {str(CODE)!r}); import evaluate_sim; "
                               "assert not any(n in sys.modules for n in ('torch','numpy','onnxruntime','mjlab'))"],
                              text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_seeds_are_exact_unique_bounded_and_not_training_default(self):
        self.assertEqual(ev.parse_seeds("900, 901,902"), (900, 901, 902))
        for text in ("", "nan", "1,1", "-1", "42", str(2**32), ",900", ",".join(map(str, range(17)))):
            with self.subTest(text=text), self.assertRaises(ev.EvaluationError):
                ev.parse_seeds(text)

    def test_control_budget(self):
        self.assertEqual(ev.step_budget(10), 500)
        self.assertEqual(ev.step_budget(0.14), 7)
        for seconds in (0, -1, 0.019, 0.03, 60.02, math.nan, math.inf):
            with self.subTest(seconds=seconds), self.assertRaises(ev.EvaluationError):
                ev.step_budget(seconds)
        with self.assertRaises(ev.EvaluationError):
            ev.step_budget(10, 0.01)

    def test_tilt_orientation_normalization_and_invalid_values(self):
        self.assertEqual(ev.tilt_degrees((0, 0, -9.81)), 0)
        self.assertEqual(ev.tilt_degrees((1, 0, 0)), 90)
        self.assertEqual(ev.tilt_degrees((0, 0, 1)), 180)
        self.assertAlmostEqual(ev.tilt_degrees((1, 0, -1)), 45)
        for values in ((0, 0, 0), (0, math.nan, -1), (0, 0), (0, 0, math.inf)):
            with self.subTest(values=values), self.assertRaises(ev.EvaluationError):
                ev.tilt_degrees(values)

    def test_distance_is_relative_xy_and_velocity_is_body_frame(self):
        f = ev.Frame((13, 24, 100), (0.4, 0.4, 88), (7, 7, 0.5), (0, 0, -1))
        m = ev.frame_metrics(f, (10, 20, 0), (13, 20, 0), ev.Command(0.1, 0, 0.2))
        self.assertEqual(m["distance_m"], 5)
        self.assertEqual(m["path_increment_m"], 4)
        self.assertAlmostEqual(m["planar_velocity_error_m_s"], 0.5)
        self.assertAlmostEqual(m["yaw_rate_error_rad_s"], 0.3)

    def test_nonfinite_state_is_not_a_numeric_success(self):
        for f in (frame(x=math.nan), frame(vx=math.inf), frame(finite=False)):
            m = ev.frame_metrics(f, (0, 0, 0), (0, 0, 0), ev.Command())
            self.assertEqual(m, {"finite": False})
            self.assertEqual(ev.first_failure(f, m, ev.Thresholds()), "nonfinite_or_invalid_state")

    def test_policy_signature_rejects_wrong_count_type_and_dynamic_shape(self):
        inp = SimpleNamespace(shape=[1, 61], type="tensor(float)", name="obs")
        out = SimpleNamespace(shape=[1, 14], type="tensor(float)", name="act")
        self.assertEqual(ev.validate_policy_signature([inp], [out]), ("obs", "act"))
        for inputs, outputs in (([], [out]), ([inp, inp], [out]), ([inp], [out, out]),
                                ([SimpleNamespace(shape=[None, 61], type="tensor(float)")], [out]),
                                ([SimpleNamespace(shape=[1, 61], type="tensor(double)")], [out]),
                                ([inp], [SimpleNamespace(shape=[1, 15], type="tensor(float)")])):
            with self.subTest(inputs=inputs), self.assertRaises(ev.EvaluationError):
                ev.validate_policy_signature(inputs, outputs)


class RolloutTests(unittest.TestCase):
    def run_frames(self, frames, command=ev.Command(vx=0.1), seconds=0.06, initial=None):
        result = ev.new_result(900, "test", command, seconds)
        advance = mock.Mock(side_effect=frames)
        trace = []
        ev.bounded_rollout(initial or frame(), advance, result, command, ev.Thresholds(), trace.append)
        return result, trace, advance

    def test_exact_duration_with_relative_distance_and_no_hardware_authorization(self):
        result, rows, advance = self.run_frames([frame(10.002), frame(10.004), frame(10.006)], initial=frame(10))
        self.assertEqual(advance.call_count, 3)
        self.assertEqual(result["sim_time_s"], 0.06)
        self.assertAlmostEqual(result["distance_m"], 0.006)
        self.assertAlmostEqual(result["path_length_m"], 0.006)
        self.assertTrue(result["provisional_thresholds_met"])
        self.assertEqual(result["stop_reason"], "duration_reached")
        self.assertEqual(result["metric_samples"], 3)
        for row in [result, *rows]:
            self.assertTrue(row["manual_review_required"])
            self.assertFalse(row["physical_trial_authorized"])

    def test_first_termination_keeps_fallen_pose_and_does_not_autoreset(self):
        result, rows, advance = self.run_frames([frame(0.2, terminated=True, gravity=(0, 0, 1)), frame()])
        self.assertEqual(advance.call_count, 1)
        self.assertEqual(len(rows), 2)
        self.assertTrue(result["terminated"])
        self.assertFalse(result["truncated"])
        self.assertEqual(result["stop_reason"], "terminated")
        self.assertEqual(result["distance_m"], 0.2)
        self.assertEqual(result["max_tilt_deg"], 180)
        self.assertFalse(result["provisional_thresholds_met"])

    def test_truncation_on_final_tick_is_not_duration_success(self):
        result, _, advance = self.run_frames([frame(truncated=True)], seconds=0.02)
        self.assertEqual(advance.call_count, 1)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["stop_reason"], "truncated")
        self.assertFalse(result["provisional_thresholds_met"])

    def test_initial_failure_never_calls_policy(self):
        result, rows, advance = self.run_frames([], initial=frame(gravity=(0, 0, 1)))
        advance.assert_not_called()
        self.assertEqual(result["steps"], 0)
        self.assertEqual(result["stop_reason"], "tilt_deg_limit")
        self.assertEqual(len(rows), 1)

    def test_nonfinite_action_does_not_advance_simulated_time(self):
        result, rows, advance = self.run_frames([frame(finite=False, advanced=False, failure_stage="policy"), frame()])
        self.assertEqual(advance.call_count, 1)
        self.assertEqual(result["steps"], 0)
        self.assertEqual(result["sim_time_s"], 0)
        self.assertFalse(result["finite"])
        self.assertEqual(result["failure_stage"], "policy")
        json.dumps(rows, allow_nan=False)

    def test_nonfinite_after_step_keeps_tick_and_last_finite_metrics(self):
        result, rows, advance = self.run_frames([frame(0.002), frame(x=math.nan), frame()])
        self.assertEqual(advance.call_count, 2)
        self.assertEqual(result["steps"], 2)
        self.assertEqual(result["distance_m"], 0.002)
        self.assertEqual(result["metric_samples"], 1)
        self.assertFalse(rows[-1]["finite"])
        self.assertNotIn("distance_m", rows[-1])
        json.dumps(result, allow_nan=False)

    def test_zero_command_drift_and_instantaneous_error_stop_immediately(self):
        for f, command, reason in (
            (frame(0.251, vx=0), ev.Command(), "zero_command_drift_limit"),
            (frame(vx=0.851), ev.Command(vx=0.1), "planar_velocity_error_m_s_limit"),
            (replace(frame(), angular_velocity=(0, 0, 2.01)), ev.Command(vx=0.1), "yaw_rate_error_rad_s_limit"),
        ):
            with self.subTest(reason=reason):
                result, _, advance = self.run_frames([f, frame()], command=command)
                self.assertEqual(advance.call_count, 1)
                self.assertEqual(result["stop_reason"], reason)

    def test_duration_alone_does_not_meet_mean_tracking_threshold(self):
        result, _, _ = self.run_frames([frame(vx=0.31)] * 3)
        self.assertEqual(result["stop_reason"], "mean_planar_velocity_error_limit")
        self.assertFalse(result["provisional_thresholds_met"])

    def test_interrupted_rollout_exposes_partial_result(self):
        result = ev.new_result(901, "test", ev.Command(), 10)
        advance = mock.Mock(side_effect=[frame(vx=0), RuntimeError("simulation error")])
        with self.assertRaisesRegex(RuntimeError, "simulation error"):
            ev.bounded_rollout(frame(vx=0), advance, result, ev.Command(), ev.Thresholds(), lambda row: None)
        self.assertEqual(result["steps"], 1)
        self.assertFalse(result["provisional_thresholds_met"])


class EvidenceTests(unittest.TestCase):
    def test_repo_rejects_wrong_pin_dirty_files_and_wrong_origin(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            for responses, message in (([str(repo), "b" * 40], "HEAD"),
                                       ([str(repo), ev.PIN, "https://github.com/other/fork.git"], "origin"),
                                       ([str(repo), ev.PIN, "https://github.com/pollen-robotics/microduck_rl.git", " M src/code.py"], "clean")):
                with self.subTest(message=message), mock.patch.object(ev, "git", side_effect=responses):
                    with self.assertRaisesRegex(ev.EvaluationError, message):
                        ev.verify_repo(repo)

    def test_repo_rejects_untracked_source_shadow(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            (repo / "src").mkdir()
            (repo / "src" / "shadow.py").write_text("# unexpected import")
            responses = [str(repo), ev.PIN, "https://github.com/pollen-robotics/microduck_rl.git", "", ""]
            with mock.patch.object(ev, "git", side_effect=responses):
                with self.assertRaisesRegex(ev.EvaluationError, "untracked importable"):
                    ev.verify_repo(repo)

    def test_json_and_csv_keep_failure_and_review_gates(self):
        result = ev.new_result(902, "zero", ev.Command(), 10)
        result.update(stop_reason="nonfinite_or_invalid_state", finite=False)
        with tempfile.TemporaryDirectory() as temp:
            ev.save_report(Path(temp), {"episodes": [result], **ev.GATES})
            loaded = json.loads((Path(temp) / "simulation-report.json").read_text())
            self.assertFalse(loaded["episodes"][0]["finite"])
            self.assertTrue(loaded["manual_review_required"])
            self.assertFalse(loaded["physical_trial_authorized"])
            self.assertIn("nonfinite_or_invalid_state", (Path(temp) / "episodes.csv").read_text())


@unittest.skipUnless(HAS_ONNX, "Optional onnx, onnxruntime and numpy are required")
class PolicyBytesTests(unittest.TestCase):
    @staticmethod
    def model(weight=1.0):
        weights = np.zeros((61, 14), dtype=np.float32)
        weights[:14] = np.eye(14, dtype=np.float32) * weight
        graph = helper.make_graph(
            [helper.make_node("MatMul", ["obs", "weights"], ["action"])],
            "synthetic-evaluator-test",
            [helper.make_tensor_value_info("obs", TensorProto.FLOAT, [1, 61])],
            [helper.make_tensor_value_info("action", TensorProto.FLOAT, [1, 14])],
            [numpy_helper.from_array(weights, "weights")],
        )
        return helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=8)

    @staticmethod
    def external_tensor():
        tensor = TensorProto(name="external_weights", data_type=TensorProto.FLOAT, dims=[61, 14])
        tensor.data_location = TensorProto.EXTERNAL
        tensor.external_data.add(key="location", value="weights.bin")
        return tensor

    def test_external_weights_rejected_before_session_even_when_file_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model = self.model()
            model.graph.initializer[0].CopyFrom(self.external_tensor())
            model.graph.initializer[0].name = "weights"
            for location in (TensorProto.EXTERNAL, TensorProto.DEFAULT):
                model.graph.initializer[0].data_location = location
                path = root / "policy.onnx"
                path.write_bytes(model.SerializeToString())
                for weight in (1.0, 3.0):
                    np.full((61, 14), weight, dtype=np.float32).tofile(root / "weights.bin")
                    with self.subTest(location=location, weight=weight):
                        with mock.patch("onnxruntime.InferenceSession") as session:
                            with self.assertRaisesRegex(ev.EvaluationError, "External tensor data"):
                                ev.load_policy(ev.read_regular(path))
                            session.assert_not_called()

    def test_external_tensors_in_nested_graph_function_and_sparse_data_rejected(self):
        external = self.external_tensor()
        constant = helper.make_node("Constant", [], ["embedded"], value=external)
        nested = helper.make_graph(
            [constant], "nested", [],
            [helper.make_tensor_value_info("embedded", TensorProto.FLOAT, [61, 14])],
        )
        graph_model = self.model()
        graph_model.graph.node.append(helper.make_node(
            "If", ["condition"], ["unused"], then_branch=nested, else_branch=nested))
        function_model = self.model()
        function_model.functions.append(helper.make_function(
            "fixture", "Unused", [], ["embedded"], [constant], [helper.make_opsetid("", 17)]))
        sparse_model = self.model()
        sparse = sparse_model.graph.sparse_initializer.add()
        sparse.values.CopyFrom(external)
        sparse.indices.CopyFrom(numpy_helper.from_array(np.array([0], dtype=np.int64), "indices"))
        sparse.dims.extend([61, 14])
        for name, model in (("graph", graph_model), ("function", function_model), ("sparse", sparse_model)):
            with self.subTest(container=name), mock.patch("onnxruntime.InferenceSession") as session:
                with self.assertRaisesRegex(ev.EvaluationError, "External tensor data"):
                    ev.load_policy(model.SerializeToString())
                session.assert_not_called()

    def test_file_replacement_after_read_keeps_report_hash_and_inference_bound_to_bytes(self):
        original = self.model(weight=1.0).SerializeToString()
        replacement = self.model(weight=3.0).SerializeToString()
        captured_bytes, sessions = [], []
        reader = ev.read_regular
        session_factory = ort.InferenceSession
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            policy = root / "policy.onnx"
            policy.write_bytes(original)
            output = root / "evidence"

            def read_then_replace(path):
                data = reader(path)
                captured_bytes.append(data)
                path.write_bytes(replacement)
                return data

            def capture_session(data, **kwargs):
                self.assertIs(data, captured_bytes[0])
                session = session_factory(data, **kwargs)
                sessions.append(session)
                return session

            with (mock.patch.object(ev, "read_regular", side_effect=read_then_replace) as read,
                  mock.patch.object(ev, "verify_repo", return_value={"commit": ev.PIN}),
                  mock.patch("onnxruntime.InferenceSession", side_effect=capture_session) as session,
                  mock.patch.object(ev, "load_runtime", side_effect=ev.EvaluationError("CPU-only test; no simulation")),
                  redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
                code = ev.main(["--repo", str(root), "--policy", str(policy), "--output", str(output)])
            read.assert_called_once_with(policy)
            session.assert_called_once()
            self.assertEqual(code, 2)  # Deliberately stop before importing the GPU runtime.
            report = json.loads((output / "simulation-report.json").read_text())
            self.assertEqual(report["status"], "error")
            self.assertFalse(report["simulation_executed"])
            self.assertEqual(report["policy_sha256"], hashlib.sha256(original).hexdigest())
            self.assertNotEqual(report["policy_sha256"], hashlib.sha256(policy.read_bytes()).hexdigest())
            actions = sessions[0].run(["action"], {"obs": np.ones((1, 61), dtype=np.float32)})[0]
            np.testing.assert_array_equal(actions, np.ones((1, 14), dtype=np.float32))
            self.assertTrue(report["manual_review_required"])
            self.assertFalse(report["physical_trial_authorized"])

    def test_load_policy_refuses_filename_and_mutable_buffer(self):
        for value in ("policy.onnx", Path("policy.onnx"), bytearray(self.model().SerializeToString())):
            with self.subTest(kind=type(value).__name__), mock.patch("onnxruntime.InferenceSession") as session:
                with self.assertRaisesRegex(ev.EvaluationError, "immutable bytes"):
                    ev.load_policy(value)
                session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
