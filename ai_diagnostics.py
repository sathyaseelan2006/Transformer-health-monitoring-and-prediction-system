"""
Local Edge-Host AI Diagnostic Engine with Retrieval-Augmented Generation (RAG).
Connects to local Ollama (Phi-3 / Llama-3) or uses local grounded knowledge base.
Follows Section X of the research paper.
"""
import json
import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import urllib.request
import urllib.error
from config import CONFIG

logger = logging.getLogger(__name__)

# Grounded Technical Documents Knowledge Base (Local RAG Corpus)
KNOWLEDGE_BASE = [
    {
        "topic": "thermal_overheating_winding",
        "keywords": ["temperature", "hot", "thermal", "overheating", "winding"],
        "guidelines": (
            "IEEE C57.91 / IEC 60076-7 Standard: Winding temperatures exceeding 85°C cause accelerated "
            "insulation paper tensile loss (Arrhenius degradation). Every 6°C rise above thermal limit cuts insulation "
            "life by half. Verify forced cooling (radiators, fans), check for blocked ducting or oil sludge formation. "
            "Recommended tools: Infrared thermographic camera (FLIR), resistance bridge for winding DC resistance."
        ),
        "actions": [
            "De-energize and inspect radiator fan operation and oil circulation valves.",
            "Conduct winding DC resistance test across phases to detect inter-turn short circuits.",
            "Sample insulating oil for Dissolved Gas Analysis (check ethylene C2H4 and ethane C2H6 levels).",
            "Verify ambient cross-ventilation in substation enclosure."
        ]
    },
    {
        "topic": "overload_overcurrent_stress",
        "keywords": ["current", "overload", "load", "amps", "overcurrent"],
        "guidelines": (
            "Overload Operation Guidelines (IEEE Std C57.115): Operating at >150% rated current produces severe I²R "
            "Joule heating and magnetic saturation in core laminations. Arcing risk at tap-changer contacts increases. "
            "Recommended tools: True-RMS clamp meter, power quality analyzer (Class A), thermal imager."
        ),
        "actions": [
            "Perform load redistribution to auxiliary feeder or initiate peak-shedding.",
            "Inspect secondary terminal bushings and cable lug crimps for thermal discoloration.",
            "Verify overcurrent relay trip curve calibration and differential protection settings.",
            "Check bushing current transformer (CT) secondary wiring integrity."
        ]
    },
    {
        "topic": "mechanical_vibration_looseness",
        "keywords": ["vibration", "shaking", "piezoelectric", "mechanical", "noise", "humming"],
        "guidelines": (
            "Vibration Severity Standards (ISO 10816-3): High vibration (>0.5g / >4.5 mm/s RMS) indicates core clamping "
            "bolt slackness, shield plate resonance, magnetostriction degradation, or internal winding displacement. "
            "Recommended tools: Tri-axial accelerometer vibration analyzer, torque wrench, Sweep Frequency Response Analyzer (SFRA)."
        ),
        "actions": [
            "Inspect transformer base anchor bolts and tank clamping hardware; re-torque to manufacturer specifications.",
            "Execute Sweep Frequency Response Analysis (SFRA) to check for axial or radial winding deformation.",
            "Inspect anti-vibration damping pads under transformer base skids.",
            "Check oil pump and cooling fan impeller balance."
        ]
    },
    {
        "topic": "insulating_oil_level_breakdown",
        "keywords": ["oil", "float", "dielectric", "leak", "moisture", "level"],
        "guidelines": (
            "Insulating Mineral Oil Standard (ASTM D877 / IEC 60156): Low oil level exposes live core/coil assemblies "
            "to ambient atmosphere, causing catastrophic flashover and loss of convective heat transfer. "
            "Recommended tools: Oil breakdown voltage (BDV) tester, Karl Fischer moisture titrator, ultrasonic leak detector."
        ),
        "actions": [
            "Immediately check conservator tank glass and main tank gaskets for weepage or active oil leaks.",
            "Draw bottom and top oil samples; test Breakdown Voltage (BDV must exceed 30 kV for distribution class).",
            "Inspect silica gel breather status (pink coloration indicates moisture saturation requiring charge replacement).",
            "Top up with inhibited mineral transformer oil matching ASTM D3487 specifications under dry weather."
        ]
    },
    {
        "topic": "environmental_wildfire_risk",
        "keywords": ["ambient", "fire", "humidity", "wind", "wildfire", "environment"],
        "guidelines": (
            "Wildfire Risk Mitigation (NFPA 850 / Byrne & Patrick fire-weather criteria): High ambient temperatures (>38°C), "
            "low relative humidity (<20%), and strong winds drastically elevate fire receptivity. An external flashover, bushing "
            "puncture, or tank rupture under these conditions can ignite dry perimeter vegetation into a destructive wildfire. "
            "Recommended tools: Kestrel weather meter, spark-arresting inspection cameras, combustible gas sniffer."
        ),
        "actions": [
            "Inspect substation perimeter vegetation defensible clearance (minimum 10-meter gravel firebreak).",
            "Verify explosion vent diaphragm / pressure relief device (PRD) integrity.",
            "Ensure substation dry chemical / water spray fire extinguishing systems are in ready state.",
            "Under high wind/dry alerts, prioritize rapid de-energization over re-closing attempts upon fault."
        ]
    },
    {
        "topic": "overvoltage_insulation_stress",
        "keywords": ["voltage", "overvoltage", "surge", "undervoltage", "stress"],
        "guidelines": (
            "IEEE Std C57.12.00: Sustained overvoltage (>110% nominal) causes core saturation, excessive excitation current, "
            "stray flux heating in metallic structural components, and accelerated dielectric breakdown of winding turn insulation. "
            "Recommended tools: Digital multimeter, insulation resistance (Megger) tester (2.5kV/5kV), transient surge recorder."
        ),
        "actions": [
            "Verify on-load/off-circuit tap changer (OCTC) position and contact alignment.",
            "Test metal oxide surge arresters (MOSA) for leakage current or thermal hotspots.",
            "Perform insulation resistance (IR) test (Winding-to-Earth and Winding-to-Winding).",
            "Review substation incoming grid bus voltage regulation and capacitor bank switching status."
        ]
    }
]

@dataclass
class DiagnosticReport:
    timestamp: str
    likely_cause: str
    severity_code: str       # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    recommended_instruments: List[str]
    technician_playbook: List[str]
    rag_references: List[str]
    model_used: str
    decision_support_disclaimer: str

class LocalAIDiagnosticEngine:
    def __init__(self, ollama_url: str = CONFIG.OLLAMA_BASE_URL, model: str = CONFIG.DEFAULT_LLM_MODEL):
        self.ollama_url = ollama_url
        self.model = model

    def retrieve_relevant_guidelines(self, telemetry_summary: str) -> List[Dict[str, Any]]:
        """RAG retriever: Matches telemetry conditions to local technical standards."""
        query = telemetry_summary.lower()
        scored = []
        for doc in KNOWLEDGE_BASE:
            score = sum(1 for kw in doc["keywords"] if kw in query)
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:3]]

    def is_ollama_available(self) -> bool:
        """Checks if local Ollama runtime is reachable."""
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", headers={"User-Agent": "TransformerHost/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def query_ollama(self, prompt: str) -> Optional[str]:
        """Queries local Ollama inference server."""
        try:
            url = f"{self.ollama_url}/api/generate"
            payload = json.dumps({
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 450}
            }).encode('utf-8')
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data.get("response", "")
        except Exception as e:
            logger.warning(f"Ollama local inference failed or timed out: {e}")
            return None

    def generate_diagnosis(
        self,
        thi: float,
        v_real: float,
        i_real: float,
        t_real: float,
        vib_real: float,
        oil_level: str,
        env_risk: str,
        trip_status: Optional[str] = None
    ) -> DiagnosticReport:
        """
        Executes grounded diagnostic workflow complying with Section X.
        """
        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Telemetry summary for retrieval
        telemetry_terms = []
        if v_real > CONFIG.V_OVERVOLT_LIMIT or v_real < CONFIG.V_UNDERVOLT_LIMIT:
            telemetry_terms.append("voltage surge overvoltage stress")
        if i_real > CONFIG.I_OVERLOAD_LIMIT or i_real > 12.0:
            telemetry_terms.append("current overload overcurrent heating")
        if t_real > CONFIG.T_NOMINAL + 15.0:
            telemetry_terms.append("temperature hot thermal overheating winding")
        if vib_real > CONFIG.VIB_NOMINAL * 2.0:
            telemetry_terms.append("vibration shaking piezoelectric mechanical")
        if oil_level != "NORMAL":
            telemetry_terms.append("oil float dielectric leak breakdown")
        if env_risk in ["HIGH", "EXTREME"]:
            telemetry_terms.append("ambient fire humidity wind wildfire environment")

        summary_str = " ".join(telemetry_terms) if telemetry_terms else "normal operation baseline"
        retrieved_docs = self.retrieve_relevant_guidelines(summary_str)

        # Severity determination
        if trip_status or thi < CONFIG.THI_CRITICAL_THRESHOLD or oil_level == "CRITICAL":
            severity = "CRITICAL"
        elif thi < CONFIG.THI_WARNING_THRESHOLD or env_risk == "EXTREME":
            severity = "HIGH"
        elif thi < 85.0 or env_risk == "HIGH":
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # Check if Ollama is running
        ollama_active = self.is_ollama_available()
        ollama_output = None

        if ollama_active:
            rag_context = "\n".join([f"- {d['topic'].upper()}: {d['guidelines']}" for d in retrieved_docs])
            prompt = f"""
You are an expert power transformer maintenance diagnostician for an Intelligent Grid Network.
A transformer edge node reported an anomaly.

CURRENT TELEMETRY:
- THI (Health Index): {thi}/100
- Voltage: {v_real} V (Nominal: {CONFIG.V_NOMINAL}V)
- Current: {i_real} A (Nominal: {CONFIG.I_NOMINAL}A)
- Temperature: {t_real} °C (Nominal: {CONFIG.T_NOMINAL}°C, Max: {CONFIG.T_MAX}°C)
- Vibration: {vib_real} g (Nominal: {CONFIG.VIB_NOMINAL}g)
- Oil Level: {oil_level}
- Environmental Risk: {env_risk}
- Trip State: {trip_status or 'None'}

RETRIEVED TECHNICAL KNOWLEDGE:
{rag_context}

Provide a concise technical response formatted with:
1. Likely Root Cause Explanation
2. Recommended Inspection Instruments
3. Step-by-Step Field Technician Playbook
Remember: You are a decision-support tool; deterministic relay safety is handled locally by the edge controller.
"""
            ollama_output = self.query_ollama(prompt)

        # Build structured output
        if ollama_output:
            likely_cause = f"AI Diagnosis ({self.model}):\n" + ollama_output[:250] + "..."
            model_tag = f"Local Ollama ({self.model})"
        else:
            # Deterministic offline RAG generation
            causes = []
            if v_real > CONFIG.V_OVERVOLT_LIMIT:
                causes.append(f"Grid overvoltage condition ({v_real}V) causing excitation core saturation")
            if i_real > CONFIG.I_OVERLOAD_LIMIT:
                causes.append(f"Severe phase overload ({i_real}A) generating severe Joule heating")
            if t_real > CONFIG.T_MAX:
                causes.append(f"Elevated winding temperature ({t_real}°C) causing accelerated cellulose paper aging")
            if vib_real > CONFIG.VIB_NOMINAL * 3:
                causes.append(f"Excessive mechanical vibration ({vib_real}g) indicative of core clamping slackness")
            if oil_level in ["LOW", "CRITICAL"]:
                causes.append(f"Dielectric coolant depletion ({oil_level} oil level) risking winding flashover")
            if env_risk == "EXTREME":
                causes.append("Surrounding hot, dry, and windy micro-climate drastically amplifying collateral fire hazard")

            likely_cause = "; ".join(causes) if causes else "Normal baseline operation with minor operational stress."
            model_tag = "Offline Grounded RAG Expert Engine (Deterministic Fallback)"

        instruments = [
            "Calibrated True-RMS Clamp Multimeter (CAT IV 600V)",
            "Thermal Imaging Camera (FLIR E8 or equivalent)",
            "Insulation Resistance (Megger) Tester 2.5kV / 5kV",
            "Tri-axial Vibration FFT Analyzer",
            "Portable Oil Breakdown Voltage (BDV) Test Cell"
        ]

        # Aggregate technician playbook steps from retrieved knowledge
        playbook = []
        for doc in retrieved_docs:
            playbook.extend(doc.get("actions", []))
        if not playbook:
            playbook = [
                "Verify visual condition of high-voltage and low-voltage bushings.",
                "Inspect silica gel breather condition and color.",
                "Confirm LoRa antenna line-of-sight and battery/supply voltage.",
                "Log routine thermal and current readings in substation logbook."
            ]

        rag_refs = [d["guidelines"] for d in retrieved_docs]

        return DiagnosticReport(
            timestamp=now_str,
            likely_cause=likely_cause,
            severity_code=severity,
            recommended_instruments=instruments,
            technician_playbook=list(dict.fromkeys(playbook)),  # deduplicate preserving order
            rag_references=rag_refs,
            model_used=model_tag,
            decision_support_disclaimer=(
                "IMPORTANT NOTICE (Section VI & X): This AI diagnostic output operates strictly as an advisory "
                "decision-support tool for maintenance operators. Safety-critical protection (overcurrent/thermal relay "
                "tripping) is executed deterministically by the STM32 edge microcontroller independently."
            )
        )
