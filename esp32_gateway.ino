#include <WiFi.h>
#include <HTTPClient.h>

// Wi-Fi Credentials for Reno11
const char* ssid     = "Reno11";
const char* password = "9790419564";

// Backend API URL on laptop (current IP on Reno11 hotspot)
const char* serverUrl = "http://10.153.163.136:8080/api/telemetry";

// Serial2 pins connected to STM32 (PA9 -> RX2, PA10 not needed for one-way telemetry)
#define RXD2 16

void setup() {
  Serial.begin(9600);
  Serial2.begin(9600, SERIAL_8N1, RXD2, -1); // -1 disables TX to prevent pin contention
  Serial2.setTimeout(100); // 100ms timeout for non-blocking UART read

  // Lower RF transmit power to prevent chip heating while maintaining reliable Wi-Fi
  WiFi.setTxPower(WIFI_POWER_15dBm);

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
    Serial.println("\n[WARN] Wi-Fi connection pending. Listening on UART...");
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
        http.setTimeout(2500); // 2.5s timeout prevents blocking loop
        http.addHeader("Content-Type", "application/json");

        int httpResponseCode = http.POST(jsonTelemetry);
        if (httpResponseCode > 0) {
          Serial.println("[ESP32 -> Dashboard] Success (HTTP " + String(httpResponseCode) + ")");
        } else {
          Serial.println("[ESP32 -> Dashboard] HTTP Error: " + http.errorToString(httpResponseCode));
        }
        http.end();
      } else {
        static unsigned long lastReconnect = 0;
        if (millis() - lastReconnect > 10000) {
          lastReconnect = millis();
          Serial.println("[WARN] Wi-Fi disconnected. Reconnecting...");
          WiFi.begin(ssid, password);
        }
      }
    }
  }
  delay(50);
}
