package com.gridguard.api;

import com.gridguard.api.dto.ApiResponse;
import com.gridguard.model.*;
import com.gridguard.service.AnalyticsService;
import com.gridguard.service.TelemetryService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.List;

/**
 * AnalyticsController - REST API for analytics and reporting
 */
@RestController
@RequestMapping("/analytics")
@RequiredArgsConstructor
@Slf4j
@Tag(name = "Analytics", description = "Analytics, predictions, and reporting endpoints")
public class AnalyticsController {

    private final AnalyticsService analyticsService;
    private final TelemetryService telemetryService;

    /**
     * POST /api/analytics/compute-thi - Compute THI for telemetry data
     */
    @PostMapping("/compute-thi")
    @Operation(summary = "Compute THI from telemetry frame")
    public ResponseEntity<ApiResponse<StressIndicators>> computeTHI(@RequestBody TelemetryFrame frame) {
        try {
            StressIndicators stress = analyticsService.computeStressAndTHI(frame);
            return ResponseEntity.ok(ApiResponse.success(stress, "THI computed successfully"));
        } catch (Exception e) {
            log.error("Error computing THI", e);
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(ApiResponse.error("Failed to compute THI: " + e.getMessage(), "COMPUTATION_ERROR"));
        }
    }

    /**
     * GET /api/analytics/{deviceId}/rul - Get RUL prediction
     */
    @GetMapping("/{deviceId}/rul")
    @Operation(summary = "Get RUL prediction for device")
    public ResponseEntity<ApiResponse<RULPrediction>> getRULPrediction(
            @PathVariable String deviceId,
            @RequestParam(required = false) Double currentTHI) {
        try {
            TelemetryFrame latest = telemetryService.getLatestTelemetry(deviceId);
            if (latest == null) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(ApiResponse.error("No telemetry data found", "NOT_FOUND"));
            }

            Double thi = currentTHI != null ? currentTHI : 87.3; // default
            RULPrediction rul = analyticsService.calculateRULAndNextService(deviceId, thi);

            return ResponseEntity.ok(ApiResponse.success(rul, "RUL prediction retrieved"));
        } catch (Exception e) {
            log.error("Error retrieving RUL", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(ApiResponse.error("Failed to retrieve RUL: " + e.getMessage(), "ERROR"));
        }
    }

    /**
     * GET /api/analytics/{deviceId}/environmental-risk - Get environmental risk
     * assessment
     */
    @GetMapping("/{deviceId}/environmental-risk")
    @Operation(summary = "Get environmental risk assessment")
    public ResponseEntity<ApiResponse<EnvironmentalRisk>> getEnvironmentalRisk(@PathVariable String deviceId) {
        try {
            TelemetryFrame latest = telemetryService.getLatestTelemetry(deviceId);
            if (latest == null) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(ApiResponse.error("No telemetry data found", "NOT_FOUND"));
            }

            EnvironmentalRisk risk = analyticsService.evaluateEnvironmentalRisk(latest);
            return ResponseEntity.ok(ApiResponse.success(risk, "Environmental risk assessment retrieved"));
        } catch (Exception e) {
            log.error("Error retrieving environmental risk", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(ApiResponse.error("Failed to retrieve risk assessment", "ERROR"));
        }
    }

    /**
     * GET /api/analytics/{deviceId}/protection-status - Get edge protection status
     */
    @GetMapping("/{deviceId}/protection-status")
    @Operation(summary = "Get edge protection status")
    public ResponseEntity<ApiResponse<EdgeProtectionStatus>> getProtectionStatus(@PathVariable String deviceId) {
        try {
            TelemetryFrame latest = telemetryService.getLatestTelemetry(deviceId);
            if (latest == null) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(ApiResponse.error("No telemetry data found", "NOT_FOUND"));
            }

            EdgeProtectionStatus protection = analyticsService.evaluateProtection(latest);
            return ResponseEntity.ok(ApiResponse.success(protection, "Protection status retrieved"));
        } catch (Exception e) {
            log.error("Error retrieving protection status", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(ApiResponse.error("Failed to retrieve protection status", "ERROR"));
        }
    }

    /**
     * GET /api/analytics/{deviceId}/history - Get telemetry history with analytics
     */
    @GetMapping("/{deviceId}/history")
    @Operation(summary = "Get telemetry history with analytics")
    public ResponseEntity<ApiResponse<Page<TelemetryFrame>>> getTelemetryHistory(
            @PathVariable String deviceId,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "50") int size) {
        try {
            Pageable pageable = PageRequest.of(page, size);
            Page<TelemetryFrame> history = telemetryService.getTelemetryHistoryPaged(deviceId, pageable);
            return ResponseEntity
                    .ok(ApiResponse.success(history, "Retrieved " + history.getNumberOfElements() + " records"));
        } catch (Exception e) {
            log.error("Error retrieving history", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(ApiResponse.error("Failed to retrieve history", "ERROR"));
        }
    }

    /**
     * GET /api/analytics/{deviceId}/critical-events - Get critical events
     */
    @GetMapping("/{deviceId}/critical-events")
    @Operation(summary = "Get critical events for device")
    public ResponseEntity<ApiResponse<List<TelemetryFrame>>> getCriticalEvents(@PathVariable String deviceId) {
        try {
            List<TelemetryFrame> critical = telemetryService.getCriticalEvents(deviceId);
            return ResponseEntity
                    .ok(ApiResponse.success(critical, "Retrieved " + critical.size() + " critical events"));
        } catch (Exception e) {
            log.error("Error retrieving critical events", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(ApiResponse.error("Failed to retrieve critical events", "ERROR"));
        }
    }

    /**
     * GET /api/analytics/{deviceId}/high-vibration - Get high vibration events
     */
    @GetMapping("/{deviceId}/high-vibration")
    @Operation(summary = "Get high vibration events")
    public ResponseEntity<ApiResponse<List<TelemetryFrame>>> getHighVibrationEvents(
            @PathVariable String deviceId,
            @RequestParam(defaultValue = "0.5") Double threshold,
            @RequestParam(defaultValue = "7") int daysBack) {
        try {
            LocalDateTime since = LocalDateTime.now().minus(daysBack, ChronoUnit.DAYS);
            List<TelemetryFrame> events = telemetryService.getHighVibrationEvents(deviceId, threshold, since);
            return ResponseEntity.ok(ApiResponse.success(events, "Retrieved " + events.size() + " vibration events"));
        } catch (Exception e) {
            log.error("Error retrieving vibration events", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(ApiResponse.error("Failed to retrieve vibration events", "ERROR"));
        }
    }

    /**
     * GET /api/analytics/{deviceId}/high-temperature - Get high temperature events
     */
    @GetMapping("/{deviceId}/high-temperature")
    @Operation(summary = "Get high temperature events")
    public ResponseEntity<ApiResponse<List<TelemetryFrame>>> getHighTemperatureEvents(
            @PathVariable String deviceId,
            @RequestParam(defaultValue = "80") Double threshold,
            @RequestParam(defaultValue = "7") int daysBack) {
        try {
            LocalDateTime since = LocalDateTime.now().minus(daysBack, ChronoUnit.DAYS);
            List<TelemetryFrame> events = telemetryService.getHighTemperatureEvents(deviceId, threshold, since);
            return ResponseEntity.ok(ApiResponse.success(events, "Retrieved " + events.size() + " temperature events"));
        } catch (Exception e) {
            log.error("Error retrieving temperature events", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(ApiResponse.error("Failed to retrieve temperature events", "ERROR"));
        }
    }
}
