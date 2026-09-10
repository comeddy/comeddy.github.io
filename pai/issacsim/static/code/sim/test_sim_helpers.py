"""CPU checks for simulator helpers; these do not execute Isaac or robot physics."""

import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

import numpy as np

from run_sim import parse_args, run
from scene_math import Box, clearance, expected_scan, make_layout, write_png


class LayoutTests(unittest.TestCase):
    def test_seeds_repeat_and_produce_free_spawns(self):
        for seed in range(100):
            boxes, spawn, yaw = make_layout(seed)
            repeat_boxes, repeat_spawn, repeat_yaw = make_layout(seed)
            self.assertEqual(boxes, repeat_boxes)
            np.testing.assert_array_equal(spawn, repeat_spawn)
            self.assertEqual(yaw, repeat_yaw)
            self.assertGreater(clearance(spawn, boxes), 0.65)
            self.assertEqual(len(boxes), 12)
            self.assertTrue(all(box.height >= 0.5 for box in boxes))
        self.assertNotEqual(make_layout(42)[0], make_layout(900)[0])

    def test_oracle_cardinal_and_rotated_distances(self):
        boxes = [
            Box(2.1, 0, 0.2, 8), Box(-4.1, 0, 0.2, 8),
            Box(0, 3.1, 8, 0.2), Box(0, -1.1, 8, 0.2),
        ]
        angles = np.arange(4) * np.pi / 2
        np.testing.assert_allclose(expected_scan([0, 0], 0, angles, boxes, 10), [2, 3, 4, 1])
        np.testing.assert_allclose(
            expected_scan([0, 0], np.pi / 2, angles, boxes, 10), [3, 4, 1, 2]
        )

    def test_oracle_rejects_parallel_miss_and_out_of_range(self):
        box = Box(2, 2, 1, 1)
        result = expected_scan([0, 0], 0, np.array([0, np.pi / 2]), [box], 10)
        self.assertTrue(np.isposinf(result).all())
        result = expected_scan([0, 0], 0, np.array([np.pi / 4]), [box], 1)
        self.assertTrue(np.isposinf(result).all())

    def test_clearance_accounts_for_robot_radius(self):
        box = Box(0, 0, 1, 1)
        self.assertAlmostEqual(clearance([1, 0], [box]), 0.36)
        self.assertLess(clearance([0.6, 0], [box]), 0)


class OutputTests(unittest.TestCase):
    def test_png_is_a_lossless_camera_image(self):
        image = np.arange(3 * 5 * 4, dtype=np.uint8).reshape(3, 5, 4)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preview.png"
            write_png(path, image)
            data = path.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        index, chunks = 8, {}
        while index < len(data):
            length = struct.unpack(">I", data[index:index + 4])[0]
            kind = data[index + 4:index + 8]
            payload = data[index + 8:index + 8 + length]
            crc = struct.unpack(">I", data[index + 8 + length:index + 12 + length])[0]
            self.assertEqual(crc, zlib.crc32(kind + payload) & 0xFFFFFFFF)
            chunks[kind] = payload
            index += 12 + length
        self.assertEqual(struct.unpack(">II", chunks[b"IHDR"][:8]), (5, 3))
        self.assertEqual(
            zlib.decompress(chunks[b"IDAT"]),
            b"".join(b"\0" + row[:, :3].tobytes() for row in image),
        )

    def test_cli_matches_output_mount_contract(self):
        args = parse_args([
            "--mode", "collect", "--episodes", "30", "--steps", "600", "--seed", "42",
            "--output", "/output/dataset.npz", "--preview", "/output/preview.png",
        ])
        self.assertEqual(args.output, Path("/output/dataset.npz"))
        self.assertFalse(args.render)
        args = parse_args([
            "--mode", "evaluate", "--episodes", "5", "--steps", "600", "--seed", "900",
            "--policy", "/output/policy.npz", "--output", "/output/evaluation.json",
        ])
        self.assertEqual(args.policy, Path("/output/policy.npz"))

    def test_evaluation_requires_a_policy(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_args(["--mode", "evaluate", "--output", "/output/evaluation.json"])


class OutputContractTests(unittest.TestCase):
    """Mock only the unavailable GPU boundary, never claim simulated motion."""

    class FixtureArena:
        asset_path = "test-fixture-not-a-real-asset"
        initial_position = np.array([0, 0, 0])
        boxes = [Box(2, 0, 0.5, 0.5)]
        close_obstacle = False

        def __init__(self, app, render):
            pass

        def reset(self, seed):
            return self.scan()

        def scan(self):
            ranges = np.full(360, 2.0)
            if self.close_obstacle:
                ranges[0] = 0.20
            return ranges

        def pose(self):
            return np.array([0.0, 0.0, 0.0]), 0.0

        def advance(self, action):
            return 0.0, False, 1.0

        def command(self, action):
            pass

    def test_npz_keeps_metres_and_episode_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dataset.npz"
            args = parse_args(["--mode", "collect", "--episodes", "2", "--steps", "3",
                               "--output", str(output)])
            with patch("run_sim.Arena", self.FixtureArena), contextlib.redirect_stdout(io.StringIO()):
                run(args, object())
            with np.load(output, allow_pickle=False) as dataset:
                self.assertEqual(set(dataset.files), {"observations", "actions", "episodes"})
                np.testing.assert_allclose(dataset["observations"], np.full((6, 12), 2.0))
                np.testing.assert_array_equal(dataset["episodes"], [0, 0, 0, 1, 1, 1])
                np.testing.assert_allclose(dataset["actions"], [[0.12, 0.0]] * 6)
            metadata = json.loads(output.with_suffix(".metadata.json").read_text())
            self.assertEqual(metadata["summary"]["moving_step_fraction"], 0)
            self.assertEqual(len(output.with_suffix(".csv").read_text().splitlines()), 7)

    def test_guard_latches_even_when_teacher_already_requests_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dataset.npz"
            args = parse_args(["--mode", "collect", "--episodes", "1", "--steps", "600",
                               "--output", str(output)])
            with (
                patch("run_sim.Arena", self.FixtureArena),
                patch.object(self.FixtureArena, "close_obstacle", True),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                run(args, object())
            metadata = json.loads(output.with_suffix(".metadata.json").read_text())
            episode = metadata["episodes"][0]
            self.assertEqual(episode["steps"], 1)
            self.assertEqual(episode["termination"], "safety_stop")
            self.assertEqual(episode["safety_interventions"], 1)
            self.assertEqual(episode["stationary_step_fraction"], 1)


if __name__ == "__main__":
    unittest.main()
