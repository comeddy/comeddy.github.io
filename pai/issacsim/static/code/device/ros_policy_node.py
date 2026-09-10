#!/usr/bin/env python3
"""ROS 2 Humble local inference. Default output is a preview, never /cmd_vel.

Source /opt/ros/humble/setup.bash before execution on the prepared robot.
Restart with --arm only after resolving a latched fault and checking the manual
stop, OpenCR communication watchdog, and absence of other velocity publishers.
The laser frame must already have +X pointing forward; this node does not apply TF.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import signal
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workshop_core import MAX_LINEAR, Policy, SafetyGuard, scan_to_sectors

PREVIEW_TOPIC = "/workshop/cmd_vel_preview"
COMMAND_TOPIC = "/cmd_vel"
WATCHDOG_PERIOD = 0.05
DISCOVERY_SETTLE_TIME = 1.0
DEFAULT_MAX_LINEAR = 0.05
COMMAND_TYPE = "geometry_msgs/msg/Twist"
ZERO = (0.0, 0.0)


class EdgeController:
    """ROS-independent callback logic, also exercised by offline unit tests."""

    def __init__(
        self, policy, publish, count_publishers, topic_types, *,
        max_linear=DEFAULT_MAX_LINEAR, clock=time.monotonic,
    ):
        if not math.isfinite(max_linear) or not 0 < max_linear <= MAX_LINEAR:
            raise ValueError(f"max_linear must be in (0, {MAX_LINEAR}] m/s")
        self.policy = policy
        self._publish = publish
        self._count_publishers = count_publishers
        self._topic_types = topic_types
        self.max_linear = max_linear
        self._clock = clock
        self._started = clock()
        self._received = None
        self.guard = SafetyGuard()
        self._emit(ZERO)

    def _emit(self, action):
        try:
            self._publish(action)
        except Exception:
            self.guard.stop("command publication failed")
            try:
                self._publish(ZERO)
            except Exception:
                pass
            raise

    def _check(self, now):
        reference = self._started if self._received is None else self._received
        self.guard.check_timeout(now - reference)
        types = tuple(self._topic_types())
        if any(topic_type != COMMAND_TYPE for topic_type in types):
            self.guard.stop("command topic type mismatch; expected geometry_msgs/msg/Twist")
        elif not types and now - self._started >= DISCOVERY_SETTLE_TIME:
            self.guard.stop("command topic type unavailable")
        count = self._count_publishers()
        if count > 1:
            self.guard.stop("another command publisher was discovered")
        elif count != 1 and now - self._started >= DISCOVERY_SETTLE_TIME:
            self.guard.stop("command publisher graph unavailable")
        return bool(types) and count == 1 and now - self._started >= DISCOVERY_SETTLE_TIME

    def on_scan(self, scan):
        action = ZERO
        try:
            now = self._clock()
            ready = self._check(now)
            # Check the previous receipt first: a delayed scan cannot clear a
            # timeout even if it arrives before the next watchdog callback.
            self._received = now
            if self.guard.fault_reason is None:
                sectors, valid = scan_to_sectors(
                    scan.ranges,
                    scan.angle_min,
                    scan.angle_increment,
                    scan.range_min,
                    scan.range_max,
                )
                requested = self.policy.predict(sectors) if valid else ZERO
                action = self.guard.apply(sectors, requested, self._clock() - now, valid)
                action = min(action[0], self.max_linear), action[1]
                if not ready:
                    action = ZERO
        except Exception as exc:
            action = self.guard.stop(f"scan callback failed: {type(exc).__name__}")
        self._emit(action)

    def watchdog(self):
        try:
            self._check(self._clock())
        except Exception as exc:
            self.guard.stop(f"watchdog failed: {type(exc).__name__}")
        if self.guard.fault_reason is not None or self._received is None:
            self._emit(ZERO)

    def stop(self, reason="shutdown"):
        self.guard.stop(reason)
        self._emit(ZERO)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--arm", action="store_true", help="Explicitly enable /cmd_vel")
    parser.add_argument("--scan-topic", default="/scan")
    parser.add_argument(
        "--max-linear", type=float, default=DEFAULT_MAX_LINEAR,
        help="Device forward speed cap in m/s, >0 and <=0.12 (default: 0.05)",
    )
    parser.add_argument(
        "--cmd-topic",
        choices=[COMMAND_TOPIC],
        default=COMMAND_TOPIC,
        help="Teaching command topic; used only with --arm (default: /cmd_vel)",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not math.isfinite(args.max_linear) or not 0 < args.max_linear <= MAX_LINEAR:
        parser.error(f"--max-linear must be >0 and <={MAX_LINEAR} m/s")
    try:
        policy = Policy.load(args.model)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"모델을 읽을 수 없습니다: {exc}\n")
    # Lazy imports keep --help and all offline core/controller tests ROS-free.
    try:
        import rclpy
        from geometry_msgs.msg import Twist
        from rclpy.clock import Clock, ClockType
        from rclpy.node import Node
        from rclpy.qos import qos_profile_sensor_data
        from rclpy.signals import SignalHandlerOptions
        from sensor_msgs.msg import LaserScan
    except ImportError as exc:
        parser.exit(1, f"ROS 2 Humble 환경을 source 하세요: {exc}\n")

    class PolicyNode(Node):
        def __init__(self):
            # Do not allow ROS remapping to redirect a preview onto a motor topic.
            super().__init__("workshop_policy", use_global_arguments=False)
            topic = args.cmd_topic if args.arm else PREVIEW_TOPIC
            self.command_publisher = self.create_publisher(Twist, topic, 1)
            self.controller = EdgeController(
                policy,
                self.publish_action,
                lambda: self.count_publishers(self.command_publisher.topic_name),
                self.command_types,
                max_linear=args.max_linear,
            )
            self.last_reported_fault = None
            self.scan_subscription = self.create_subscription(
                LaserScan, args.scan_topic, self.on_scan, qos_profile_sensor_data
            )
            # A steady clock still fires if ROS simulated time is paused.
            self.watchdog_clock = Clock(clock_type=ClockType.STEADY_TIME)
            self.watchdog_timer = self.create_timer(
                WATCHDOG_PERIOD, self.on_watchdog, clock=self.watchdog_clock
            )
            mode = "ARMED: 실제 속도 출력" if args.arm else "PREVIEW: 미리보기"
            self.get_logger().info(f"{mode} → {topic}; 오류 후에는 원인 해결 및 재시작 필요")

        def publish_action(self, action):
            command = Twist()
            command.linear.x = float(action[0])
            command.angular.z = float(action[1])
            self.command_publisher.publish(command)

        def command_types(self):
            topic = self.command_publisher.topic_name
            endpoints = (
                self.get_publishers_info_by_topic(topic)
                + self.get_subscriptions_info_by_topic(topic)
            )
            return [endpoint.topic_type for endpoint in endpoints]

        def report_fault(self):
            reason = self.controller.guard.fault_reason
            if reason is not None and self.last_reported_fault != reason:
                self.last_reported_fault = reason
                self.get_logger().error(f"정지 고정: {reason}. 원인 해결 후 재시작하세요.")

        def on_scan(self, scan):
            self.controller.on_scan(scan)
            self.report_fault()

        def on_watchdog(self):
            self.controller.watchdog()
            self.report_fault()

    # Keep the ROS context alive until the final zero is published on SIGINT/
    # SIGTERM. The default ROS signal handler would shut that context down first.
    stop_requested = threading.Event()
    previous_handlers = {}
    node = None
    initialized = False
    exit_code = 0
    try:
        rclpy.init(args=[], signal_handler_options=SignalHandlerOptions.NO)
        initialized = True
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.signal(
                signum, lambda _signum, _frame: stop_requested.set()
            )
        node = PolicyNode()
        while rclpy.ok() and not stop_requested.is_set():
            rclpy.spin_once(node, timeout_sec=WATCHDOG_PERIOD)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"노드 오류: {exc}", file=sys.stderr)
        exit_code = 1
    finally:
        if node is not None:
            try:
                node.controller.stop()
            except Exception as exc:
                print(f"정지 명령 전송 실패: {exc}", file=sys.stderr)
                exit_code = 1
            finally:
                node.destroy_node()
        if initialized:
            rclpy.try_shutdown()
        for signum, previous in previous_handlers.items():
            signal.signal(signum, previous)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
