#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

// Wi-Fi Credentials for Reno11
const char* ssid     = "Reno11";
const char* password = "9790419564";

// Backend API URL on laptop
const char* serverUrl = "http://172.3.2.135:8080/api/telemetry";

// Serial2 pins connected to STM32 (PA9 -> RX2, PA10 -> TX2)
#define RXD2 16
#define TXD2 17

void setup() {
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, RXD2, TXD2);

  Serial.println("\n[ESP32 Gateway] Initializing Wi-Fi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 40) {
    delay(500);
    Serial.print(".");
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[OK] Connected to Wi-Fi: " + String(ssid));
    Serial.println("[OK] ESP32 IP Address: " + WiFi.localIP().toString());
    Serial.println("[OK] Telemetry Target: " + String(serverUrl));
  } else {
    Serial.println("\n[WARN] Wi-Fi connection pending. Retrying in background...");
  }
}

void loop() {
  // Check if STM32 sent a telemetry JSON line
  if (Serial2.available()) {
    String jsonTelemetry = Serial2.readStringUntil('\n');
    jsonTelemetry.trim();

    if (jsonTelemetry.startsWith("{") && jsonTelemetry.endsWith("}")) {
      Serial.println("\n[STM32 -> ESP32] Telemetry: " + jsonTelemetry);

      if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        http.begin(serverUrl);
        http.addHeader("Content-Type", "application/json");

        int httpResponseCode = http.POST(jsonTelemetry);
        if (httpResponseCode > 0) {
          Serial.println("[ESP32 -> Dashboard] Success (HTTP " + String(httpResponseCode) + ")");
        } else {
          Serial.println("[ESP32 -> Dashboard] HTTP Error: " + http.errorToString(httpResponseCode));
        }
        http.end();
      } else {
        Serial.println("[WARN] Wi-Fi disconnected. Reconnecting...");
        WiFi.begin(ssid, password);
      }
    }
  }
  delay(50);
}
