package com.gridguard.repository;

import com.gridguard.model.TelemetryFrame;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.data.mongodb.repository.Query;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

/**
 * TelemetryFrameRepository - MongoDB repository for time-series telemetry data
 */
@Repository
public interface TelemetryFrameRepository extends MongoRepository<TelemetryFrame, String> {

    /**
     * Find latest telemetry frame for a device
     */
    TelemetryFrame findFirstByDeviceIdOrderByTimestampDesc(String deviceId);

    /**
     * Find telemetry frames within time range
     */
    List<TelemetryFrame> findByDeviceIdAndTimestampBetweenOrderByTimestampDesc(
            String deviceId, LocalDateTime startTime, LocalDateTime endTime);

    /**
     * Find paginated telemetry history
     */
    Page<TelemetryFrame> findByDeviceIdOrderByTimestampDesc(String deviceId, Pageable pageable);

    /**
     * Find critical status frames
     */
    List<TelemetryFrame> findByDeviceIdAndStatusOrderByTimestampDesc(String deviceId, String status);

    /**
     * Count telemetry frames for a device
     */
    Long countByDeviceId(String deviceId);

    /**
     * Find frames with high vibration
     */
    @Query("{ 'deviceId': ?0, 'vibration': { $gt: ?1 }, 'timestamp': { $gte: ?2 } }")
    List<TelemetryFrame> findHighVibrationEvents(String deviceId, Double threshold, LocalDateTime since);

    /**
     * Find frames with high temperature
     */
    @Query("{ 'deviceId': ?0, 'temperature': { $gt: ?1 }, 'timestamp': { $gte: ?2 } }")
    List<TelemetryFrame> findHighTemperatureEvents(String deviceId, Double threshold, LocalDateTime since);
}
