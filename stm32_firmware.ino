#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <OneWire.h>
#include <DallasTemperature.h>

/* STM32F103C8T6 Blue Pill transformer monitor.
 * USB CDC serial output is newline-delimited JSON for the backend & web dashboard.
 * Real-time threshold validation, audio buzzer alarm, deterministic relay trip,
 * and status LED management.
 */

LiquidCrystal_I2C lcd(0x27, 16, 2);

/* ------------ PIN DEFINITIONS ------------ */
#define ONE_WIRE_BUS PA2
#define VOLTAGE_PIN PA0
#define CURRENT_PIN PA1
#define VIBRATION_PIN PA3
#define OIL_PIN PB0
#define RELAY PB8
#define BUZZER PB9
#define RESET_BUTTON PB10
#define OVERLOAD_SWITCH PB11
#define GREEN_LED PB12
#define YELLOW_LED PB13
#define RED_LED PB14

/* ------------ CALIBRATED SENSOR THRESHOLD LIMITS ------------ */
#define VOLTAGE_MIN_LIMIT 185.0f   // Minimum safe voltage (V)
#define VOLTAGE_MAX_LIMIT 265.0f   // Maximum safe voltage (V)
#define CURRENT_LIMIT 4.0f         // Overload current trip limit (A)
#define TEMP_LIMIT 40.0f           // High temperature trip limit (°C)
#define VIBRATION_LIMIT 0.50f      // Vibration anomaly threshold (g)
#define HEALTH_CRITICAL_LIMIT 40.0f // Critical THI cutoff (0-100)
#define CURRENT_SAMPLES 1000

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature temperatureSensor(&oneWire);

/* ------------ GLOBAL SENSOR VARIABLES ------------ */
float voltage = 0.0f;
float current = 0.0f;
float temperature = 0.0f;
float vibration = 0.0f;
float healthIndex = 100.0f;
float remainingLife = 20.0f;
float faultPenalty = 0.0f;

int oilState = HIGH;          // HIGH = Normal, LOW = Low Oil Alert
int vibrationAdc = 0;
int overloadState = HIGH;     // HIGH = Normal, LOW = Overload Trip Pressed
int lastOverloadState = HIGH;

/* ------------ ALARM & PROTECTION FLAGS ------------ */
bool buzzerActive = false;
bool dangerActive = false;
bool isRelayTripped = false;
String activeTripReason = "Deterministic edge logic normal";

void setup() {
  Serial.begin(9600);
  analogReadResolution(12);

  pinMode(RELAY, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(OIL_PIN, INPUT_PULLUP);
  pinMode(RESET_BUTTON, INPUT_PULLUP);
  pinMode(OVERLOAD_SWITCH, INPUT_PULLUP);

  digitalWrite(RELAY, HIGH); // Closed / Energized
  digitalWrite(BUZZER, LOW); // Buzzer OFF initially
  digitalWrite(GREEN_LED, HIGH);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(RED_LED, LOW);

  temperatureSensor.begin();

  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("TRANSFORMER");
  lcd.setCursor(0, 1);
  lcd.print("HEALTH MONITOR");
  delay(2000);
  lcd.clear();
}

void loop() {
  readSensors();
  calculateHealth();
  checkThresholdsAndFaults();
  updateIndicatorsAndRelay();
  displayData();
  resetSystem();
  sendTelemetryJson();
  delay(1000);
}

void readSensors() {
  // 1. DS18B20 Temperature Sensor
  temperatureSensor.requestTemperatures();
  float measuredTemperature = temperatureSensor.getTempCByIndex(0);
  if (measuredTemperature != DEVICE_DISCONNECTED_C && measuredTemperature > -50.0f && measuredTemperature < 150.0f) {
    temperature = measuredTemperature;
  }

  // 2. AC/DC Voltage Sensor
  int voltageAdc = analogRead(VOLTAGE_PIN);
  voltage = (voltageAdc * 3.3f / 4095.0f) * 100.0f;

  // 3. Current Sensor (1000-sample averaging for clean RMS)
  long currentSum = 0;
  for (int sample = 0; sample < CURRENT_SAMPLES; sample++) {
    currentSum += analogRead(CURRENT_PIN);
  }
  current = ((currentSum / (float) CURRENT_SAMPLES) * 3.3f / 4095.0f) * 30.0f;

  // 4. Vibration Piezo Sensor
  vibrationAdc = analogRead(VIBRATION_PIN);
  vibration = (vibrationAdc / 4095.0f) * 1.5f;

  // 5. Digital Oil Level & Overload Switch
  oilState = digitalRead(OIL_PIN);
  overloadState = digitalRead(OVERLOAD_SWITCH);
}

void calculateHealth() {
  float thermalStress = (temperature / TEMP_LIMIT) * 30.0f;
  float electricalStress = (current / CURRENT_LIMIT) * 30.0f;
  float oilStress = (oilState == LOW) ? 20.0f : 0.0f;
  float vibrationStress = (vibration > VIBRATION_LIMIT || vibrationAdc > 500) ? 20.0f : 0.0f;

  healthIndex = 100.0f - (thermalStress + electricalStress + oilStress + vibrationStress + faultPenalty);
  healthIndex = constrain(healthIndex, 0.0f, 100.0f);
  remainingLife = (healthIndex / 100.0f) * 20.0f;
}

/* ------------ THRESHOLD VALIDATION & BUZZER TRIGGER ------------ */
void checkThresholdsAndFaults() {
  bool faultDetected = false;
  String reason = "";

  // 1. Temperature Threshold Breach
  if (temperature > TEMP_LIMIT) {
    faultDetected = true;
    reason += "TEMP HIGH TRIP (" + String(temperature, 1) + "C); ";
    faultPenalty += 0.5f;
  }

  // 2. Insulating Oil Level Drop / Breach
  if (oilState == LOW) {
    faultDetected = true;
    reason += "OIL LEVEL LOW; ";
    faultPenalty += 1.0f;
  }

  // 3. Mechanical Vibration Anomaly
  if (vibration > VIBRATION_LIMIT || vibrationAdc > 500) {
    faultDetected = true;
    reason += "HIGH VIBRATION (" + String(vibration, 2) + "g); ";
    faultPenalty += 0.5f;
  }

  // 4. Current Overload Threshold
  if (current > CURRENT_LIMIT) {
    faultDetected = true;
    reason += "CURRENT OVERLOAD (" + String(current, 1) + "A); ";
    faultPenalty += 0.8f;
  }

  // 5. Voltage Envelope Breach (Under-voltage / Over-voltage)
  if (voltage > VOLTAGE_MAX_LIMIT) {
    faultDetected = true;
    reason += "OVER-VOLTAGE (" + String(voltage, 0) + "V); ";
    faultPenalty += 0.6f;
  } else if (voltage < VOLTAGE_MIN_LIMIT && voltage > 10.0f) {
    faultDetected = true;
    reason += "UNDER-VOLTAGE (" + String(voltage, 0) + "V); ";
    faultPenalty += 0.4f;
  }

  // 6. Overload Switch Trip
  if (overloadState == LOW) {
    faultDetected = true;
    reason += "MANUAL OVERLOAD TRIP; ";
    faultPenalty += 1.0f;
  }

  // 7. Critical Health Index Degradation
  if (healthIndex <= HEALTH_CRITICAL_LIMIT) {
    faultDetected = true;
    reason += "CRITICAL THI DEGRADATION; ";
  }

  lastOverloadState = overloadState;
  faultPenalty = min(faultPenalty, 100.0f);

  if (faultDetected) {
    buzzerActive = true;
    dangerActive = true;
    isRelayTripped = true;
    activeTripReason = reason;
  } else {
    buzzerActive = false;
    dangerActive = false;
    isRelayTripped = false;
    activeTripReason = "Deterministic edge logic normal";
  }
}

/* ------------ HARDWARE ACTUATORS (RELAY, BUZZER, LEDS) ------------ */
void updateIndicatorsAndRelay() {
  if (dangerActive || buzzerActive) {
    // Danger / Buzzer Alarm Active: Ring buzzer, illuminate RED LED, trip relay
    digitalWrite(BUZZER, HIGH);
    digitalWrite(RED_LED, HIGH);
    digitalWrite(YELLOW_LED, LOW);
    digitalWrite(GREEN_LED, LOW);
    digitalWrite(RELAY, LOW); // Relay Tripped / Open
  } else {
    // Normal / Non-critical Operation: Buzzer silenced, Relay closed
    digitalWrite(BUZZER, LOW);
    digitalWrite(RELAY, HIGH); // Relay Closed / Energized

    if (healthIndex > 60.0f) {
      digitalWrite(GREEN_LED, HIGH);
      digitalWrite(YELLOW_LED, LOW);
      digitalWrite(RED_LED, LOW);
    } else if (healthIndex > 40.0f) {
      digitalWrite(GREEN_LED, LOW);
      digitalWrite(YELLOW_LED, HIGH);
      digitalWrite(RED_LED, LOW);
    } else {
      digitalWrite(GREEN_LED, LOW);
      digitalWrite(YELLOW_LED, LOW);
      digitalWrite(RED_LED, HIGH);
    }
  }
}

/* ------------ LCD DISPLAY ROUTINE ------------ */
void displayData() {
  static int screen = 0;
  lcd.clear();

  if (dangerActive || buzzerActive) {
    // Urgent Alert Screen when Buzzer / Fault occurs
    lcd.setCursor(0, 0);
    lcd.print("! DANGER ALARM !");
    lcd.setCursor(0, 1);
    if (temperature > TEMP_LIMIT) lcd.print("T HIGH: " + String(temperature, 1) + "C");
    else if (oilState == LOW) lcd.print("OIL LEVEL LOW");
    else if (current > CURRENT_LIMIT) lcd.print("I OVER: " + String(current, 1) + "A");
    else if (vibration > VIBRATION_LIMIT) lcd.print("VIB HIGH: " + String(vibration, 2) + "g");
    else lcd.print("TRIP: " + activeTripReason.substring(0, 16));
    return;
  }

  // Normal rotating status screens
  if (screen == 0) {
    lcd.setCursor(0, 0);
    lcd.print("V:");
    lcd.print(voltage, 0);
    lcd.print(" I:");
    lcd.print(current, 1);
    lcd.setCursor(0, 1);
    lcd.print("T:");
    lcd.print(temperature, 1);
    lcd.print(" HI:");
    lcd.print(healthIndex, 0);
  } else {
    lcd.setCursor(0, 0);
    lcd.print("Life:");
    lcd.print(remainingLife, 1);
    lcd.print("Y");
    lcd.setCursor(0, 1);
    lcd.print("Oil:");
    lcd.print(oilState == LOW ? "LOW " : "OK  ");
    lcd.print(" Vib:");
    lcd.print(vibration, 2);
  }

  screen = (screen + 1) % 2;
}

/* ------------ SYSTEM RESET BUTTON ------------ */
void resetSystem() {
  if (digitalRead(RESET_BUTTON) == LOW) {
    digitalWrite(RELAY, HIGH);
    digitalWrite(BUZZER, LOW);
    digitalWrite(RED_LED, LOW);
    digitalWrite(GREEN_LED, HIGH);
    faultPenalty = 0.0f;
    buzzerActive = false;
    dangerActive = false;
    isRelayTripped = false;
    activeTripReason = "Deterministic edge logic normal";

    lcd.clear();
    lcd.print("SYSTEM RESET OK");
    delay(1200);
  }
}

/* ------------ USB / LORA SERIAL TELEMETRY JSON ------------ */
void sendTelemetryJson() {
  Serial.print("{\"deviceId\":\"STM32-TX01\",\"voltage\":");
  Serial.print(voltage, 2);
  Serial.print(",\"current\":");
  Serial.print(current, 2);
  Serial.print(",\"temperature\":");
  Serial.print(temperature, 2);
  Serial.print(",\"vibration\":");
  Serial.print(vibration, 3);
  Serial.print(",\"oilLevel\":\"");
  Serial.print(oilState == LOW ? "LOW" : "NORMAL");
  Serial.print("\",\"ambientTemp\":28.0,\"relativeHumidity\":45.0,\"windSpeed\":12.0,\"edgeTHI\":");
  Serial.print(healthIndex, 2);
  Serial.print(",\"buzzer\":");
  Serial.print(buzzerActive ? "true" : "false");
  Serial.print(",\"danger\":");
  Serial.print(dangerActive ? "true" : "false");
  Serial.print(",\"relayStatus\":\"");
  Serial.print(isRelayTripped ? "OPEN (TRIPPED)" : "CLOSED (ENERGIZED)");
  Serial.print("\",\"tripReason\":\"");
  Serial.print(activeTripReason);
  Serial.println("\"}");
}
