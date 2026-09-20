"""
Unit tests and verification for Transformer Health Monitoring System.
Tests ESF, THI equations (1)-(4), RUL (6), degradation slope (7),
protection logic, telemetry serialization, and RAG diagnostics.
"""
import unittest
from datetime import datetime, timedelta
from config import CONFIG
from analytics import TransformerAnalytics
from telemetry import LoRaSerialReceiver, TelemetryFrame
from simulator import TransformerSimulator
from ai_diagnostics import LocalAIDiagnosticEngine

class TestTransformerSystem(unittest.TestCase):
    def setUp(self):
        self.analytics = TransformerAnalytics(CONFIG)
        self.simulator = TransformerSimulator()
        self.ai_engine = LocalAIDiagnosticEngine()

    def test_nominal_stress_and_thi(self):
        """Under perfect nominal conditions, stress indicators should be 0 and THI should be 100."""
        res = self.analytics.compute_stress_and_thi(
            v_real=CONFIG.V_NOMINAL,
            i_real=CONFIG.I_NOMINAL,
            t_real=CONFIG.T_NOMINAL,
            vib_real=CONFIG.VIB_NOMINAL
        )
        self.assertEqual(res.s_v, 0.0)
        self.assertEqual(res.s_i, 0.0)
        self.assertEqual(res.s_t, 0.0)
        self.assertEqual(res.s_vib, 0.0)
        self.assertEqual(res.thi, 100.0)
        self.assertEqual(res.health_status, "OPTIMAL / GOOD")

    def test_paper_stressed_bench_condition(self):
        """
        Section XIII in paper: Under representative stressed overload test condition,
        the prototype computed a THI of 59.
        """
        res = self.analytics.compute_stress_and_thi(
            v_real=236.0,
            i_real=19.4,
            t_real=35.0,
            vib_real=0.18
        )
        self.assertTrue(55.0 <= res.thi <= 65.0, f"Expected THI around 59, got {res.thi}")
        self.assertIn("DEGRADED", res.health_status)

    def test_deterministic_protection_trip(self):
        """Test overvoltage and overload relay trips."""
        # Overvoltage trip
        prot_ov = self.analytics.evaluate_deterministic_protection(
            v_real=270.0, i_real=10.0, t_real=30.0, vib_real=0.05, oil_level="NORMAL"
        )
        self.assertTrue(prot_ov.is_tripped)
        self.assertIn("Over-Voltage", prot_ov.trip_reason)
        self.assertIn("TRIPPED", prot_ov.relay_state)

        # Overload trip
        prot_ol = self.analytics.evaluate_deterministic_protection(
            v_real=230.0, i_real=18.0, t_real=30.0, vib_real=0.05, oil_level="NORMAL"
        )
        self.assertTrue(prot_ol.is_tripped)
        self.assertIn("Overload Current", prot_ol.trip_reason)

    def test_environmental_risk_fusion(self):
        """Test environmental wildfire risk calculation."""
        # Cool, humid conditions
        env_mild = self.analytics.evaluate_environmental_risk_fusion(
            transformer_temp=32.0, ambient_temp=22.0, rel_humidity=75.0, wind_speed=5.0, oil_level="NORMAL"
        )
        self.assertEqual(env_mild.risk_level, "LOW")

        # Extreme conditions: 44°C, 12% humidity, 38 km/h wind + hot transformer
        env_extreme = self.analytics.evaluate_environmental_risk_fusion(
            transformer_temp=78.0, ambient_temp=44.0, rel_humidity=12.0, wind_speed=38.0, oil_level="LOW"
        )
        self.assertEqual(env_extreme.risk_level, "EXTREME")
        self.assertEqual(env_extreme.consequence_severity, "WILDFIRE DISASTER RISK")

    def test_degradation_slope_and_service_date(self):
        """Test slope m calculation and service prediction."""
        t0 = datetime.now() - timedelta(days=10)
        t1 = datetime.now()
        history = [(t0, 95.0), (t1, 85.0)] # 10 points dropped in 10 days => m = 1.0 THI/day
        res = self.analytics.calculate_rul_and_next_service(85.0, history)
        self.assertAlmostEqual(res["daily_slope"], 1.0, places=1)
        # From 85 down to warning threshold 70 => 15 days left
        self.assertAlmostEqual(res["days_to_warning"], 15.0, places=0)

    def test_json_telemetry_parser(self):
        """Test JSON telemetry parsing matching LoRa SX1278 stream."""
        json_sample = '{"voltage": 235.5, "current": 11.2, "temperature": 36.0, "vibration": 0.08, "oil_level": "NORMAL", "ambient_temp": 29.0, "rel_humidity": 48.0, "wind_speed": 14.0}'
        frame = LoRaSerialReceiver.parse_json_payload(json_sample)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.voltage, 235.5)
        self.assertEqual(frame.current, 11.2)
        self.assertEqual(frame.oil_level, "NORMAL")

    def test_ai_diagnostic_engine(self):
        """Test local RAG diagnostic report generation."""
        report = self.ai_engine.generate_diagnosis(
            thi=55.0,
            v_real=230.0,
            i_real=19.0,
            t_real=88.0,
            vib_real=0.08,
            oil_level="LOW",
            env_risk="HIGH",
            trip_status="Overload Current"
        )
        self.assertEqual(report.severity_code, "CRITICAL")
        self.assertTrue(len(report.recommended_instruments) > 0)
        self.assertTrue(len(report.technician_playbook) > 0)
        self.assertIn("decision-support", report.decision_support_disclaimer)

if __name__ == "__main__":
    unittest.main()
