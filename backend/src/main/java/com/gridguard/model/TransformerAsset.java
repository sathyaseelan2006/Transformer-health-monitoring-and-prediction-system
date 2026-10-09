package com.gridguard.model;

import lombok.*;
import jakarta.persistence.*;
import java.time.LocalDateTime;

/**
 * TransformerAsset - Core transformer equipment record
 * Stored in MySQL for persistent asset management
 */
@Entity
@Table(name = "transformer_assets")
@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class TransformerAsset {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private String deviceId; // STM32-TX01, etc.

    @Column(nullable = false)
    private String assetName; // Friendly name
    private String location; // Substation location
    private String manufacturer; // ABB, Siemens, etc.
    private Integer manufacturingYear;

    // Specifications
    @Column(nullable = false)
    private Double ratedVoltage; // Primary voltage (V)
    private Double secondaryVoltage; // Secondary voltage (V)
    private Double ratedPower; // kVA
    private Double ratedCurrent; // Amperes

    // Maintenance & Design
    private Double designLifeYears; // Original design life (typically 25)
    private LocalDateTime commissionDate;
    private LocalDateTime lastMaintenanceDate;

    // Operational Status
    @Enumerated(EnumType.STRING)
    private OperationalStatus status; // OPERATIONAL, MAINTENANCE, DECOMMISSIONED

    // Current Metrics
    private Double currentTHI;
    private Double currentRUL;
    private String healthStatus;
    private LocalDateTime lastDataPoint;

    // Auditing
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

    public enum OperationalStatus {
        OPERATIONAL, MAINTENANCE, DECOMMISSIONED, STANDBY
    }
}
