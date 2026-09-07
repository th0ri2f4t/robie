#pragma once
// R.O.B.I.E. firmware pin map v3 — matched to actual 30-pin DevKit silkscreen
// LEFT header  -> FRONT L298N (FL/FR)
// RIGHT header -> REAR L298N (RL/RR)

// Motor PWM (LEDC channels 0-3)
#define PIN_M_FL 19   // left
#define PIN_M_FR 22   // left
#define PIN_M_RL 27   // right
#define PIN_M_RR 26   // right

// Motor direction (L298N IN1/IN2 pairs)
#define PIN_D_FL_1 21 // left
#define PIN_D_FL_2 23 // left
#define PIN_D_FR_1 17 // left, silk RX2
#define PIN_D_FR_2 15 // left
#define PIN_D_RL_1 33 // right
#define PIN_D_RL_2 32 // right
#define PIN_D_RR_1 14 // right
#define PIN_D_RR_2 13 // right

// Safety inputs (HIGH = stop / HIGH = obstacle; NC wiring)
#define PIN_ESTOP  4  // left
#define PIN_BUMP_F 5  // left
#define PIN_BUMP_R 18 // left

#define PIN_LED 2     // left, heartbeat

// RESERVED — do not repurpose:
// GPIO 34, 35 (right, silk D34/D35): MQ-4/MQ-6 analog via divider (input-only pins, ideal for ADC)
// GPIO 16 (left, silk TX2), GPIO 25, GPIO 12 (right): spares

#define PWM_FREQ 20000
#define PWM_RES 8
#define WHEEL_MAX_RAD_S 30.0
#define SAFETY_HZ 20
