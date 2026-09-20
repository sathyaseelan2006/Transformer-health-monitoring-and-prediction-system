package com.gridguard.api;

import com.gridguard.api.dto.ApiResponse;
import com.gridguard.model.*;
import com.gridguard.service.AnalyticsService;
import com.gridguard.service.TelemetryService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;

/**
 * TelemetryController - REST API for telemetry ingestion and analytics
 */
@RestController
@RequestMapping("/telemetry")
@RequiredArgsConstructor
@Slf4j
@Tag(name = "Telemetry", description = "Real-time sensor data and analytics endpoints")
public class TelemetryController {

    private final TelemetryService telemetryService;
    private final AnalyticsService analyticsService;

    /**
     * POST /api/telemetry/ingest - Ingest telemetry from ESP32
     */
    @PostMapping("/ingest")
    @Operation(summary = "Ingest telemetry frame from ESP32", description = "Accepts JSON telemetry data and performs analytics")
    public ResponseEntity<ApiResponse<TelemetryAnalyticsResponse>> ingestTelemetry(
            @RequestBody TelemetryFrame telemetryFrame) {
        try {
            // Save telemetry frame
            TelemetryFrame saved = telemetryService.saveTelemetryFrame(telemetryFrame);
            log.info("Telemetry ingested for device: {}", telemetryFrame.getDeviceId());

            // Compute analytics
            StressIndicators stress = analyticsService.computeStressAndTHI(saved);
            EnvironmentalRisk envRisk = analyticsService.evaluateEnvironmentalRisk(saved);
            EdgeProtectionStatus protection = analyticsService.evaluateProtection(saved);
            RULPrediction rul = analyticsService.calculateRULAndNextService(
                    telemetryFrame.getDeviceId(),
                    stress.getThi());

            // Build response
            TelemetryAnalyticsResponse response = TelemetryAnalyticsResponse.builder()
                    .telemetryId(saved.getId())
                    .deviceId(saved.getDeviceId())
                    .timestamp(saved.getTimestamp())
                    .rawData(TelemetryAnalyticsResponse.RawData.builder()
                            .voltage(saved.getVoltage())
                            .current(saved.getCurrent())
                            .temperature(saved.getTemperature())
                            .vibration(saved.getVibration())
                            .oilLevel(saved.getOilLevel())
                            .ambientTemp(saved.getAmbientTemp())
                            .relativeHumidity(saved.getRelativeHumidity())
                            .windSpeed(saved.getWindSpeed())
                            .build())
                    .stress(stress)
                    .environmental(envRisk)
                    .protection(protection)
                    .rul(rul)
                    .status(protection.getIsTripped() ? "ALERT" : "OK")
                    .build();

            return ResponseEntity.ok(ApiResponse.success(response, "Telemetry processed successfully"));
        } catch (Exception e) {
            log.error("Error ingesting telemetry", e);
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(ApiResponse.error("Failed to ingest telemetry: " + e.getMessage(), "TELEMETRY_ERROR"));
        }
    }

    /**
     * GET /api/telemetry/{deviceId}/latest - Get latest telemetry
     */
    @GetMapping("/{deviceId}/latest")
    @Operation(summary = "Get latest telemetry for device")
    public ResponseEntity<ApiResponse<TelemetryFrame>> getLatestTelemetry(@PathVariable String deviceId) {
        TelemetryFrame latest = telemetryService.getLatestTelemetry(deviceId);
        if (latest == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(ApiResponse.error("No telemetry found for device: " + deviceId, "NOT_FOUND"));
        }
        return ResponseEntity.ok(ApiResponse.success(latest, "Latest telemetry retrieved"));
    }

    /**
     * GET /api/telemetry/{deviceId}/count - Get telemetry count
     */
    @GetMapping("/{deviceId}/count")
    @Operation(summary = "Get telemetry frame count for device")
    public ResponseEntity<ApiResponse<Long>> getTelemetryCount(@PathVariable String deviceId) {
        Long count = telemetryService.getTelemetryCount(deviceId);
        return ResponseEntity.ok(ApiResponse.success(count, "Telemetry count: " + count));
    }

    /**
     * Health check endpoint
     */
    @GetMapping("/health")
    @Operation(summary = "Health check")
    public ResponseEntity<ApiResponse<String>> health() {
        return ResponseEntity.ok(ApiResponse.success("GridGuard Backend is healthy", "Health check passed"));
    }
}
