-- =============================================================================
-- GridGuard OS: Intelligent Transformer Health & Environmental Risk Management System
-- Relational Database Schema for MySQL 8.0+ / MySQL Workbench
-- =============================================================================

CREATE DATABASE IF NOT EXISTS `gridguard_transformer_db` 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE `gridguard_transformer_db`;

-- -----------------------------------------------------------------------------
-- Table 1: transformers (Asset Registry & Baseline Specifications)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `transformers` (
    `transformer_id` VARCHAR(32) NOT NULL,
    `substation_name` VARCHAR(128) NOT NULL,
    `feeder_id` VARCHAR(64) NOT NULL,
    `rated_power_kva` DECIMAL(8,2) NOT NULL DEFAULT 25.00,
    `rated_voltage_v` DECIMAL(8,2) NOT NULL DEFAULT 230.00,
    `rated_current_a` DECIMAL(8,2) NOT NULL DEFAULT 10.00,
    `nominal_temperature_c` DECIMAL(5,2) NOT NULL DEFAULT 30.00,
    `max_temperature_c` DECIMAL(5,2) NOT NULL DEFAULT 85.00,
    `nominal_vibration_g` DECIMAL(6,4) NOT NULL DEFAULT 0.0500,
    `max_vibration_g` DECIMAL(6,4) NOT NULL DEFAULT 0.5000,
    `rated_life_years` DECIMAL(4,1) NOT NULL DEFAULT 25.0,
    `installation_date` DATE NOT NULL DEFAULT (CURRENT_DATE),
    `status` ENUM('ACTIVE_NOMINAL', 'DEGRADED_WARNING', 'CRITICAL_TRIPPED', 'MAINTENANCE_OFFLINE') NOT NULL DEFAULT 'ACTIVE_NOMINAL',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`transformer_id`),
    INDEX `idx_substation_status` (`substation_name`, `status`)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- Table 2: telemetry_frames (Time-Series Edge Sensor Data Stream via LoRa/ESP32)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `telemetry_frames` (
    `frame_id` BIGINT UNSIGNED AUTO_INCREMENT NOT NULL,
    `transformer_id` VARCHAR(32) NOT NULL,
    `voltage_v` DECIMAL(6,2) NOT NULL,
    `current_a` DECIMAL(6,2) NOT NULL,
    `winding_temp_c` DECIMAL(6,2) NOT NULL,
    `vibration_g` DECIMAL(7,4) NOT NULL,
    `oil_level` ENUM('NORMAL', 'LOW', 'CRITICAL') NOT NULL DEFAULT 'NORMAL',
    `ambient_temp_c` DECIMAL(5,2) NOT NULL DEFAULT 28.00,
    `rel_humidity_pct` DECIMAL(5,2) NOT NULL DEFAULT 45.00,
    `wind_speed_kmh` DECIMAL(5,2) NOT NULL DEFAULT 12.00,
    `device_id` VARCHAR(64) NOT NULL DEFAULT 'STM32-TX01',
    `relay_status` ENUM('CLOSED', 'OPEN_TRIPPED') NOT NULL DEFAULT 'CLOSED',
    `sampling_rate_hz` INT NOT NULL DEFAULT 100,
    `signal_confidence_pct` DECIMAL(5,2) NOT NULL DEFAULT 96.00,
    `recorded_at` DATETIME(3) NOT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`frame_id`),
    FOREIGN KEY (`transformer_id`) REFERENCES `transformers`(`transformer_id`) ON DELETE CASCADE,
    INDEX `idx_transformer_time` (`transformer_id`, `recorded_at` DESC),
    INDEX `idx_recorded_at` (`recorded_at` DESC)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- Table 3: health_assessments (ESF Multi-Stress Index & RUL Degradation)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `health_assessments` (
    `assessment_id` BIGINT UNSIGNED AUTO_INCREMENT NOT NULL,
    `frame_id` BIGINT UNSIGNED NOT NULL,
    `transformer_id` VARCHAR(32) NOT NULL,
    `voltage_stress_sv` DECIMAL(6,4) NOT NULL,
    `current_stress_si` DECIMAL(6,4) NOT NULL,
    `thermal_stress_st` DECIMAL(6,4) NOT NULL,
    `vibration_stress_svib` DECIMAL(6,4) NOT NULL,
    `transformer_health_index_thi` DECIMAL(5,2) NOT NULL,
    `health_category` ENUM('OPTIMAL_GOOD', 'MODERATE_ACCEPTABLE', 'WARNING_DEGRADED', 'CRITICAL_SEVERE_RISK') NOT NULL,
    `rul_years_predicted` DECIMAL(5,2) NOT NULL,
    `daily_degradation_slope` DECIMAL(6,4) NOT NULL,
    `projected_service_date` VARCHAR(64) NOT NULL,
    `assessed_at` DATETIME(3) NOT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`assessment_id`),
    FOREIGN KEY (`frame_id`) REFERENCES `telemetry_frames`(`frame_id`) ON DELETE CASCADE,
    FOREIGN KEY (`transformer_id`) REFERENCES `transformers`(`transformer_id`) ON DELETE CASCADE,
    INDEX `idx_thi_time` (`transformer_id`, `assessed_at` DESC),
    INDEX `idx_health_category` (`health_category`)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- Table 4: environmental_risks (Canadian FWI Climate Hazard Fusion)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `environmental_risks` (
    `risk_id` BIGINT UNSIGNED AUTO_INCREMENT NOT NULL,
    `frame_id` BIGINT UNSIGNED NOT NULL,
    `transformer_id` VARCHAR(32) NOT NULL,
    `fire_weather_index_fwi` DECIMAL(5,2) NOT NULL,
    `risk_level` ENUM('LOW', 'MODERATE', 'HIGH', 'EXTREME') NOT NULL,
    `consequence_severity` VARCHAR(64) NOT NULL,
    `risk_narrative` TEXT NOT NULL,
    `assessed_at` DATETIME(3) NOT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`risk_id`),
    FOREIGN KEY (`frame_id`) REFERENCES `telemetry_frames`(`frame_id`) ON DELETE CASCADE,
    FOREIGN KEY (`transformer_id`) REFERENCES `transformers`(`transformer_id`) ON DELETE CASCADE,
    INDEX `idx_risk_level` (`risk_level`),
    INDEX `idx_assessed_at` (`assessed_at` DESC)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- Table 5: classified_alerts (Real-Time Classified Alert Management Engine)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `classified_alerts` (
    `alert_id` BIGINT UNSIGNED AUTO_INCREMENT NOT NULL,
    `transformer_id` VARCHAR(32) NOT NULL,
    `severity` ENUM('CRITICAL', 'WARNING', 'ADVISORY', 'INFO') NOT NULL,
    `category` ENUM('ELECTRICAL', 'THERMAL', 'MECHANICAL', 'OIL_DIELECTRIC', 'ENVIRONMENTAL', 'PROTECTION_TRIP', 'SYSTEM_HEARTBEAT') NOT NULL,
    `alert_code` VARCHAR(64) NOT NULL,
    `alert_title` VARCHAR(128) NOT NULL,
    `alert_message` TEXT NOT NULL,
    `trigger_value` VARCHAR(64) NULL,
    `threshold_limit` VARCHAR(64) NULL,
    `is_tripped` BOOLEAN NOT NULL DEFAULT FALSE,
    `is_acknowledged` BOOLEAN NOT NULL DEFAULT FALSE,
    `acknowledged_by` VARCHAR(64) NULL,
    `acknowledged_at` DATETIME NULL,
    `triggered_at` DATETIME(3) NOT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`alert_id`),
    FOREIGN KEY (`transformer_id`) REFERENCES `transformers`(`transformer_id`) ON DELETE CASCADE,
    INDEX `idx_severity_ack` (`severity`, `is_acknowledged`, `triggered_at` DESC),
    INDEX `idx_category` (`category`),
    INDEX `idx_triggered_at` (`triggered_at` DESC)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- Table 6: kafka_event_stream (Message Broker Ingestion Audit & Event Log)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `kafka_event_stream` (
    `event_id` BIGINT UNSIGNED AUTO_INCREMENT NOT NULL,
    `topic_name` VARCHAR(128) NOT NULL,
    `partition_id` INT NOT NULL DEFAULT 0,
    `offset_num` BIGINT NOT NULL DEFAULT 0,
    `message_key` VARCHAR(64) NULL,
    `payload_json` JSON NOT NULL,
    `status` ENUM('PRODUCED', 'CONSUMED', 'PROCESSED', 'FAILED') NOT NULL DEFAULT 'PROCESSED',
    `ingested_at` DATETIME(3) NOT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`event_id`),
    INDEX `idx_topic_offset` (`topic_name`, `offset_num`),
    INDEX `idx_ingested_at` (`ingested_at` DESC)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- Table 7: ai_diagnostic_reports (RAG Local AI Root-Cause Diagnostic Reports)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `ai_diagnostic_reports` (
    `report_id` BIGINT UNSIGNED AUTO_INCREMENT NOT NULL,
    `transformer_id` VARCHAR(32) NOT NULL,
    `severity_code` VARCHAR(32) NOT NULL,
    `likely_cause` VARCHAR(255) NOT NULL,
    `recommended_instruments_json` JSON NOT NULL,
    `technician_playbook_json` JSON NOT NULL,
    `rag_references_json` JSON NOT NULL,
    `model_used` VARCHAR(128) NOT NULL,
    `disclaimer` TEXT NOT NULL,
    `generated_at` DATETIME(3) NOT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`report_id`),
    FOREIGN KEY (`transformer_id`) REFERENCES `transformers`(`transformer_id`) ON DELETE CASCADE,
    INDEX `idx_generated_at` (`generated_at` DESC)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- Table 8: maintenance_forecasts (Predictive Component Replacement Log)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `maintenance_forecasts` (
    `forecast_id` BIGINT UNSIGNED AUTO_INCREMENT NOT NULL,
    `transformer_id` VARCHAR(32) NOT NULL,
    `component_name` VARCHAR(128) NOT NULL,
    `priority` ENUM('MONITOR', 'WARNING', 'URGENT') NOT NULL,
    `action_window_days` INT NOT NULL,
    `diagnostic_reason` TEXT NOT NULL,
    `forecast_date` DATETIME NOT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`forecast_id`),
    FOREIGN KEY (`transformer_id`) REFERENCES `transformers`(`transformer_id`) ON DELETE CASCADE,
    INDEX `idx_priority` (`priority`, `action_window_days`)
) ENGINE=InnoDB;

-- =============================================================================
-- ANALYTICAL VIEWS FOR MISSION CONTROL & MYSQL WORKBENCH
-- =============================================================================

-- View 1: Real-time live status cockpit of all monitored transformers
CREATE OR REPLACE VIEW `v_live_transformer_cockpit` AS
SELECT 
    t.transformer_id,
    t.substation_name,
    t.status AS asset_status,
    f.voltage_v,
    f.current_a,
    f.winding_temp_c,
    f.vibration_g,
    f.oil_level,
    f.relay_status,
    h.transformer_health_index_thi AS thi,
    h.health_category,
    h.rul_years_predicted AS rul_years,
    e.fire_weather_index_fwi AS fwi,
    e.risk_level AS environmental_risk,
    f.recorded_at AS latest_telemetry_time
FROM `transformers` t
LEFT JOIN (
    SELECT f1.* 
    FROM `telemetry_frames` f1
    INNER JOIN (
        SELECT `transformer_id`, MAX(`frame_id`) as max_id 
        FROM `telemetry_frames` 
        GROUP BY `transformer_id`
    ) f2 ON f1.`frame_id` = f2.max_id
) f ON t.`transformer_id` = f.`transformer_id`
LEFT JOIN `health_assessments` h ON f.`frame_id` = h.`frame_id`
LEFT JOIN `environmental_risks` e ON f.`frame_id` = e.`frame_id`;

-- View 2: Unacknowledged high-priority classified alerts
CREATE OR REPLACE VIEW `v_unresolved_critical_alerts` AS
SELECT 
    a.alert_id,
    a.transformer_id,
    a.severity,
    a.category,
    a.alert_code,
    a.alert_title,
    a.alert_message,
    a.trigger_value,
    a.threshold_limit,
    a.is_tripped,
    a.triggered_at
FROM `classified_alerts` a
WHERE a.`is_acknowledged` = FALSE AND a.`severity` IN ('CRITICAL', 'WARNING')
ORDER BY a.`triggered_at` DESC;

-- View 3: 24-Hour hourly aggregated health & thermal load trend
CREATE OR REPLACE VIEW `v_hourly_stress_trend` AS
SELECT 
    f.transformer_id,
    DATE_FORMAT(f.recorded_at, '%Y-%m-%d %H:00:00') AS hour_window,
    ROUND(AVG(f.voltage_v), 1) AS avg_voltage,
    ROUND(MAX(f.voltage_v), 1) AS max_voltage,
    ROUND(AVG(f.current_a), 1) AS avg_current,
    ROUND(MAX(f.current_a), 1) AS max_current,
    ROUND(AVG(f.winding_temp_c), 1) AS avg_temp,
    ROUND(MAX(f.winding_temp_c), 1) AS max_temp,
    ROUND(AVG(f.vibration_g), 3) AS avg_vibration,
    ROUND(AVG(h.transformer_health_index_thi), 1) AS avg_thi,
    COUNT(*) AS frame_count
FROM `telemetry_frames` f
LEFT JOIN `health_assessments` h ON f.frame_id = h.frame_id
GROUP BY f.transformer_id, hour_window
ORDER BY hour_window DESC;

-- =============================================================================
-- SEED INITIAL ASSET REGISTRY
-- =============================================================================
INSERT INTO `transformers` (
    `transformer_id`, `substation_name`, `feeder_id`, `rated_power_kva`, 
    `rated_voltage_v`, `rated_current_a`, `nominal_temperature_c`, 
    `max_temperature_c`, `nominal_vibration_g`, `max_vibration_g`, 
    `rated_life_years`, `installation_date`, `status`
) VALUES (
    'STM32-TX01', 'Substation Node Alpha (Rural Feeder 4)', 'FDR-04-NORTH',
    25.00, 230.00, 10.00, 30.00, 85.00, 0.0500, 0.5000, 25.0, '2024-01-15', 'ACTIVE_NOMINAL'
) ON DUPLICATE KEY UPDATE `updated_at` = CURRENT_TIMESTAMP;

-- -----------------------------------------------------------------------------
-- SCHEMA INITIALIZATION COMPLETE
-- -----------------------------------------------------------------------------
