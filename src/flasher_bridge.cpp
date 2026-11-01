#include <Arduino.h>

/**
 * ESP32 Hardware UART Bridge for Flashing STM32 Blue Pill.
 *
 * Bridges the PC's USB port (COM8) to the STM32's USART1 bootloader pins:
 *   ESP32 Pin 16 (RX2) <---> STM32 PA9  (TX1)
 *   ESP32 Pin 17 (TX2) <---> STM32 PA10 (RX1)
 *   ESP32 GND          <---> STM32 GND
 *
 * Uses 115200 baud with EVEN parity (SERIAL_8E1) required by the
 * STM32 factory ROM bootloader (ST Application Note AN2606 / AN3155).
 */

#define RXD2 16  // Hardware UART2 RX -> connects to STM32 PA9
#define TXD2 17  // Hardware UART2 TX -> connects to STM32 PA10
#define LED_PIN 2 // Onboard status LED

void setup() {
  // 1. USB Serial connection to PC (115200, 8 data bits, Even parity, 1 stop bit)
  Serial.begin(115200, SERIAL_8E1);

  // 2. Hardware UART2 connected to STM32 USART1 Bootloader
  Serial2.begin(115200, SERIAL_8E1, RXD2, TXD2);

  // 3. Status indicator LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH); // LED ON indicates flasher bridge is active
}

void loop() {
  // Forward bytes from PC (USB) -> STM32 (Serial2)
  while (Serial.available()) {
    Serial2.write(Serial.read());
  }

  // Forward bytes from STM32 (Serial2) -> PC (USB)
  while (Serial2.available()) {
    Serial.write(Serial2.read());
  }
}
