#!/usr/bin/env python3
"""R.O.B.I.E. SITL runner: plume_sim and gas_climber in ONE process.
Both nodes share one DDS participant, so they talk without network discovery
(which is broken on this WSL setup). The algorithm code is imported unchanged.
Usage: python3 sitl_runner.py --ros-args -p plume_sim:peak:=400.0 -p gas_climber:threshold:=150.0 ..."""
import sys
import rclpy
from rclpy.executors import SingleThreadedExecutor
from robie_gas.plume_sim import PlumeSim
from robie_gas.gas_climber import GasClimber

def main():
    rclpy.init(args=sys.argv)
    sim = PlumeSim()
    climber = GasClimber()
    ex = SingleThreadedExecutor()
    ex.add_node(sim)
    ex.add_node(climber)
    try:
        ex.spin()                      # gas_climber raises SystemExit when its run ends
    except (SystemExit, KeyboardInterrupt):
        pass
    finally:
        climber.csv.close()
        ex.shutdown()
        climber.destroy_node()
        sim.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
