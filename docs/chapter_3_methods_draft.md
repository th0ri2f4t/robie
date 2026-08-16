# Chapter 3: Methodology and System Architecture

## 3.1 Introduction
This chapter details the software architecture, control algorithms, and simulation environment developed for the R.O.B.I.E. (Robotic Odor-Based Inspection Engine) project. The system design adheres to a strict separation of concerns, dividing computational responsibilities between a high-level central processor and a low-level real-time microcontroller. This layered approach ensures that complex navigational planning does not compromise the deterministic safety requirements of the hardware.

## 3.2 Layered Control Architecture
The robot's software stack is built on ROS 2 Humble, operating across two distinct physical tiers:

1. **The Brain (Raspberry Pi 5 / Ubuntu 22.04):** Handles state estimation, SLAM (via SLAM Toolbox), global path planning (Nav2), and the high-level gas-seeking state machine. 
2. **The Spinal Cord (ESP32 Microcontroller):** Acts as a hard real-time bridge. It receives high-level velocity targets via a deterministic 115200-baud serial protocol, executes 20 kHz hardware PWM signals for the motor drivers, and continuously monitors physical safety inputs (E-stop, bumpers).

This division solves a fundamental robotics problem: Linux is not a real-time operating system. By offloading hardware PWM and safety interrupts to the ESP32, the system guarantees that an E-stop button will cut motor power in milliseconds, regardless of CPU load on the Pi.

> **[PLACEHOLDER: Insert SysML Block Definition Diagram (BDD) showing Pi, ESP32, and Sensor nodes]**

## 3.3 The Safety Interlock and Motor Arbiter
Safety in autonomous mobile robots cannot be treated as an afterthought; it must be enforced by construction. The R.O.B.I.E. architecture implements a "defense in depth" safety model:

* **Software Interlock (`robie_safety`):** A dedicated ROS 2 node monitors topics representing the E-stop state, bumper states, and the telemetry heartbeat from the ESP32. If any fault condition is met, it publishes `False` to the `/motor_enable` topic.
* **The Arbiter (`motor_arbiter`):** This node sits logically between the navigation stack and the hardware bridge. It subscribes to both `/wheel_commands` (the desired motion) and `/motor_enable` (the safety gate). If the safety gate is closed, the arbiter forces all wheel target velocities to `0.0` rad/s, overriding any navigational commands.
* **Hardware Interlock:** The ESP32 firmware independently verifies the physical state of the E-stop pin. Even if the Pi freezes or the serial link drops, the microcontroller autonomously zeroes the PWM duty cycles.

> **[PLACEHOLDER: Insert ROS Node/Topic Graph showing the flow from /cmd_vel -> Arbiter -> /motor_targets]**

## 3.4 Locomotion and Inverse Kinematics
The mobile base utilizes a four-wheel Mecanum drivetrain to provide holonomic motion (simultaneous translation and rotation). The `mecanum_driver` node translates standard Cartesian velocity commands (`geometry_msgs/Twist`) into individual wheel angular velocities using closed-form inverse kinematics:

$$ \begin{bmatrix} \omega_{fl} \\ \omega_{fr} \\ \omega_{rl} \\ \omega_{rr} \end{bmatrix} = \frac{1}{r} \begin{bmatrix} 1 & -1 & -(l_x + l_y) \\ 1 & 1 & (l_x + l_y) \\ 1 & 1 & -(l_x + l_y) \\ 1 & -1 & (l_x + l_y) \end{bmatrix} \begin{bmatrix} v_x \\ v_y \\ \omega_z \end{bmatrix} $$

Where $r$ is the wheel radius and $(l_x + l_y)$ represents the geometric arm from the robot's center of rotation to the wheels. To prevent actuator saturation from altering the commanded trajectory, the node implements a ratio-preserving clamp: if any calculated wheel speed exceeds the physical maximum, all four wheels are scaled down proportionally. This ensures the direction of the resultant velocity vector is preserved.

## 3.5 The Digital Twin and Gas-Seeking Algorithm
Before physical assembly, a comprehensive digital twin was developed to validate the gas-seeking controller (`gas_climber`). The simulation environment models a 2D Gaussian gas plume subject to configurable Gaussian noise, mimicking the turbulent nature of real-world chemical dispersion.

The sensor response is modeled using a first-order Exponential Moving Average (EMA) filter to simulate the physical thermal and chemical lag inherent in metal-oxide (MOX) gas sensors:
$$ \text{EMA}_t = \text{EMA}_{t-1} + \alpha (\text{Raw}_t - \text{EMA}_{t-1}) $$

The gas-seeking algorithm utilizes a custom state machine:
1. **PATROL:** Random or waypoint-driven exploration until the EMA-filtered reading crosses a defined threshold.
2. **CLIMB (Drive/Turn):** A modified gradient ascent. The robot drives forward, evaluating the change in gas concentration.
3. **HOME & CAST:** If concentration drops (indicating a local maximum or noise spike), the robot returns to the last known peak and "casts" (probes) at fixed angular offsets to reacquire the gradient.
4. **LOCALISED:** Termination state when the robot remains within a defined radius of the peak concentration for a sustained dwell time.

## 3.6 Verification and Validation Strategy
System validation was conducted via a 180-run automated factorial test harness. The harness evaluated the gas-seeking algorithm across varying detection thresholds, noise levels, and plume configurations. This batch-processing approach allowed for the generation of Receiver Operating Characteristic (ROC) curves, objectively quantifying the trade-off between True Positive Rate (sensitivity) and False Positive Rate. 

Furthermore, this simulation-first methodology revealed critical hardware constraints—specifically, the relationship between the robot's patrol speed and the MOX sensor's integration time—directly informing the mechanical specification of an active sampling pump to reduce the sensor's time constant.

