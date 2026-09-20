package com.gridguard.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * EnvironmentalRisk - Fire-weather index and hazard assessment
 * Section VIII of research paper - Environmental Risk Fusion
 */
@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class EnvironmentalRisk {

    private Double fireWeatherIndex; // FWI Score (0-100)
    private String riskLevel; // LOW, MODERATE, HIGH, EXTREME
    private String consequenceSeverity; // CONTAINED, ELEVATED_HAZARD, WILDFIRE_DISASTER_RISK
    private String description;

    // Component factors
    private Double temperatureFactor;
    private Double drynessFactor;
    private Double windFactor;

    // Ambient conditions
    private Double ambientTemp;
    private Double relativeHumidity;
    private Double windSpeed;
    private String oilLevel;

    /**
     * Get risk level description with action items
     */
    public String getRiskDescription() {
        return switch (this.riskLevel.toUpperCase()) {
            case "LOW" -> "Environmental conditions normal. Transformer operation safe.";
            case "MODERATE" -> "Elevated ambient risk. Monitor conditions. Increase inspection frequency.";
            case "HIGH" ->
                "High fire receptivity. Consider controlled de-energization. Activate perimeter defensible space protocols.";
            case "EXTREME" ->
                "CRITICAL WILDFIRE RISK. Immediate de-energization recommended. Activate emergency procedures.";
            default -> "Risk level unknown";
        };
    }
}
