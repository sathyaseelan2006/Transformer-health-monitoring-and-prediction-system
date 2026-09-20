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

@app.get("/api/telemetry")
def get_telemetry():
    global active_custom_override
    # 1. Acquire telemetry frame
    if active_mode == "SERIAL" and receiver.is_connected():
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
    # Fetch current frame and compute diagnosis
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
