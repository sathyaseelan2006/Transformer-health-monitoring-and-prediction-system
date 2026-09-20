package com.gridguard.service;

import com.gridguard.model.TelemetryFrame;
import com.gridguard.repository.TelemetryFrameRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/**
 * TelemetryService - Telemetry data management
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class TelemetryService {

    private final TelemetryFrameRepository telemetryRepository;

    /**
     * Save telemetry frame
     */
    public TelemetryFrame saveTelemetryFrame(TelemetryFrame frame) {
        frame.setTimestamp(LocalDateTime.now());
        frame.setCreatedAt(LocalDateTime.now());
        TelemetryFrame saved = telemetryRepository.save(frame);
        log.info("Telemetry saved for device: {}", frame.getDeviceId());
        return saved;
    }

    /**
     * Get latest telemetry for device
     */
    public TelemetryFrame getLatestTelemetry(String deviceId) {
        return telemetryRepository.findFirstByDeviceIdOrderByTimestampDesc(deviceId);
    }

    /**
     * Get telemetry history within time range
     */
    public List<TelemetryFrame> getTelemetryHistory(String deviceId, LocalDateTime startTime, LocalDateTime endTime) {
        return telemetryRepository.findByDeviceIdAndTimestampBetweenOrderByTimestampDesc(deviceId, startTime, endTime);
    }

    /**
     * Get paginated telemetry history
     */
    public Page<TelemetryFrame> getTelemetryHistoryPaged(String deviceId, Pageable pageable) {
        return telemetryRepository.findByDeviceIdOrderByTimestampDesc(deviceId, pageable);
    }

    /**
     * Get critical telemetry events
     */
    public List<TelemetryFrame> getCriticalEvents(String deviceId) {
        return telemetryRepository.findByDeviceIdAndStatusOrderByTimestampDesc(deviceId, "CRITICAL");
    }

    /**
     * Get high vibration events
     */
    public List<TelemetryFrame> getHighVibrationEvents(String deviceId, Double threshold, LocalDateTime since) {
        return telemetryRepository.findHighVibrationEvents(deviceId, threshold, since);
    }

    /**
     * Get high temperature events
     */
    public List<TelemetryFrame> getHighTemperatureEvents(String deviceId, Double threshold, LocalDateTime since) {
        return telemetryRepository.findHighTemperatureEvents(deviceId, threshold, since);
    }

    /**
     * Count telemetry records for device
     */
    public Long getTelemetryCount(String deviceId) {
        return telemetryRepository.countByDeviceId(deviceId);
    }
}
