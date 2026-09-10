// Workshop addition; independent of ROS and OpenCR firmware.
#ifndef TURTLEBOT3_NODE__WORKSHOP_CMD_VEL_WATCHDOG_HPP_
#define TURTLEBOT3_NODE__WORKSHOP_CMD_VEL_WATCHDOG_HPP_

#include <chrono>
#include <mutex>

namespace workshop
{
// Gate the existing OpenCR heartbeat on recently received motor commands.
// This does not measure actual motor stop latency or replace a physical stop.
class CommandHeartbeatWatchdog
{
public:
  using Clock = std::chrono::steady_clock;
  using TimePoint = Clock::time_point;

  void command_received(TimePoint now = Clock::now())
  {
    std::lock_guard<std::mutex> lock(mutex_);
    last_command_ = now;
    received_ = true;
  }

  bool allow_heartbeat(TimePoint now = Clock::now()) const
  {
    std::lock_guard<std::mutex> lock(mutex_);
    // No heartbeat at cold start. At exactly 500 ms the command is expired.
    return received_ && now >= last_command_ &&
           now - last_command_ < std::chrono::milliseconds(500);
  }

private:
  mutable std::mutex mutex_;
  bool received_ = false;
  TimePoint last_command_{};
};
}  // namespace workshop

#endif  // TURTLEBOT3_NODE__WORKSHOP_CMD_VEL_WATCHDOG_HPP_
