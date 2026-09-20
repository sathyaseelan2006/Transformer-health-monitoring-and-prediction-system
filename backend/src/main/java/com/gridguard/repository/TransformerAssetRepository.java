package com.gridguard.repository;

import com.gridguard.model.TransformerAsset;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * TransformerAssetRepository - JPA repository for MySQL transformer asset
 * records
 */
@Repository
public interface TransformerAssetRepository extends JpaRepository<TransformerAsset, Long> {

    /**
     * Find transformer by device ID
     */
    Optional<TransformerAsset> findByDeviceId(String deviceId);

    /**
     * Find all assets by operational status
     */
    List<TransformerAsset> findByStatus(TransformerAsset.OperationalStatus status);

    /**
     * Find all assets at a location
     */
    List<TransformerAsset> findByLocation(String location);

    /**
     * Find assets by manufacturer
     */
    List<TransformerAsset> findByManufacturer(String manufacturer);

    /**
     * Check if device ID exists
     */
    Boolean existsByDeviceId(String deviceId);
}
