package com.gridguard.service;

import com.gridguard.config.TransformerConfig;
import com.gridguard.model.*;
import com.gridguard.repository.TelemetryFrameRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.List;

/**
 * AnalyticsService - Core analytics engine
 * Implements equations (1)-(7) from research paper
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class AnalyticsService {

    private final TransformerConfig config;
    private final TelemetryFrameRepository telemetryRepository;

    /**
     * Compute stress indicators and THI (Equations 1-4)
     */
    public StressIndicators computeStressAndTHI(TelemetryFrame frame) {
        TransformerConfig.TransformerProperties props = config.getTransformer();
        TransformerConfig.WeightProperties weights = config.getWeights();

        // Eq (1): Voltage stress - normalized deviation from nominal
        Double voltageStress = Math.min(1.0, Math.max(0.0,
                Math.abs(frame.getVoltage() - props.getNominalVoltage()) / props.getNominalVoltage()));

        // Eq (1): Current stress - normalized deviation from nominal
        Double currentStress = Math.min(1.0, Math.max(0.0,
                Math.abs(frame.getCurrent() - props.getNominalCurrent()) / props.getNominalCurrent()));

        // Eq (2): Thermal stress - only if above nominal, normalized 0-1
        Double thermalStress = Math.min(1.0, Math.max(0.0,
                (frame.getTemperature() - props.getNominalTemperature()) /
                        (props.getMaxTemperature() - props.getNominalTemperature())));

        // Eq (3): Vibration stress - only if above nominal, normalized 0-1
        Double vibrationStress = Math.min(1.0, Math.max(0.0,
                (frame.getVibration() - 0.05) / (0.50 - 0.05)));

        // Eq (4): Transformer Health Index with weighted stress
        Double weightedStress = weights.getVoltageStress() * voltageStress +
                weights.getCurrentStress() * currentStress +
                weights.getThermalStress() * thermalStress +
                weights.getVibrationStress() * vibrationStress;

        Double rawTHI = 100.0 - (weightedStress * 100.0);
        Double thi = Math.max(0.0, Math.min(100.0, Math.round(rawTHI * 100.0) / 100.0));

        return StressIndicators.builder()
                .voltageStress(Math.round(voltageStress * 10000.0) / 10000.0)
                .currentStress(Math.round(currentStress * 10000.0) / 10000.0)
                .thermalStress(Math.round(thermalStress * 10000.0) / 10000.0)
                .vibrationStress(Math.round(vibrationStress * 10000.0) / 10000.0)
                .thi(thi)
                .healthStatus(getHealthStatus(thi))
                .weightedStress(Math.round(weightedStress * 10000.0) / 10000.0)
                .build();
    }

    /**
     * Calculate RUL and next service date (Equations 6-7)
     */
    public RULPrediction calculateRULAndNextService(String deviceId, Double currentTHI) {
        TransformerConfig.TransformerProperties props = config.getTransformer();
        List<TelemetryFrame> history = telemetryRepository.findByDeviceIdAndTimestampBetweenOrderByTimestampDesc(
                deviceId,
                LocalDateTime.now().minusDays(30),
                LocalDateTime.now());

        // Eq (6): Proportional RUL estimate
        Double rulYears = Math.round(props.getRatedDesignLifeYears() * (currentTHI / 100.0) * 100.0) / 100.0;

        Double dailySlope = 0.0;
        Double daysToWarning = null;
        LocalDateTime projectedServiceDate = null;
        String serviceDescription = "Stable (Insufficient historical degradation)";

        if (history.size() >= 2) {
            LocalDateTime tInit = history.get(history.size() - 1).getTimestamp();
            Double thiInit = history.get(history.size() - 1).getEdgeTHI() != null
                    ? history.get(history.size() - 1).getEdgeTHI()
                    : currentTHI;

            LocalDateTime tCurr = history.get(0).getTimestamp();
            Double thiCurr = currentTHI;

            Long elapsedSeconds = ChronoUnit.SECONDS.between(tInit, tCurr);
            double elapsedDays = Math.max(1e-5, elapsedSeconds / 86400.0);

            // Eq (7): m = (THI(init) - THI(curr)) / days
            dailySlope = (thiInit - thiCurr) / elapsedDays;

            if (dailySlope > 0.001) {
                Double deltaToThreshold = thiCurr - props.getWarningThiThreshold();
                if (deltaToThreshold > 0) {
                    daysToWarning = deltaToThreshold / dailySlope;
                    projectedServiceDate = LocalDateTime.now().plusDays(daysToWarning.longValue());
                    serviceDescription = String.format("Projected: %d days", daysToWarning.longValue());
                } else {
                    serviceDescription = "IMMEDIATE ACTION REQUIRED (THI <= Warning)";
                }
            }
        }

        return RULPrediction.builder()
                .rulYears(rulYears)
                .dailyDegradationSlope(Math.round(dailySlope * 10000.0) / 10000.0)
                .daysToWarningThreshold(daysToWarning != null ? Math.round(daysToWarning * 10.0) / 10.0 : null)
                .projectedServiceDate(projectedServiceDate)
                .serviceDescription(serviceDescription)
                .ratedDesignLife(props.getRatedDesignLifeYears())
                .currentTHI(currentTHI)
                .warningThreshold(props.getWarningThiThreshold())
                .build();
    }

    /**
     * Evaluate environmental risk fusion (Section VIII)
     */
    public EnvironmentalRisk evaluateEnvironmentalRisk(TelemetryFrame frame) {
        // Temperature factor (normalized)
        Double tempFactor = Math.max(0.0, Math.min(1.0, (frame.getAmbientTemp() - 20.0) / 30.0));

        // Dryness factor (humidity inverse)
        Double drynessFactor = Math.max(0.0, Math.min(1.0, (80.0 - frame.getRelativeHumidity()) / 70.0));

        // Wind factor
        Double windFactor = Math.max(0.0, Math.min(1.0, frame.getWindSpeed() / 45.0));

        // Fire Weather Index (weighted combination)
        Double fwi = (0.4 * tempFactor + 0.4 * drynessFactor + 0.2 * windFactor) * 100.0;

        String riskLevel = determineRiskLevel(fwi);
        String consequence = determineConsequence(frame, fwi);

        return EnvironmentalRisk.builder()
                .fireWeatherIndex(Math.round(fwi * 10.0) / 10.0)
                .riskLevel(riskLevel)
                .consequenceSeverity(consequence)
                .temperatureFactor(Math.round(tempFactor * 10000.0) / 10000.0)
                .drynessFactor(Math.round(drynessFactor * 10000.0) / 10000.0)
                .windFactor(Math.round(windFactor * 10000.0) / 10000.0)
                .ambientTemp(frame.getAmbientTemp())
                .relativeHumidity(frame.getRelativeHumidity())
                .windSpeed(frame.getWindSpeed())
                .oilLevel(frame.getOilLevel())
                .build();
    }

    /**
     * Determine environmental risk level
     */
    private String determineRiskLevel(Double fwi) {
        if (fwi < 25.0) {
            return "LOW";
        } else if (fwi < 50.0) {
            return "MODERATE";
        } else if (fwi < 75.0) {
            return "HIGH";
        } else {
            return "EXTREME";
        }
    }

    /**
     * Determine consequence severity
     */
    private String determineConsequence(TelemetryFrame frame, Double fwi) {
        if ("CRITICAL".equalsIgnoreCase(frame.getOilLevel()) || fwi > 75.0) {
            return "WILDFIRE_DISASTER_RISK";
        } else if ("LOW".equalsIgnoreCase(frame.getOilLevel()) || fwi > 50.0) {
            return "ELEVATED_HAZARD";
        } else {
            return "CONTAINED";
        }
    }

    /**
     * Evaluate deterministic edge protection
     */
    public EdgeProtectionStatus evaluateProtection(TelemetryFrame frame) {
        TransformerConfig.ThresholdProperties thresholds = config.getThresholds();

        boolean isTripped = false;
        String tripReason = null;

        if (frame.getVoltage() > thresholds.getVoltageOvervolt()) {
            isTripped = true;
            tripReason = "OVERVOLTAGE";
        } else if (frame.getVoltage() < thresholds.getVoltageUndervolt()) {
            isTripped = true;
            tripReason = "UNDERVOLTAGE";
        } else if (frame.getCurrent() > thresholds.getCurrentOverload()) {
            isTripped = true;
            tripReason = "OVERCURRENT";
        } else if (frame.getTemperature() > thresholds.getTemperatureTrip()) {
            isTripped = true;
            tripReason = "THERMAL_TRIP";
        } else if (frame.getVibration() > thresholds.getVibrationTrip()) {
            isTripped = true;
            tripReason = "VIBRATION_ANOMALY";
        } else if ("CRITICAL".equalsIgnoreCase(frame.getOilLevel())) {
            isTripped = true;
            tripReason = "OIL_CRITICAL";
        }

        String relayState = isTripped ? "OPEN (TRIPPED)" : "CLOSED (ENERGIZED)";

        return EdgeProtectionStatus.builder()
                .isTripped(isTripped)
                .tripReason(tripReason)
                .buzzerActive(isTripped)
                .ledAlert(isTripped)
                .relayState(relayState)
                .tripTimestamp(isTripped ? LocalDateTime.now() : null)
                .faultVoltage(frame.getVoltage())
                .faultCurrent(frame.getCurrent())
                .faultTemperature(frame.getTemperature())
                .build();
    }

    /**
     * Get health status string
     */
    private String getHealthStatus(Double thi) {
        if (thi >= 85.0) {
            return "OPTIMAL / GOOD";
        } else if (thi >= 70.0) {
            return "MODERATE / ACCEPTABLE";
        } else if (thi >= 50.0) {
            return "WARNING / DEGRADED";
        } else {
            return "CRITICAL / SEVERE RISK";
        }
    }
}
