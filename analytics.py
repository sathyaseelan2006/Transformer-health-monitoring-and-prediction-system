"""
Analytics and Mathematical Engine for Transformer Health & Risk Assessment
Implements equations (1) - (7) and Environmental Risk Fusion from the paper.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from config import CONFIG, TransformerConfig

@dataclass
class StressIndicators:
    s_v: float       # Voltage stress
    s_i: float       # Current stress
    s_t: float       # Thermal stress
    s_vib: float     # Vibration stress
    thi: float       # Transformer Health Index (0-100)
    health_status: str # "GOOD", "DEGRADED", "WARNING", "CRITICAL"

@dataclass
class EnvironmentalRisk:
    fire_weather_index: float # 0 - 100
    risk_level: str          # "LOW", "MODERATE", "HIGH", "EXTREME"
    consequence_severity: str# "CONTAINED", "ELEVATED HAZARD", "WILDFIRE DISASTER RISK"
    description: str

@dataclass
class EdgeProtectionStatus:
    is_tripped: bool
    trip_reason: Optional[str]
    buzzer_active: bool
    led_alert: bool
    relay_state: str  # "CLOSED (ENERGIZED)" or "OPEN (TRIPPED)"

class TransformerAnalytics:
    def __init__(self, config: TransformerConfig = CONFIG):
        self.config = config

    def compute_stress_and_thi(
        self,
        v_real: float,
        i_real: float,
        t_real: float,
        vib_real: float
    ) -> StressIndicators:
        """
        Computes normalized stress indicators and THI via equations (1) - (4).
        """
        # Eq (1): Voltage stress (normalized 0.0 - 1.0)
        s_v = min(1.0, max(0.0, abs(v_real - self.config.V_NOMINAL) / self.config.V_NOMINAL))
        
        # Eq (1): Current stress (normalized 0.0 - 1.0)
        s_i = min(1.0, max(0.0, abs(i_real - self.config.I_NOMINAL) / self.config.I_NOMINAL))
        
        # Eq (2): Thermal stress (0 if below nominal, normalized 0.0 - 1.0)
        s_t = min(1.0, max(0.0, (t_real - self.config.T_NOMINAL) / (self.config.T_MAX - self.config.T_NOMINAL)))
        
        # Eq (3): Vibration stress (0 if below nominal, normalized 0.0 - 1.0)
        s_vib = min(1.0, max(0.0, (vib_real - self.config.VIB_NOMINAL) / (self.config.VIB_MAX - self.config.VIB_NOMINAL)))
        
        # Eq (4): Transformer Health Index (0-100 scale)
        weighted_stress = (
            self.config.W1 * s_v +
            self.config.W2 * s_i +
            self.config.W3 * s_t +
            self.config.W4 * s_vib
        )
        
        raw_thi = 100.0 - (weighted_stress * 100.0)
        thi = max(0.0, min(100.0, round(raw_thi, 2)))

        if thi >= 85.0:
            status = "OPTIMAL / GOOD"
        elif thi >= self.config.THI_WARNING_THRESHOLD:
            status = "MODERATE / ACCEPTABLE"
        elif thi >= self.config.THI_CRITICAL_THRESHOLD:
            status = "WARNING / DEGRADED"
        else:
            status = "CRITICAL / SEVERE RISK"

        return StressIndicators(
            s_v=round(s_v, 4),
            s_i=round(s_i, 4),
            s_t=round(s_t, 4),
            s_vib=round(s_vib, 4),
            thi=thi,
            health_status=status
        )

    def calculate_rul_and_next_service(
        self,
        current_thi: float,
        thi_history: list[Tuple[datetime, float]]
    ) -> Dict[str, Any]:
        """
        Calculates simple RUL (Eq 6) and degradation slope-based service prediction (Eq 7).
        """
        # Eq (6): Proportional RUL estimate
        rul_years = round(self.config.RATED_DESIGN_LIFE_YEARS * (current_thi / 100.0), 2)
        
        daily_slope = 0.0
        days_to_warning: Optional[float] = None
        projected_service_date: Optional[datetime] = None
        service_date_str = "Stable (Insufficient historical degradation)"

        if len(thi_history) >= 2:
            t_init, thi_init = thi_history[0]
            t_curr, thi_curr = thi_history[-1]
            elapsed_days = max(1e-5, (t_curr - t_init).total_seconds() / 86400.0)
            
            # Eq (7): m = (THI(init) - THI(curr)) / days
            daily_slope = (thi_init - thi_curr) / elapsed_days

            if daily_slope > 0.001:
                # Extrapolate to when THI reaches warning threshold (70%)
                delta_to_threshold = thi_curr - self.config.THI_WARNING_THRESHOLD
                if delta_to_threshold > 0:
                    days_to_warning = delta_to_threshold / daily_slope
                    projected_service_date = t_curr + timedelta(days=days_to_warning)
                    service_date_str = projected_service_date.strftime("%Y-%m-%d (%d days left)")
                else:
                    service_date_str = "Immediate Action Required (THI <= Warning Threshold)"
            else:
                service_date_str = "Degradation Rate Minimal / Stable"

        return {
            "rul_years": rul_years,
            "daily_slope": round(daily_slope, 4),
            "days_to_warning": round(days_to_warning, 1) if days_to_warning is not None else None,
            "projected_service_date": service_date_str
        }

    def evaluate_environmental_risk_fusion(
        self,
        transformer_temp: float,
        ambient_temp: float,
        rel_humidity: float,
        wind_speed: float,
        oil_level: str
    ) -> EnvironmentalRisk:
        """
        Couples equipment telemetry with ambient fire-receptivity variables (Section VIII).
        Differentiates equipment failure likelihood from consequence severity.
        """
        # Environmental dryness and fire vulnerability index (0 to 100)
        temp_factor = max(0.0, min(1.0, (ambient_temp - 20.0) / 30.0))
        dryness_factor = max(0.0, min(1.0, (80.0 - rel_humidity) / 70.0))
        wind_factor = max(0.0, min(1.0, wind_speed / 45.0))
        
        env_index = (0.4 * temp_factor + 0.4 * dryness_factor + 0.2 * wind_factor) * 100.0

        # Equipment vulnerability amplification
        equipment_hot = transformer_temp > self.config.T_TRIP_LIMIT * 0.85
        low_oil = oil_level in ["LOW", "CRITICAL"]

        if env_index > 75.0 or (env_index > 55.0 and (equipment_hot or low_oil)):
            risk_level = "EXTREME"
            severity = "WILDFIRE DISASTER RISK"
            desc = "Dry vegetation, high heat, wind, and hot equipment elevate arcing/fault ignition hazard."
        elif env_index > 50.0:
            risk_level = "HIGH"
            severity = "ELEVATED HAZARD"
            desc = "Sub-optimal ambient conditions; equipment faults may escape local containment."
        elif env_index > 30.0:
            risk_level = "MODERATE"
            severity = "MODERATE RISK"
            desc = "Normal ambient range with mild fire receptivity."
        else:
            risk_level = "LOW"
            severity = "CONTAINED"
            desc = "Cool and humid surroundings; faults confined to equipment casing."

        return EnvironmentalRisk(
            fire_weather_index=round(env_index, 1),
            risk_level=risk_level,
            consequence_severity=severity,
            description=desc
        )

    def evaluate_deterministic_protection(
        self,
        v_real: float,
        i_real: float,
        t_real: float,
        vib_real: float,
        oil_level: str
    ) -> EdgeProtectionStatus:
        """
        Evaluates deterministic edge safety protection (local to STM32).
        Triggers buzzer/LED and relay disconnection for safety violations.
        """
        tripped = False
        reasons = []

        if v_real > self.config.V_OVERVOLT_LIMIT:
            tripped = True
            reasons.append(f"Over-Voltage ({v_real:.1f}V > {self.config.V_OVERVOLT_LIMIT}V)")
        elif v_real < self.config.V_UNDERVOLT_LIMIT:
            tripped = True
            reasons.append(f"Under-Voltage ({v_real:.1f}V < {self.config.V_UNDERVOLT_LIMIT}V)")

        if i_real > self.config.I_OVERLOAD_LIMIT:
            tripped = True
            reasons.append(f"Overload Current ({i_real:.1f}A > {self.config.I_OVERLOAD_LIMIT}A)")

        if t_real > self.config.T_TRIP_LIMIT:
            tripped = True
            reasons.append(f"Winding Over-Temperature ({t_real:.1f}°C > {self.config.T_TRIP_LIMIT}°C)")

        if vib_real > self.config.VIB_TRIP_LIMIT:
            tripped = True
            reasons.append(f"Severe Mechanical Vibration ({vib_real:.2f}g > {self.config.VIB_TRIP_LIMIT}g)")

        if oil_level == "CRITICAL":
            tripped = True
            reasons.append("Critical Insulating Oil Depletion")

        buzzer = tripped or (oil_level == "LOW") or (t_real > self.config.T_MAX)
        led = tripped or (oil_level != "NORMAL")

        return EdgeProtectionStatus(
            is_tripped=tripped,
            trip_reason=", ".join(reasons) if reasons else None,
            buzzer_active=buzzer,
            led_alert=led,
            relay_state="OPEN (TRIPPED / PROTECTED)" if tripped else "CLOSED (ENERGIZED)"
        )

    def classify_alerts(
        self,
        v_real: float,
        i_real: float,
        t_real: float,
        vib_real: float,
        oil_level: str,
        thi: float,
        fwi: float,
        protection: EdgeProtectionStatus
    ) -> List[Dict[str, Any]]:
        """
        Classifies operational alerts into distinct severity tiers and functional categories.
        Severities: CRITICAL, WARNING, ADVISORY, INFO.
        Categories: ELECTRICAL, THERMAL, MECHANICAL, OIL_DIELECTRIC, ENVIRONMENTAL, PROTECTION_TRIP.
        """
        alerts = []

        # 1. Protection Trip (CRITICAL)
        if protection.is_tripped:
            alerts.append({
                "severity": "CRITICAL",
                "category": "PROTECTION_TRIP",
                "code": "PROT-TRIP-01",
                "title": "Hardware Circuit Breaker Tripped",
                "message": f"Deterministic safety interlock opened relay: {protection.trip_reason}",
                "value": "OPEN",
                "threshold": "CLOSED",
                "is_tripped": True
            })

        # 2. Thermal Alerts
        if t_real >= self.config.T_TRIP_LIMIT:
            alerts.append({
                "severity": "CRITICAL",
                "category": "THERMAL",
                "code": "TEMP-CRIT-01",
                "title": "Winding Temperature Trip Threshold Exceeded",
                "message": f"Winding temp {t_real:.1f}°C exceeds safe cutoff of {self.config.T_TRIP_LIMIT}°C. Accelerated Arrhenius paper degradation active.",
                "value": f"{t_real:.1f}°C",
                "threshold": f"{self.config.T_TRIP_LIMIT}°C",
                "is_tripped": True
            })
        elif t_real >= 68.0:
            alerts.append({
                "severity": "WARNING",
                "category": "THERMAL",
                "code": "TEMP-WARN-02",
                "title": "Elevated Thermal Loading Trend",
                "message": f"Winding temperature {t_real:.1f}°C approaching continuous operating envelope.",
                "value": f"{t_real:.1f}°C",
                "threshold": "68.0°C",
                "is_tripped": False
            })

        # 3. Electrical Load & Voltage Alerts
        if i_real >= self.config.I_OVERLOAD_LIMIT:
            alerts.append({
                "severity": "CRITICAL",
                "category": "ELECTRICAL",
                "code": "ELEC-CRIT-01",
                "title": "Severe Feeder Overload Current",
                "message": f"Current {i_real:.1f}A is {((i_real/self.config.I_NOMINAL)-1)*100:.0f}% above nominal rating.",
                "value": f"{i_real:.1f}A",
                "threshold": f"{self.config.I_OVERLOAD_LIMIT}A",
                "is_tripped": True
            })
        elif i_real >= 12.5:
            alerts.append({
                "severity": "WARNING",
                "category": "ELECTRICAL",
                "code": "ELEC-WARN-02",
                "title": "High Feeder Load Utilization",
                "message": f"Current load {i_real:.1f}A above 125% continuous duty cycle.",
                "value": f"{i_real:.1f}A",
                "threshold": "12.5A",
                "is_tripped": False
            })

        if v_real > self.config.V_OVERVOLT_LIMIT or v_real < self.config.V_UNDERVOLT_LIMIT:
            alerts.append({
                "severity": "CRITICAL",
                "category": "ELECTRICAL",
                "code": "VOLT-CRIT-03",
                "title": "Voltage Outside Safe Envelope",
                "message": f"Measured voltage {v_real:.1f}V violates grid regulatory tolerance.",
                "value": f"{v_real:.1f}V",
                "threshold": f"{self.config.V_UNDERVOLT_LIMIT}V - {self.config.V_OVERVOLT_LIMIT}V",
                "is_tripped": True
            })
        elif abs(v_real - self.config.V_NOMINAL) > (self.config.V_NOMINAL * 0.06):
            alerts.append({
                "severity": "WARNING",
                "category": "ELECTRICAL",
                "code": "VOLT-WARN-04",
                "title": "Voltage Harmonic / Tap Drift",
                "message": f"Voltage deviation {abs(v_real - self.config.V_NOMINAL):.1f}V from nominal 230V baseline.",
                "value": f"{v_real:.1f}V",
                "threshold": "±6% nominal",
                "is_tripped": False
            })

        # 4. Mechanical Vibration Alerts
        if vib_real >= self.config.VIB_TRIP_LIMIT:
            alerts.append({
                "severity": "CRITICAL",
                "category": "MECHANICAL",
                "code": "VIB-CRIT-01",
                "title": "Severe Core/Tank Mechanical Vibration",
                "message": f"Triaxial piezo vibration {vib_real:.3f}g indicates structural looseness or shield resonance.",
                "value": f"{vib_real:.3f}g",
                "threshold": f"{self.config.VIB_TRIP_LIMIT}g",
                "is_tripped": True
            })
        elif vib_real >= 0.20:
            alerts.append({
                "severity": "WARNING",
                "category": "MECHANICAL",
                "code": "VIB-WARN-02",
                "title": "Elevated Vibration Spectrum",
                "message": f"Vibration amplitude {vib_real:.3f}g exceeds ISO 10816 class limit.",
                "value": f"{vib_real:.3f}g",
                "threshold": "0.20g",
                "is_tripped": False
            })

        # 5. Oil & Dielectric Alerts
        if oil_level == "CRITICAL":
            alerts.append({
                "severity": "CRITICAL",
                "category": "OIL_DIELECTRIC",
                "code": "OIL-CRIT-01",
                "title": "Critical Insulating Oil Depletion",
                "message": "Tank oil level critical. Winding insulation exposed to dry atmosphere arcing risk.",
                "value": "CRITICAL",
                "threshold": "NORMAL",
                "is_tripped": True
            })
        elif oil_level == "LOW":
            alerts.append({
                "severity": "WARNING",
                "category": "OIL_DIELECTRIC",
                "code": "OIL-WARN-02",
                "title": "Low Insulating Oil Reserve",
                "message": "Oil level below nominal sensor threshold; schedule top-up and BDV test.",
                "value": "LOW",
                "threshold": "NORMAL",
                "is_tripped": False
            })

        # 6. Environmental FWI Alerts
        if fwi >= 75.0:
            alerts.append({
                "severity": "CRITICAL",
                "category": "ENVIRONMENTAL",
                "code": "ENV-CRIT-01",
                "title": "Extreme Wildfire Exposure Condition",
                "message": f"Fire Weather Index at {fwi:.1f}. High wind/dry ambient amplifies flashover consequence.",
                "value": f"{fwi:.1f} FWI",
                "threshold": "75.0 FWI",
                "is_tripped": False
            })
        elif fwi >= 55.0:
            alerts.append({
                "severity": "WARNING",
                "category": "ENVIRONMENTAL",
                "code": "ENV-WARN-02",
                "title": "Elevated Climate Risk Hazard",
                "message": f"Fire Weather Index {fwi:.1f}. Hot and dry conditions warrant closer site inspection.",
                "value": f"{fwi:.1f} FWI",
                "threshold": "55.0 FWI",
                "is_tripped": False
            })

        # 7. Routine Nominal Advisory / Info
        if not alerts:
            alerts.append({
                "severity": "INFO",
                "category": "SYSTEM_HEARTBEAT",
                "code": "SYS-NOM-01",
                "title": "Nominal Operating Baseline",
                "message": f"All telemetry metrics within standard margins. Composite THI is healthy at {thi:.1f}/100.",
                "value": f"{thi:.1f} THI",
                "threshold": ">85.0 THI",
                "is_tripped": False
            })

        return alerts

