"""
Telemetry acquisition and serial parser for LoRa SX1278 receiver.
Parses compact JSON telemetry frames transmitted by the STM32 edge node.
"""
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any, Generator

logger = logging.getLogger(__name__)

@dataclass
class TelemetryFrame:
    timestamp: datetime
    voltage: float           # V_real
    current: float           # I_real
    temperature: float       # T_real
    vibration: float         # Vib_real
    oil_level: str           # NORMAL / LOW / CRITICAL
    ambient_temp: float      # Celsius
    rel_humidity: float      # %
    wind_speed: float        # km/h
    motion_shake: float = 0.05 # g-force / shake amplitude (SW-420 / Accelerometer)
    device_id: str = "STM32-TX01"
    edge_thi: Optional[float] = None
    relay_status: Optional[str] = "CLOSED"
    buzzer: Optional[bool] = False
    danger: Optional[bool] = False
    trip_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        return data

class LoRaSerialReceiver:
    def __init__(self, port: str = "COM3", baudrate: int = 115200, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self._is_connected = False

    def connect(self) -> bool:
        """Attempts connection to the physical serial port."""
        try:
            import serial
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            self._is_connected = True
            logger.info(f"Connected to LoRa receiver on {self.port}")
            return True
        except Exception as e:
            logger.warning(f"Could not connect to serial port {self.port}: {e}")
            self._is_connected = False
            return False

    def is_connected(self) -> bool:
        return self._is_connected and self.serial_conn is not None and self.serial_conn.is_open

    def read_frame(self) -> Optional[TelemetryFrame]:
        """Reads a single line of JSON telemetry from the serial stream."""
        if not self.is_connected():
            return None
        try:
            line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                return None
            return self.parse_json_payload(line)
        except Exception as e:
            logger.error(f"Error reading serial line: {e}")
            return None

    @staticmethod
    def parse_json_payload(json_str: str) -> Optional[TelemetryFrame]:
        """Parses a compact JSON string into a TelemetryFrame."""
        try:
            payload = json.loads(json_str)
            raw_relay = str(payload.get("relayStatus", payload.get("relay_status", "CLOSED"))).upper()
            raw_buzzer = bool(payload.get("buzzer", False))
            raw_danger = bool(payload.get("danger", False))
            raw_trip_reason = payload.get("tripReason") or payload.get("trip_reason")

            return TelemetryFrame(
                timestamp=datetime.now(),
                voltage=float(payload.get("voltage", 230.0)),
                current=float(payload.get("current", 10.0)),
                temperature=float(payload.get("temperature", 30.0)),
                vibration=float(payload.get("vibration", 0.05)),
                oil_level=str(payload.get("oilLevel", payload.get("oil_level", "NORMAL"))).upper(),
                ambient_temp=float(payload.get("ambientTemp", payload.get("ambient_temp", 25.0))),
                rel_humidity=float(payload.get("relativeHumidity", payload.get("rel_humidity", 50.0))),
                wind_speed=float(payload.get("windSpeed", payload.get("wind_speed", 10.0))),
                motion_shake=float(payload.get("motion_shake", payload.get("motion", payload.get("vibration", 0.05)))),
                device_id=str(payload.get("deviceId", payload.get("device_id", "STM32-TX01"))),
                edge_thi=float(payload.get("edgeTHI", payload.get("thi", 0.0))) if ("edgeTHI" in payload or "thi" in payload) else None,
                relay_status=raw_relay,
                buzzer=raw_buzzer,
                danger=raw_danger,
                trip_reason=raw_trip_reason
            )
        except Exception as e:
            logger.error(f"Failed to parse JSON telemetry: {e}")
            return None

    def disconnect(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self._is_connected = False
