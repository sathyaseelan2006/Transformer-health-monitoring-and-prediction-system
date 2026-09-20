package com.gridguard.model;

import lombok.*;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import javax.persistence.*;
import java.time.LocalDateTime;

/**
 * TelemetryFrame - Real-time sensor data from ESP32 edge node
 * Stored in MongoDB for time-series analytics
 */
@Data
@AllArgsConstructor
@NoArgsConstructor
@Document(collection = "telemetry_frames")
public class TelemetryFrame {

    @Id
    private String id;

    private LocalDateTime timestamp;
    private String deviceId;

    // Primary Sensor Readings
    private Double voltage; // V_real (Volts)
    private Double current; // I_real (Amperes)
    private Double temperature; // T_real (Celsius - Winding)
    private Double vibration; // Vib_real (g - acceleration)

    // Oil & Environmental
    private String oilLevel; // NORMAL / LOW / CRITICAL
    private Double ambientTemp; // Celsius
    private Double relativeHumidity; // Percentage (0-100)
    private Double windSpeed; // km/h

    // Edge-Computed Values (optional)
    private Double edgeTHI; // THI computed at edge
    private String relayStatus; // CLOSED (ENERGIZED) / OPEN (TRIPPED)

    // Status
    private String status; // NORMAL / WARNING / CRITICAL
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    @PrePersist
    public void prePersist() {
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    @PreUpdate
    public void preUpdate() {
        this.updatedAt = LocalDateTime.now();
    }
}
