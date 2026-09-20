package com.gridguard.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

/**
 * EdgeProtectionStatus - Deterministic edge hardware protection state
 * STM32F103 relay and protection logic
 */
@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class EdgeProtectionStatus {

    private Boolean isTripped; // Circuit breaker state
    private String tripReason; // Reason for trip (if tripped)
    private Boolean buzzerActive; // Solenoid buzzer state
    private Boolean ledAlert; // LED alert indicator
    private String relayState; // CLOSED (ENERGIZED) or OPEN (TRIPPED)

    private LocalDateTime tripTimestamp;
    private Double faultVoltage; // Voltage at time of trip
    private Double faultCurrent; // Current at time of trip
    private Double faultTemperature; // Temperature at time of trip

    /**
     * Get human-readable trip reason
     */
    public String getTripReason() {
        return switch (this.tripReason) {
            case "OVERVOLTAGE" -> "Sustained overvoltage detected (>265V)";
            case "UNDERVOLTAGE" -> "Sustained undervoltage detected (<185V)";
            case "OVERCURRENT" -> "Load current exceeded threshold (>15A)";
            case "THERMAL_TRIP" -> "Winding temperature critical (>85°C)";
            case "VIBRATION_ANOMALY" -> "Excessive vibration detected (>0.60g)";
            case "OIL_CRITICAL" -> "Oil level critical - insufficient dielectric";
            case "MANUAL_TRIP" -> "Manually tripped by operator";
            case "COMMUNICATION_LOSS" -> "Communication loss - safety trip";
            default -> "Unknown trip reason";
        };
    }
}
