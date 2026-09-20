package com.gridguard.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

/**
 * RULPrediction - Remaining Useful Life & Service Planning
 * Equations (6)-(7) from research paper
 */
@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class RULPrediction {

    private Double rulYears; // Remaining Useful Life in years (Eq. 6)
    private Double dailyDegradationSlope; // m: THI/day degradation rate (Eq. 7)
    private Double daysToWarningThreshold;
    private LocalDateTime projectedServiceDate;
    private String serviceDescription;

    private Double ratedDesignLife; // Original design life (25 years)
    private Double currentTHI; // Current THI value
    private Double warningThreshold; // THI = 70 threshold

    /**
     * Check if immediate service is required
     */
    public boolean isImmediateServiceRequired() {
        return this.currentTHI <= this.warningThreshold;
    }

    /**
     * Get maintenance urgency level
     */
    public String getUrgencyLevel() {
        if (this.daysToWarningThreshold == null || this.daysToWarningThreshold < 0) {
            return "IMMEDIATE";
        } else if (this.daysToWarningThreshold <= 30) {
            return "URGENT";
        } else if (this.daysToWarningThreshold <= 90) {
            return "SCHEDULED";
        } else {
            return "ROUTINE";
        }
    }
}
