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
from database import DB
from kafka_service import KAFKA

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
def get_telemetry(scenario: Optional[str] = None):
    global active_custom_override, active_mode
    # 1. Acquire telemetry frame
    if scenario:
        frame = simulator.generate_frame(fault_override=scenario)
    elif active_mode == "ESP32_WIFI" and esp32_latest_frame:
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
            motion_shake=float(c.get("motion_shake", c.get("vibration", 0.05))),
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
        motion_shake=getattr(frame, 'motion_shake', frame.vibration),
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

    # 3. Classify Alerts based on multi-parameter thresholds
    classified_alerts = analytics.classify_alerts(
        v_real=frame.voltage,
        i_real=frame.current,
        t_real=frame.temperature,
        vib_real=frame.vibration,
        oil_level=frame.oil_level,
        thi=stress.thi,
        fwi=env_risk.fire_weather_index,
        protection=prot
    )

    # 4. Stream to Apache Kafka Topics
    kafka_events = KAFKA.publish_telemetry_stream(
        telemetry=frame.to_dict(),
        stress={
            "s_v": stress.s_v, "s_i": stress.s_i, "s_t": stress.s_t,
            "s_vib": stress.s_vib, "thi": stress.thi, "health_status": stress.health_status
        },
        env={"fwi": env_risk.fire_weather_index, "level": env_risk.risk_level, "severity": env_risk.consequence_severity},
        protection={"is_tripped": prot.is_tripped, "trip_reason": prot.trip_reason, "relay_state": prot.relay_state},
        alerts=classified_alerts
    )

    # 5. Persist to MySQL Database (with SQLite fallback)
    db_result = DB.record_telemetry_and_events(
        telemetry=frame.to_dict(),
        stress={"s_v": stress.s_v, "s_i": stress.s_i, "s_t": stress.s_t, "s_vib": stress.s_vib, "thi": stress.thi, "health_status": stress.health_status},
        env={"fwi": env_risk.fire_weather_index, "level": env_risk.risk_level, "severity": env_risk.consequence_severity, "description": env_risk.description},
        protection={"is_tripped": prot.is_tripped, "trip_reason": prot.trip_reason, "relay_state": prot.relay_state},
        alerts=classified_alerts,
        kafka_events=kafka_events
    )

    # 6. Update history buffers
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

    # 7. Service prediction
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
            "fused_risk_score": env_risk.fused_risk_score,
            "level": env_risk.risk_level,
            "severity": env_risk.consequence_severity,
            "description": env_risk.description,
            "rust_corrosion_risk": env_risk.rust_corrosion_risk,
            "seismic_shake_risk": env_risk.seismic_shake_risk,
            "thermal_ambient_risk": env_risk.thermal_ambient_risk,
            "dew_point_temp": env_risk.dew_point_temp,
            "condensation_status": env_risk.condensation_status,
            "seismic_status": env_risk.seismic_status,
            "corrosion_rate_category": env_risk.corrosion_rate_category,
            "mitigation_action": env_risk.mitigation_action
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
        "alerts": classified_alerts,
        "kafka": KAFKA.get_kafka_metrics(),
        "database": DB.get_database_status(),
        "prediction": service_pred,
        "history": history,
        "mode": active_mode,
        "is_serial_connected": receiver.is_connected()
    }

@app.get("/api/status-performance")
def get_status_and_performance():
    """Endpoint for the LIVE Status & Performance mission control cockpit."""
    if active_mode == "ESP32_WIFI" and esp32_latest_frame:
        frame = esp32_latest_frame
    elif active_mode == "SERIAL" and receiver.is_connected():
        frame = receiver.read_frame() or simulator.generate_frame("NORMAL")
    else:
        frame = simulator.generate_frame()

    stress = analytics.compute_stress_and_thi(frame.voltage, frame.current, frame.temperature, frame.vibration)
    env_risk = analytics.evaluate_environmental_risk_fusion(
        frame.temperature, frame.ambient_temp, frame.rel_humidity,
        getattr(frame, 'motion_shake', frame.vibration), frame.wind_speed, frame.oil_level
    )
    prot = analytics.evaluate_deterministic_protection(
        frame.voltage, frame.current, frame.temperature, frame.vibration, frame.oil_level
    )
    alerts = analytics.classify_alerts(
        frame.voltage, frame.current, frame.temperature, frame.vibration,
        frame.oil_level, stress.thi, env_risk.fire_weather_index, prot
    )

    critical_count = sum(1 for a in alerts if a.get("severity") == "CRITICAL")
    warning_count = sum(1 for a in alerts if a.get("severity") == "WARNING")

    # Determine overall live status
    if prot.is_tripped:
        live_status = "CRITICAL / TRIPPED"
        status_color = "red"
    elif stress.thi < 50.0 or critical_count > 0:
        live_status = "SEVERE RISK / EMERGENCY"
        status_color = "red"
    elif stress.thi < 70.0 or warning_count > 0:
        live_status = "DEGRADED / ELEVATED LOAD"
        status_color = "amber"
    else:
        live_status = "ENERGIZED / OPTIMAL NOMINAL"
        status_color = "green"

    return {
        "asset_id": frame.device_id or "STM32-TX01",
        "substation": "Node Alpha (Feeder 04)",
        "live_status": live_status,
        "status_color": status_color,
        "thi": stress.thi,
        "load_utilization_pct": round((frame.current / CONFIG.I_NOMINAL) * 100, 1),
        "thermal_headroom_c": round(max(0.0, CONFIG.T_TRIP_LIMIT - frame.temperature), 1),
        "dielectric_integrity": "COMPROMISED" if frame.oil_level != "NORMAL" else "OPTIMAL (>30 kV BDV)",
        "mechanical_stability": "VIBRATION EXCURSION" if frame.vibration > 0.4 else "STABLE (0.05g base)",
        "active_alerts_count": {"critical": critical_count, "warning": warning_count, "total": len(alerts)},
        "recent_alerts": alerts,
        "kafka_stream": KAFKA.get_recent_stream_events(limit=15),
        "kafka_metrics": KAFKA.get_kafka_metrics(),
        "database": DB.get_database_status(),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

@app.get("/api/alerts")
def get_alerts_list(severity: Optional[str] = "ALL", limit: int = 30):
    """Fetches classified alerts from active database with severity filter."""
    return {
        "alerts": DB.get_classified_alerts(limit=limit, severity=severity),
        "filter": severity,
        "total": len(DB.get_classified_alerts(limit=limit, severity=severity))
    }

@app.post("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert_endpoint(alert_id: int):
    """Acknowledges an active alert in the database."""
    success = DB.acknowledge_alert(alert_id)
    return {"status": "ok" if success else "error", "alert_id": alert_id}

@app.get("/api/kafka/events")
def get_kafka_live_events():
    """Returns real-time Kafka event streams."""
    return {
        "events": KAFKA.get_recent_stream_events(limit=30),
        "metrics": KAFKA.get_kafka_metrics()
    }

@app.get("/api/database/status")
def get_db_status():
    """Returns MySQL and SQLite status."""
    return DB.get_database_status()

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
