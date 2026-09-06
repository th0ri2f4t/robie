#pragma once
// R.O.B.I.E. firmware v1 pin map (ESP32 DevKit V1)
// L298N requires IN1/IN2 pairs for direction control

// Motor PWM (LEDC channels 0-3)
#define PIN_M_FL 25
#define PIN_M_FR 26
#define PIN_M_RL 27
#define PIN_M_RR 32

// Motor direction (IN1 / IN2 pairs)
#define PIN_D_FL_1 33
#define PIN_D_FL_2 21
#define PIN_D_FR_1 14
#define PIN_D_FR_2 23
#define PIN_D_RL_1 16
#define PIN_D_RL_2 13
#define PIN_D_RR_1 17
#define PIN_D_RR_2 12

// Safety inputs
#define PIN_ESTOP  4
#define PIN_BUMP_F 5
#define PIN_BUMP_R 18

#define PIN_LED 2

#define PWM_FREQ 20000
#define PWM_RES 8
#define WHEEL_MAX_RAD_S 30.0
#define SAFETY_HZ 20
