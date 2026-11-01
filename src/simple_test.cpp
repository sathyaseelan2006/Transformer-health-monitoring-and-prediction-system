#include <Arduino.h>

#define LED_PIN 2 // Built-in blue LED on most ESP32 DevKit boards

void setup() {
  Serial.begin(9600);
  pinMode(LED_PIN, OUTPUT);
  Serial.println("\n========================================");
  Serial.println("  ESP32 Simple Test Firmware Running!   ");
  Serial.println("  Baud Rate: 9600                       ");
  Serial.println("========================================");
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  Serial.println("[ESP32] LED ON - Tick");
  delay(1000);

  digitalWrite(LED_PIN, LOW);
  Serial.println("[ESP32] LED OFF - Tock");
  delay(1000);
}
