"""
High-fidelity Telemetry Simulator for Transformer Health & Environmental Risk.
Generates real-time sensor streams and supports dynamic fault injection scenarios.
"""
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from telemetry import TelemetryFrame
from config import CONFIG

class TransformerSimulator:
    def __init__(self):
        self.active_fault_mode = "NORMAL"
        self.noise_enabled = True
        self.simulated_day_offset = 0.0

    def set_fault_mode(self, mode: str):
        """Changes active operational or fault scenario."""
        self.active_fault_mode = mode

    def generate_frame(self, fault_override: Optional[str] = None) -> TelemetryFrame:
        mode = fault_override or self.active_fault_mode
        now = datetime.now()

        # Gaussian noise helper
        def noise(std: float) -> float:
            return random.gauss(0.0, std) if self.noise_enabled else 0.0

        if mode == "PAPER_STRESSED_BENCH":
            # Exact representative benchmark condition from Section XIII in paper
            v = 336.0 + noise(1.2)
            i = 79.0 + noise(0.8)
            t = 35.0 + noise(0.3)
            vib = 0.18 + abs(noise(0.02))
            oil = "NORMAL"
            amb_t = 32.0 + noise(0.5)
            rh = 40.0 + noise(1.0)
            wind = 14.0 + noise(1.0)

        elif mode == "OVERVOLTAGE":
            v = 278.0 + noise(2.0)
            i = 10.2 + noise(0.2)
            t = 42.0 + noise(0.5)
            vib = 0.08 + abs(noise(0.01))
            oil = "NORMAL"
            amb_t = 28.0
            rh = 50.0
            wind = 8.0

        elif mode == "OVERLOAD_TRIP":
            v = 224.0 + noise(1.5)
            i = 19.5 + noise(0.4)
            t = 68.0 + noise(1.0)
            vib = 0.22 + abs(noise(0.02))
            oil = "NORMAL"
            amb_t = 30.0
            rh = 45.0
            wind = 10.0

        elif mode == "THERMAL_RUNAWAY":
            v = 228.0 + noise(1.0)
            i = 13.8 + noise(0.3)
            t = 92.5 + noise(0.6)
            vib = 0.12 + abs(noise(0.01))
            oil = "LOW"
            amb_t = 39.0 + noise(0.4)
            rh = 30.0
            wind = 15.0

        elif mode == "VIBRATION_ANOMALY":
            v = 230.5 + noise(1.0)
            i = 10.5 + noise(0.3)
            t = 45.0 + noise(0.5)
            vib = 0.65 + abs(noise(0.05))
            oil = "NORMAL"
            amb_t = 27.0
            rh = 55.0
            wind = 12.0

        elif mode == "OIL_LEAK_CRITICAL":
            v = 229.0 + noise(1.0)
            i = 11.0 + noise(0.2)
            t = 78.0 + noise(0.8)
            vib = 0.15 + abs(noise(0.02))
            oil = "CRITICAL"
            amb_t = 34.0
            rh = 38.0
            wind = 16.0

        elif mode == "EARTHQUAKE_SEISMIC_SHAKE":
            v = 227.0 + noise(1.5)
            i = 10.8 + noise(0.4)
            t = 39.0 + noise(0.5)
            vib = 0.54 + abs(noise(0.04))
            motion = 0.52 + abs(noise(0.05)) # High tremor g-force
            oil = "NORMAL"
            amb_t = 29.0
            rh = 58.0
            wind = 14.0

        elif mode == "HIGH_HUMIDITY_RUST_RISK":
            v = 230.0 + noise(1.0)
            i = 9.5 + noise(0.3)
            t = 36.0 + noise(0.4)
            vib = 0.06 + abs(noise(0.01))
            motion = 0.05 + abs(noise(0.01))
            oil = "NORMAL"
            amb_t = 33.5 + noise(0.3) # Hot ambient
            rh = 88.0 + abs(noise(1.5)) # High humidity causing condensation
            wind = 6.0

        elif mode == "WILDFIRE_ENVIRONMENTAL_HAZARD":
            v = 232.0 + noise(1.0)
            i = 12.5 + noise(0.3)
            t = 74.0 + noise(0.7)
            vib = 0.10 + abs(noise(0.01))
            motion = 0.08 + abs(noise(0.01))
            oil = "LOW"
            amb_t = 43.5 + noise(0.5)
            rh = 14.0 + abs(noise(0.5))
            wind = 39.0 + abs(noise(2.0))

        else:  # NORMAL
            v = 230.0 + noise(1.5)
            i = 9.8 + noise(0.3)
            t = 34.0 + noise(0.4)
            vib = 0.05 + abs(noise(0.008))
            motion = 0.05 + abs(noise(0.008))
            oil = "NORMAL"
            amb_t = 28.0 + noise(0.3)
            rh = 52.0 + noise(1.0)
            wind = 11.0 + noise(1.0)

        # Fallback if motion not set in other branches
        if 'motion' not in locals():
            motion = vib

        return TelemetryFrame(
            timestamp=now,
            voltage=round(max(0.0, v), 1),
            current=round(max(0.0, i), 1),
            temperature=round(max(0.0, t), 1),
            vibration=round(max(0.0, vib), 3),
            oil_level=oil,
            ambient_temp=round(amb_t, 1),
            rel_humidity=round(max(5.0, min(100.0, rh)), 1),
            wind_speed=round(max(0.0, wind), 1),
            motion_shake=round(max(0.0, motion), 3),
            device_id="STM32-TX01"
        )
