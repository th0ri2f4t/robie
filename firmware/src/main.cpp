// R.O.B.I.E. spinal cord v1. Serial protocol (115200 baud, line-based):
//   Pi -> ESP32:  M,<fl>,<fr>,<rl>,<rr>   wheel targets, rad/s
//                 S,<0|1>                 safety enable from motor_arbiter
//   ESP32 -> Pi:  T,<e>,<bf>,<br>         safety inputs @20 Hz
//                 H,<millis>              heartbeat @1 Hz
// Defense in depth: the firmware hard-cuts motors on E-stop regardless of Pi.

#include <Arduino.h>
#include "config.h"

static bool estop = true;   // fail-safe defaults until pins are read
static bool bumpF = true;
static bool bumpR = true;
static bool serialEnable = false;
static float w[4] = {0, 0, 0, 0};
static unsigned long lastSafetyTx = 0;
static unsigned long lastHeartbeat = 0;

static const int pwmPins[4] = {PIN_M_FL, PIN_M_FR, PIN_M_RL, PIN_M_RR};
static const int dirPins[4] = {PIN_D_FL, PIN_D_FR, PIN_D_RL, PIN_D_RR};

static void applyMotors() {
  const bool on = serialEnable && !estop;  // firmware interlock
  for (int i = 0; i < 4; i++) {
    float c = constrain(w[i], -WHEEL_MAX_RAD_S, WHEEL_MAX_RAD_S);
    uint8_t duty = on ? (uint8_t)(fabs(c) / WHEEL_MAX_RAD_S * 255.0f) : 0;
    digitalWrite(dirPins[i], c >= 0.0f ? HIGH : LOW);
    ledcWrite(i, duty);
  }
}

static void readSafetyPins() {
  estop = digitalRead(PIN_ESTOP) == LOW;
  bumpF = digitalRead(PIN_BUMP_F) == LOW;
  bumpR = digitalRead(PIN_BUMP_R) == LOW;
}

static char buf[96];
static int bufLen = 0;

static void handleLine(const char* line) {
  if (line[0] == 'M') {
    float a, b, c, d;
    if (sscanf(line, "M,%f,%f,%f,%f", &a, &b, &c, &d) == 4) {
      w[0] = a; w[1] = b; w[2] = c; w[3] = d;
    }
  } else if (line[0] == 'S') {
    int v = 0;
    if (sscanf(line, "S,%d", &v) == 1) serialEnable = (v == 1);
  }
}

static void pollSerial() {
  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\n') {
      buf[bufLen] = '\0';
      handleLine(buf);
      bufLen = 0;
    } else if (bufLen < (int)sizeof(buf) - 1) {
      buf[bufLen++] = ch;
    }
  }
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) {
    ledcSetup(i, PWM_FREQ, PWM_RES);
    ledcAttachPin(pwmPins[i], i);
    pinMode(dirPins[i], OUTPUT);
  }
  pinMode(PIN_ESTOP, INPUT_PULLUP);
  pinMode(PIN_BUMP_F, INPUT_PULLUP);
  pinMode(PIN_BUMP_R, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT);
  readSafetyPins();
  applyMotors();
  Serial.println("H,ROBIE_FW_V1_BOOT");
}

void loop() {
  readSafetyPins();
  pollSerial();
  applyMotors();

  unsigned long now = millis();
  if (now - lastSafetyTx >= 1000 / SAFETY_HZ) {
    lastSafetyTx = now;
    Serial.printf("T,%d,%d,%d\n", estop ? 1 : 0, bumpF ? 1 : 0, bumpR ? 1 : 0);
  }
  if (now - lastHeartbeat >= 1000) {
    lastHeartbeat = now;
    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
    Serial.printf("H,%lu\n", now);
  }
}