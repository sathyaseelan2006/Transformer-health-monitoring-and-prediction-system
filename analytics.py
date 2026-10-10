"""
Analytics and Mathematical Engine for Transformer Health & Risk Assessment
Implements equations (1) - (7) and Environmental Risk Fusion from the paper.
"""
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from config import CONFIG, TransformerConfig

@dataclass
class StressIndicators:
    s_v: float       # Voltage stress (0.0 - 1.0)
    s_i: float       # Current overload stress (0.0 - 1.0)
    s_t: float       # Thermal stress (0.0 - 1.0)
    s_vib: float     # Vibration stress (0.0 - 1.0)
    thi: float       # Transformer Health Index (0-100)
    health_status: str # "OPTIMAL / GOOD", "MODERATE / ACCEPTABLE", "WARNING / DEGRADED", "CRITICAL / SEVERE RISK"

    # Physics-Grounded IEEE C57.91 / IEC 60076-7 Degradation Parameters
    hot_spot_temp: float = 30.0         # °C Winding Hot-Spot Temperature (Theta_H)
    f_aa: float = 1.0                  # IEEE C57.91 Aging Acceleration Factor (Arrhenius: 1.0 at 110°C)
    dp_estimated: float = 1000.0       # Cellulose Degree of Polymerization (200=brittle paper failure, 1000=new)
    loss_of_life_rate: float = 1.0     # Relative aging consumption rate multiplier (1.0 = normal consumption)
    physics_model: str = "IEEE C57.91 Arrhenius Kinetics"

@dataclass
class EnvironmentalRisk:
    fused_risk_score: float      # 0 - 100 (%) Multi-sensor fused environmental risk
    risk_level: str              # "LOW", "MODERATE", "HIGH", "EXTREME"
    consequence_severity: str    # "CONTAINED", "ELEVATED HAZARD", "SEVERE DAMAGE HAZARD"
    description: str
    
    # Physical sensor derived sub-risks
    rust_corrosion_risk: float   # 0 - 100 (%) Rust possibility from Temp + Humidity
    seismic_shake_risk: float    # 0 - 100 (%) Earthquake / shake structural damage from motion sensor
    thermal_ambient_risk: float  # 0 - 100 (%) Ambient thermal stress
    
    # Environmental indicators
    dew_point_temp: float        # °C
    condensation_status: str     # "DRY / SAFE", "ELEVATED DEW RISK", "ACTIVE CONDENSATION"
    seismic_status: str          # "QUIET / STABLE", "MILD SHAKE", "EARTHQUAKE DETECTED", "CRITICAL SEISMIC"
    corrosion_rate_category: str # "MINIMAL (<0.01 mm/yr)", "MODERATE (C2-C3)", "AGGRESSIVE (C4-C5)"
    mitigation_action: str       # Actionable maintenance advice
    
    # Backward compatibility
    fire_weather_index: float = 0.0

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
        Computes IEEE C57.91 physics-grounded stress indicators, Arrhenius aging acceleration factor,
        cellulose insulation Degree of Polymerization (DP), and composite THI.
        """
        # Eq (1): Voltage deviation stress (normalized 0.0 - 1.0)
        s_v = min(1.0, max(0.0, abs(v_real - self.config.V_NOMINAL) / self.config.V_NOMINAL))
        
        # Eq (1): Current overload stress (normalized 0.0 - 1.0, proportional to I^2 loss profile)
        s_i = min(1.0, max(0.0, abs(i_real - self.config.I_NOMINAL) / self.config.I_NOMINAL))
        
        # Eq (2): Thermal stress (0 if below nominal, normalized 0.0 - 1.0)
        s_t = min(1.0, max(0.0, (t_real - self.config.T_NOMINAL) / (self.config.T_MAX - self.config.T_NOMINAL)))
        
        # Eq (3): Vibration stress (0 if below nominal, normalized 0.0 - 1.0)
        s_vib = min(1.0, max(0.0, (vib_real - self.config.VIB_NOMINAL) / (self.config.VIB_MAX - self.config.VIB_NOMINAL)))
        
        # --- IEEE C57.91 / IEC 60076-7 Winding Hot-Spot & Arrhenius Degradation Physics ---
        # 1. Winding Hottest-Spot Temperature Theta_H = T_oil + Delta_Theta_H_rated * (I / I_rated)^1.6
        load_ratio = max(0.0, i_real / max(1e-3, self.config.I_NOMINAL))
        rated_gradient = 18.0  # °C rated winding-to-top-oil gradient for distribution transformers
        hot_spot_grad = rated_gradient * (load_ratio ** 1.6) if load_ratio > 0.05 else 0.0
        hot_spot_temp = round(t_real + hot_spot_grad, 1)

        # 2. IEEE C57.91 Aging Acceleration Factor F_AA = exp(15000/383.15 - 15000/(Theta_H + 273.15))
        # Reference temperature = 110 °C (383.15 K). Doubles every ~6°C (Montsinger's Rule)
        theta_clamped = max(-20.0, min(240.0, hot_spot_temp))
        arrhenius_exponent = (15000.0 / 383.15) - (15000.0 / (theta_clamped + 273.15))
        f_aa = round(math.exp(arrhenius_exponent), 3)

        # Eq (4): Baseline Weighted Multi-Factor Stress
        weighted_stress = (
            self.config.W1 * s_v +
            self.config.W2 * s_i +
            self.config.W3 * s_t +
            self.config.W4 * s_vib
        )
        
        # If thermal aging accelerates severely (F_AA > 1.2), apply Arrhenius non-linear penalty
        arrhenius_penalty = min(0.25, max(0.0, (f_aa - 1.0) * 0.035)) if f_aa > 1.0 else 0.0
        effective_stress = min(1.0, weighted_stress + arrhenius_penalty)

        raw_thi = 100.0 - (effective_stress * 100.0)
        thi = max(0.0, min(100.0, round(raw_thi, 2)))

        # 3. Solid Cellulose Insulation Degree of Polymerization (DP):
        # Fresh Kraft paper: DP = 1000 - 1200; End-of-life mechanical tear limit: DP <= 200
        dp_est = round(200.0 + 800.0 * (thi / 100.0), 1)

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
            health_status=status,
            hot_spot_temp=hot_spot_temp,
            f_aa=f_aa,
            dp_estimated=dp_est,
            loss_of_life_rate=round(f_aa, 2),
            physics_model="IEEE C57.91 Arrhenius Kinetics"
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
        motion_shake: float = 0.05,
        wind_speed: float = 10.0,
        oil_level: str = "NORMAL"
    ) -> EnvironmentalRisk:
        """
        Multi-Sensor Environmental Risk Fusion (Prototype Sensors: Temp, Humidity, Motion).
        Calculates:
          1. Rust & Corrosion Possibility Index (Temp + Humidity + Dew Point Condensation)
          2. Seismic & Shake Structural Damage Risk (Motion / Tremor Sensor)
          3. Thermal Ambient Degradation Stress
          4. Fused Composite Environmental Risk (0-100%)
        """
        # A. Dew Point & Condensation Calculation (Magnus-Tetens Psychrometric formula: a = 17.27, b = 237.7 °C)
        rh_clamped = max(0.01, min(100.0, rel_humidity))
        gamma = (17.27 * ambient_temp) / (237.7 + ambient_temp) + math.log(rh_clamped / 100.0)
        dew_point = round((237.7 * gamma) / (17.27 - gamma), 1)
        dew_margin = round(ambient_temp - dew_point, 1)

        if dew_margin <= 2.0 or rel_humidity >= 85.0:
            condensation_status = "ACTIVE CONDENSATION (HIGH RUST HAZARD)"
            cond_factor = 1.45
        elif dew_margin <= 4.0 or rel_humidity >= 70.0:
            condensation_status = "ELEVATED DEW RISK (SURFACE MOISTURE)"
            cond_factor = 1.25
        else:
            condensation_status = "DRY / SAFE (NO CONDENSATION)"
            cond_factor = 1.0

        # B. Rust & Atmospheric Corrosion Risk Calculation (ISO 9223 Kinetics)
        # Steel tank & cooling fin oxidation accelerates with RH > 50% and elevated temperature
        rh_factor = max(0.0, min(1.0, (rel_humidity - 40.0) / 50.0))
        temp_corrosion_factor = max(0.1, min(1.0, (ambient_temp - 10.0) / 35.0))
        raw_rust = (0.65 * rh_factor + 0.35 * temp_corrosion_factor) * 100.0 * cond_factor
        rust_risk = round(min(100.0, max(0.0, raw_rust)), 1)

        if rust_risk > 75.0:
            corrosion_cat = "AGGRESSIVE (ISO C4/C5 - Rapid Rusting)"
        elif rust_risk > 45.0:
            corrosion_cat = "MODERATE (ISO C3 - Gradual Oxidation)"
        else:
            corrosion_cat = "MINIMAL (ISO C1/C2 - Passivated Dry)"

        # C. Seismic / Earth Tremor & Motion Shake Risk Calculation
        # Motion sensor detection of ground shaking / earthquakes / structural tilt
        raw_shake = (motion_shake / 0.50) * 100.0
        seismic_risk = round(min(100.0, max(0.0, raw_shake)), 1)

        if motion_shake >= 0.45:
            seismic_status = "CRITICAL SEISMIC SHOCK / TREMOR (M >= 5.0)"
        elif motion_shake >= 0.20:
            seismic_status = "EARTHQUAKE TREMOR DETECTED (M 3.0 - 4.5)"
        elif motion_shake >= 0.08:
            seismic_status = "MILD MECHANICAL SHAKE / TILT"
        else:
            seismic_status = "QUIET / STABLE FOUNDATION"

        # D. Thermal Ambient Stress
        raw_thermal = ((ambient_temp - 25.0) / 25.0) * 100.0
        thermal_risk = round(min(100.0, max(0.0, raw_thermal)), 1)

        # E. Fused Composite Environmental Risk Score (0.45 Rust + 0.40 Shake + 0.15 Thermal)
        fused_score = round(0.45 * rust_risk + 0.40 * seismic_risk + 0.15 * thermal_risk, 1)

        # Classification & Actionable Mitigation Advice
        if fused_score >= 75.0 or seismic_risk >= 80.0 or rust_risk >= 85.0 or (wind_speed >= 35.0 and rel_humidity <= 15.0):
            risk_level = "EXTREME"
            severity = "WILDFIRE DISASTER RISK" if (wind_speed >= 30.0 and rel_humidity <= 20.0) else "SEVERE DAMAGE HAZARD"
            desc = f"Severe multi-factor risk: {seismic_status.lower()} and {corrosion_cat.lower()}."
            action = "Dispatch immediate emergency inspection: check anchor bolts, radiator fin oxidation, and foundation dampeners."
        elif fused_score >= 50.0:
            risk_level = "HIGH"
            severity = "ELEVATED HAZARD"
            desc = f"High environmental stress: {seismic_status.lower()}, rust potential {rust_risk}%."
            action = "Schedule preventative tank recoating, verify anti-vibration mountings, and inspect enclosure seals."
        elif fused_score >= 38.0:
            risk_level = "MODERATE"
            severity = "MODERATE EXPOSURE"
            desc = f"Moderate ambient exposure: {corrosion_cat.lower()}, stable foundation."
            action = "Routine environmental monitoring; ensure proper enclosure drainage and ventilation."
        else:
            risk_level = "LOW"
            severity = "OPTIMAL / SAFE"
            desc = "Dry surroundings, minimal rust kinetics, stable foundation with no seismic motion."
            action = "All environmental parameters optimal. Continue automated monitoring."

        return EnvironmentalRisk(
            fused_risk_score=fused_score,
            risk_level=risk_level,
            consequence_severity=severity,
            description=desc,
            rust_corrosion_risk=rust_risk,
            seismic_shake_risk=seismic_risk,
            thermal_ambient_risk=thermal_risk,
            dew_point_temp=dew_point,
            condensation_status=condensation_status,
            seismic_status=seismic_status,
            corrosion_rate_category=corrosion_cat,
            mitigation_action=action,
            fire_weather_index=fused_score
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

        # 6. Environmental Multi-Sensor Risk Alerts (Temp, Humidity, Motion)
        if fwi >= 75.0:
            alerts.append({
                "severity": "CRITICAL",
                "category": "ENVIRONMENTAL",
                "code": "ENV-CRIT-01",
                "title": "Severe Environmental Threat (Earthquake / Aggressive Rust)",
                "message": f"Composite Environmental Risk at {fwi:.1f}%. High risk of structural shake damage or rapid tank corrosion.",
                "value": f"{fwi:.1f}% ERF",
                "threshold": "75.0% ERF",
                "is_tripped": False
            })
        elif fwi >= 50.0:
            alerts.append({
                "severity": "WARNING",
                "category": "ENVIRONMENTAL",
                "code": "ENV-WARN-02",
                "title": "Elevated Environmental Corrosion / Tremor Hazard",
                "message": f"Environmental Risk Index {fwi:.1f}%. High humidity condensation or mechanical ground tremor detected.",
                "value": f"{fwi:.1f}% ERF",
                "threshold": "50.0% ERF",
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

