package com.gridguard.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * StressIndicators - Normalized stress components and THI
 * Equations (1)-(4) from research paper
 */
@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class StressIndicators {

    private Double voltageStress; // Sv - Normalized 0.0 to 1.0
    private Double currentStress; // Si - Normalized 0.0 to 1.0
    private Double thermalStress; // St - Normalized 0.0 to 1.0
    private Double vibrationStress; // Svib - Normalized 0.0 to 1.0

    private Double thi; // Transformer Health Index (0-100)
    private String healthStatus; // OPTIMAL/GOOD, MODERATE/ACCEPTABLE, WARNING/DEGRADED, CRITICAL/SEVERE

    private Double weightedStress; // Weighted sum of all stresses

    /**
     * Determine health status based on THI value
     */
    public String getHealthStatus() {
        if (this.thi >= 85.0) {
            return "OPTIMAL / GOOD";
        } else if (this.thi >= 70.0) {
            return "MODERATE / ACCEPTABLE";
        } else if (this.thi >= 50.0) {
            return "WARNING / DEGRADED";
        } else {
            return "CRITICAL / SEVERE RISK";
        }
    }
}
