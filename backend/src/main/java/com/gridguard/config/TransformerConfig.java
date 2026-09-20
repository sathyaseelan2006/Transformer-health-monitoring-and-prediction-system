package com.gridguard.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * TransformerConfig - Configuration parameters from application.yml
 * IEEE/IEC standards-based thresholds
 */
@Component
@ConfigurationProperties(prefix = "gridguard")
@Data
public class TransformerConfig {

    private TransformerProperties transformer;
    private ThresholdProperties thresholds;
    private WeightProperties weights;
    private ESP32Properties esp32;

    @Data
    public static class TransformerProperties {
        private Double nominalVoltage; // 230V
        private Double nominalCurrent; // 10A
        private Double nominalTemperature; // 30°C
        private Double maxTemperature; // 80°C
        private Double ratedDesignLifeYears; // 25 years
        private Double warningThiThreshold; // 70
        private Double criticalThiThreshold; // 50
    }

    @Data
    public static class ThresholdProperties {
        private Double voltageUndervolt; // 185V
        private Double voltageOvervolt; // 265V
        private Double currentOverload; // 15A
        private Double temperatureTrip; // 85°C
        private Double vibrationTrip; // 0.60g
    }

    @Data
    public static class WeightProperties {
        private Double voltageStress; // 0.25
        private Double currentStress; // 0.35
        private Double thermalStress; // 0.25
        private Double vibrationStress; // 0.15
    }

    @Data
    public static class ESP32Properties {
        private String serialPort; // COM3
        private Integer baudRate; // 115200
        private Integer timeoutMs; // 1000
    }
}
