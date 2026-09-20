package com.gridguard.api;

import com.gridguard.model.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * TelemetryAnalyticsResponse - Complete telemetry response with computed
 * analytics
 */
@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class TelemetryAnalyticsResponse {

    private String telemetryId;
    private String deviceId;
    private LocalDateTime timestamp;

    private RawData rawData;
    private StressIndicators stress;
    private EnvironmentalRisk environmental;
    private EdgeProtectionStatus protection;
    private RULPrediction rul;

    private String status; // OK, ALERT, CRITICAL

    @Data
    @AllArgsConstructor
    @NoArgsConstructor
    @Builder
    public static class RawData {
        private Double voltage;
        private Double current;
        private Double temperature;
        private Double vibration;
        private String oilLevel;
        private Double ambientTemp;
        private Double relativeHumidity;
        private Double windSpeed;
    }
}
