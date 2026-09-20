package com.gridguard.service;

import com.gridguard.model.TransformerAsset;
import com.gridguard.repository.TransformerAssetRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

/**
 * TransformerAssetService - Asset management service
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class TransformerAssetService {

    private final TransformerAssetRepository assetRepository;

    /**
     * Register new transformer asset
     */
    public TransformerAsset registerAsset(TransformerAsset asset) {
        if (assetRepository.existsByDeviceId(asset.getDeviceId())) {
            throw new IllegalArgumentException("Device ID already exists: " + asset.getDeviceId());
        }
        asset.setCreatedAt(LocalDateTime.now());
        asset.setUpdatedAt(LocalDateTime.now());
        TransformerAsset saved = assetRepository.save(asset);
        log.info("Transformer asset registered: {} ({})", asset.getAssetName(), asset.getDeviceId());
        return saved;
    }

    /**
     * Get asset by device ID
     */
    public Optional<TransformerAsset> getAssetByDeviceId(String deviceId) {
        return assetRepository.findByDeviceId(deviceId);
    }

    /**
     * Get asset by ID
     */
    public Optional<TransformerAsset> getAssetById(Long id) {
        return assetRepository.findById(id);
    }

    /**
     * Get all assets
     */
    public List<TransformerAsset> getAllAssets() {
        return assetRepository.findAll();
    }

    /**
     * Get assets by status
     */
    public List<TransformerAsset> getAssetsByStatus(TransformerAsset.OperationalStatus status) {
        return assetRepository.findByStatus(status);
    }

    /**
     * Get assets by location
     */
    public List<TransformerAsset> getAssetsByLocation(String location) {
        return assetRepository.findByLocation(location);
    }

    /**
     * Update asset
     */
    public TransformerAsset updateAsset(Long id, TransformerAsset assetDetails) {
        TransformerAsset asset = assetRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Asset not found with ID: " + id));

        asset.setAssetName(assetDetails.getAssetName());
        asset.setLocation(assetDetails.getLocation());
        asset.setStatus(assetDetails.getStatus());
        asset.setCurrentTHI(assetDetails.getCurrentTHI());
        asset.setCurrentRUL(assetDetails.getCurrentRUL());
        asset.setHealthStatus(assetDetails.getHealthStatus());
        asset.setLastDataPoint(LocalDateTime.now());
        asset.setUpdatedAt(LocalDateTime.now());

        TransformerAsset updated = assetRepository.save(asset);
        log.info("Asset updated: {}", id);
        return updated;
    }

    /**
     * Delete asset
     */
    public void deleteAsset(Long id) {
        assetRepository.deleteById(id);
        log.info("Asset deleted: {}", id);
    }
}
