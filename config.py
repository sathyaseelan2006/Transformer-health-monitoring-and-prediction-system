"""
Configuration parameters for Transformer Health & Environmental-Risk Monitoring System
Based on the split-intelligence research paper.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class TransformerConfig:
    # Nominal reference baselines (ESF)
    V_NOMINAL: float = 230.0       # Volts (V_n)
    I_NOMINAL: float = 10.0        # Amperes (I_n)
    T_NOMINAL: float = 30.0        # Celsius (T_n)
    T_MAX: float = 80.0            # Max allowable operating temperature (T_max)
    VIB_NOMINAL: float = 0.05      # Vibration reference baseline in g (Vib_n)
    VIB_MAX: float = 0.50          # Max vibration threshold in g (Vib_max)

    # Threshold limits for deterministic edge protection
    V_UNDERVOLT_LIMIT: float = 185.0
    V_OVERVOLT_LIMIT: float = 265.0
    I_OVERLOAD_LIMIT: float = 15.0
    T_TRIP_LIMIT: float = 85.0
    VIB_TRIP_LIMIT: float = 0.60
    
    # THI Weights (Sum = 1.0)
    # W1: Voltage, W2: Current, W3: Temperature, W4: Vibration
    W1: float = 0.25
    W2: float = 0.35
    W3: float = 0.25
    W4: float = 0.15

    # Asset Design Life & Maintenance thresholds
    RATED_DESIGN_LIFE_YEARS: float = 25.0   # L_rated
    THI_WARNING_THRESHOLD: float = 70.0     # Threshold triggering AI diagnostic layer
    THI_CRITICAL_THRESHOLD: float = 50.0    # Severe degradation threshold
    
    # Environmental risk baseline
    AMBIENT_TEMP_HIGH: float = 38.0        # deg C
    AMBIENT_HUMIDITY_LOW: float = 25.0      # % RH
    WIND_SPEED_HIGH: float = 30.0          # km/h

    # Hardware & Telemetry
    ADC_RESOLUTION: int = 4095             # 12-bit ADC (STM32F103)
    ADC_VREF: float = 3.3                  # STM32 reference voltage
    DEFAULT_SERIAL_PORT: str = "COM3"
    DEFAULT_BAUD_RATE: int = 115200

    # Offline AI Engine (Ollama)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    DEFAULT_LLM_MODEL: str = "phi3"        # or "llama3"

CONFIG = TransformerConfig()
