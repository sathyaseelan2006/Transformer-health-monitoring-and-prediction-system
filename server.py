"""
FastAPI Backend Server for Transformer Health & Risk Monitor.
Serves the custom HTML/CSS/JS frontend and provides real-time telemetry APIs.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

from config import CONFIG
from analytics import TransformerAnalytics
from telemetry import LoRaSerialReceiver, TelemetryFrame
from simulator import TransformerSimulator
from ai_diagnostics import LocalAIDiagnosticEngine

app = FastAPI(title="GridGuard Substation Mission Control API")

# Core singletons
analytics = TransformerAnalytics(CONFIG)
simulator = TransformerSimulator()
ai_engine = LocalAIDiagnosticEngine(CONFIG.OLLAMA_BASE_URL, CONFIG.DEFAULT_LLM_MODEL)
receiver = LoRaSerialReceiver(port=CONFIG.DEFAULT_SERIAL_PORT, baudrate=CONFIG.DEFAULT_BAUD_RATE)

# In-memory history buffer
history = []
thi_history = []
active_mode = "SIMULATION"
active_custom_override: Optional[Dict[str, Any]] = None
esp32_latest_frame: Optional[TelemetryFrame] = None
esp32_last_heartbeat: Optional[datetime] = None

# Initialize some historical wear data
base_t = datetime.now() - timedelta(days=20)
for d in range(20):
    t_pt = base_t + timedelta(days=d)
    thi_val = 97.0 - (d * 0.45)
    thi_history.append((t_pt, thi_val))

class ScenarioRequest(BaseModel):
    scenario: str
    custom_params: Optional[Dict[str, Any]] = None

class DiagnoseRequest(BaseModel):
    override: Optional[bool] = False

class Esp32TelemetryPayload(BaseModel):
    device_id: Optional[str] = "ESP32-TX01"
    voltage: float
    current: float
    temperature: float
    vibration: float
    oil_level: Optional[str] = "NORMAL"
    ambient_temp: Optional[float] = 28.5
    rel_humidity: Optional[float] = 46.0
    wind_speed: Optional[float] = 11.2
    health_index: Optional[float] = None

@app.post("/api/telemetry")
def receive_esp32_telemetry(payload: Esp32TelemetryPayload):
    global esp32_latest_frame, esp32_last_heartbeat, active_mode
    esp32_last_heartbeat = datetime.now()
    active_mode = "ESP32_WIFI"
    
    esp32_latest_frame = TelemetryFrame(
        timestamp=esp32_last_heartbeat,
        voltage=payload.voltage,
        current=payload.current,
        temperature=payload.temperature,
        vibration=payload.vibration,
        oil_level=payload.oil_level.upper() if payload.oil_level else "NORMAL",
        ambient_temp=payload.ambient_temp or 28.5,
        rel_humidity=payload.rel_humidity or 46.0,
        wind_speed=payload.wind_speed or 11.2,
        device_id=payload.device_id or "ESP32-TX01",
        edge_thi=payload.health_index
    )
    return {"status": "ok", "mode": "ESP32_WIFI", "received_at": esp32_last_heartbeat.strftime("%H:%M:%S")}

@app.get("/api/component-health")
def get_component_health():
    # Fetch current frame for component health analysis
    if active_mode == "ESP32_WIFI" and esp32_latest_frame:
        frame = esp32_latest_frame
    elif active_mode == "SERIAL" and receiver.is_connected():
        frame = receiver.read_frame() or simulator.generate_frame("NORMAL")
    else:
        frame = simulator.generate_frame()

    stress = analytics.compute_stress_and_thi(
        v_real=frame.voltage,
        i_real=frame.current,
        t_real=frame.temperature,
        vib_real=frame.vibration
    )

    component_predictions = ai_engine.predict_component_health(
        thi=stress.thi,
        v_real=frame.voltage,
        i_real=frame.current,
        t_real=frame.temperature,
        vib_real=frame.vibration,
        oil_level=frame.oil_level
    )
    return component_predictions

@app.get("/api/telemetry")
def get_telemetry():
    global active_custom_override, active_mode
    # 1. Acquire telemetry frame
    if active_mode == "ESP32_WIFI" and esp32_latest_frame:
        # Check if ESP32 frame is recent (within 10 seconds)
        if esp32_last_heartbeat and (datetime.now() - esp32_last_heartbeat).total_seconds() < 10.0:
            frame = esp32_latest_frame
        else:
            # Fallback if ESP32 timed out
            frame = simulator.generate_frame()
    elif active_mode == "SERIAL" and receiver.is_connected():
        frame = receiver.read_frame()
        if not frame:
            frame = simulator.generate_frame("NORMAL")
    elif active_custom_override:

        c = active_custom_override
        frame = TelemetryFrame(
            timestamp=datetime.now(),
            voltage=float(c.get("voltage", 230.0)),
            current=float(c.get("current", 10.0)),
            temperature=float(c.get("temperature", 34.0)),
            vibration=float(c.get("vibration", 0.05)),
            oil_level=str(c.get("oil_level", "NORMAL")).upper(),
            ambient_temp=float(c.get("ambient_temp", 28.0)),
            rel_humidity=float(c.get("rel_humidity", 45.0)),
            wind_speed=float(c.get("wind_speed", 12.0)),
            device_id="STM32-TX01"
        )
    else:
        frame = simulator.generate_frame()

    # 2. Run Analytics
    stress = analytics.compute_stress_and_thi(
        v_real=frame.voltage,
        i_real=frame.current,
        t_real=frame.temperature,
        vib_real=frame.vibration
    )

    env_risk = analytics.evaluate_environmental_risk_fusion(
        transformer_temp=frame.temperature,
        ambient_temp=frame.ambient_temp,
        rel_humidity=frame.rel_humidity,
        wind_speed=frame.wind_speed,
        oil_level=frame.oil_level
    )

    prot = analytics.evaluate_deterministic_protection(
        v_real=frame.voltage,
        i_real=frame.current,
        t_real=frame.temperature,
        vib_real=frame.vibration,
        oil_level=frame.oil_level
    )

    # 3. Update history buffers
    now_ts = datetime.now()
    thi_history.append((now_ts, stress.thi))
    if len(thi_history) > 120:
        thi_history.pop(0)

    rec = frame.to_dict()
    rec["thi"] = stress.thi
    rec["s_v"] = stress.s_v
    rec["s_i"] = stress.s_i
    rec["s_t"] = stress.s_t
    rec["s_vib"] = stress.s_vib
    rec["relay_tripped"] = prot.is_tripped
    rec["time_str"] = now_ts.strftime("%H:%M:%S")
    history.append(rec)
    if len(history) > 40:
        history.pop(0)

    # 4. Service prediction
    service_pred = analytics.calculate_rul_and_next_service(stress.thi, thi_history)

    return {
        "telemetry": frame.to_dict(),
        "stress": {
            "s_v": stress.s_v,
            "s_i": stress.s_i,
            "s_t": stress.s_t,
            "s_vib": stress.s_vib,
            "thi": stress.thi,
            "health_status": stress.health_status
        },
        "environmental_risk": {
            "fwi": env_risk.fire_weather_index,
            "level": env_risk.risk_level,
            "severity": env_risk.consequence_severity,
            "description": env_risk.description
        },
        "protection": {
            "is_tripped": prot.is_tripped,
            "trip_reason": prot.trip_reason,
            "buzzer": prot.buzzer_active,
            "led": prot.led_alert,
            "relay_state": prot.relay_state
        },
        "lora": {
            "frequency": "433.175 MHz",
            "spreading_factor": "SF7 / BW 125 kHz",
            "coding_rate": "4/5 CR",
            "rssi": -76.8 if active_mode == "ESP32_WIFI" else (-82.4 if active_mode == "SERIAL" else -78.0),
            "snr": 9.8 if active_mode == "ESP32_WIFI" else (8.4 if active_mode == "SERIAL" else 9.2),
            "packet_loss": 0.0,
            "gateway_status": "ONLINE (P2P Link Active)",
            "packet_count": len(history),
            "edge_sampling": "100 Hz / 12-bit ADC",
            "payload_size": "32 bytes (packed IEEE-754)"
        },
        "prediction": service_pred,
        "history": history,
        "mode": active_mode,
        "is_serial_connected": receiver.is_connected()
    }

@app.post("/api/scenario")
def set_scenario(req: ScenarioRequest):
    global active_mode, active_custom_override
    active_mode = "SIMULATION"
    if req.scenario == "CUSTOM" and req.custom_params:
        active_custom_override = req.custom_params
    else:
        active_custom_override = None
        simulator.set_fault_mode(req.scenario)
    return {"status": "ok", "scenario": req.scenario}

@app.post("/api/diagnose")
def trigger_diagnostics(req: DiagnoseRequest):
    # Fetch current active frame for accurate diagnosis
    if active_mode == "ESP32_WIFI" and esp32_latest_frame:
        frame = esp32_latest_frame
    elif active_mode == "SERIAL" and receiver.is_connected():
        frame = receiver.read_frame() or simulator.generate_frame("NORMAL")
    elif active_custom_override:
        c = active_custom_override
        frame = TelemetryFrame(
            timestamp=datetime.now(),
            voltage=float(c.get("voltage", 230.0)),
            current=float(c.get("current", 10.0)),
            temperature=float(c.get("temperature", 34.0)),
            vibration=float(c.get("vibration", 0.05)),
            oil_level=str(c.get("oil_level", "NORMAL")).upper(),
            ambient_temp=float(c.get("ambient_temp", 28.0)),
            rel_humidity=float(c.get("rel_humidity", 45.0)),
            wind_speed=float(c.get("wind_speed", 12.0)),
            device_id="STM32-TX01"
        )
    else:
        frame = simulator.generate_frame()

    stress = analytics.compute_stress_and_thi(frame.voltage, frame.current, frame.temperature, frame.vibration)
    env_risk = analytics.evaluate_environmental_risk_fusion(
        frame.temperature, frame.ambient_temp, frame.rel_humidity, frame.wind_speed, frame.oil_level
    )
    prot = analytics.evaluate_deterministic_protection(
        frame.voltage, frame.current, frame.temperature, frame.vibration, frame.oil_level
    )

    report = ai_engine.generate_diagnosis(
        thi=stress.thi,
        v_real=frame.voltage,
        i_real=frame.current,
        t_real=frame.temperature,
        vib_real=frame.vibration,
        oil_level=frame.oil_level,
        env_risk=env_risk.risk_level,
        trip_status=prot.trip_reason
    )

    return {
        "timestamp": report.timestamp,
        "likely_cause": report.likely_cause,
        "severity_code": report.severity_code,
        "recommended_instruments": report.recommended_instruments,
        "technician_playbook": report.technician_playbook,
        "rag_references": report.rag_references,
        "model_used": report.model_used,
        "disclaimer": report.decision_support_disclaimer
    }

# Mount static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_index():
    return FileResponse("static/index.html")

@app.get("/analytics")
def serve_analytics():
    return FileResponse("static/analytics.html")

# The dashboard uses root-relative asset URLs while the API remains under /api.
app.mount("/", StaticFiles(directory="static"), name="root-static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
