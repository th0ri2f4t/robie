#pragma once
// R.O.B.I.E. firmware v1 pin map (ESP32 DevKit V1)
// Reconcile against the CTO chatbot's wiring diagram at assembly time.

// Motor PWM (LEDC channels 0-3)
#define PIN_M_FL 25
#define PIN_M_FR 26
#define PIN_M_RL 27
#define PIN_M_RR 32

// Motor direction
#define PIN_D_FL 33
#define PIN_D_FR 14
#define PIN_D_RL 16
#define PIN_D_RR 17

// Safety inputs (active LOW, internal pull-up)
// NOTE: GPIO 34-39 have NO internal pull-ups on ESP32; do not use them here.
#define PIN_ESTOP  4
#define PIN_BUMP_F 5
#define PIN_BUMP_R 18

#define PIN_LED 2

#define PWM_FREQ 20000
#define PWM_RES 8
#define WHEEL_MAX_RAD_S 30.0
#define SAFETY_HZ 20