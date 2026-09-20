package com.gridguard.api;

import com.gridguard.api.dto.ApiResponse;
import com.gridguard.model.TransformerAsset;
import com.gridguard.service.TransformerAssetService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Optional;

/**
 * TransformerAssetController - REST API for transformer asset management
 */
@RestController
@RequestMapping("/assets")
@RequiredArgsConstructor
@Slf4j
@Tag(name = "Transformer Assets", description = "Transformer asset registration and management")
public class TransformerAssetController {

    private final TransformerAssetService assetService;

    /**
     * POST /api/assets - Register new transformer asset
     */
    @PostMapping
    @Operation(summary = "Register new transformer asset")
    public ResponseEntity<ApiResponse<TransformerAsset>> registerAsset(@RequestBody TransformerAsset asset) {
        try {
            TransformerAsset registered = assetService.registerAsset(asset);
            return ResponseEntity.status(HttpStatus.CREATED)
                    .body(ApiResponse.success(registered, "Asset registered successfully"));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(ApiResponse.error(e.getMessage(), "DUPLICATE_DEVICE_ID"));
        } catch (Exception e) {
            log.error("Error registering asset", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(ApiResponse.error("Failed to register asset", "ASSET_ERROR"));
        }
    }

    /**
     * GET /api/assets - Get all assets
     */
    @GetMapping
    @Operation(summary = "Get all transformer assets")
    public ResponseEntity<ApiResponse<List<TransformerAsset>>> getAllAssets() {
        List<TransformerAsset> assets = assetService.getAllAssets();
        return ResponseEntity.ok(ApiResponse.success(assets, "Retrieved " + assets.size() + " assets"));
    }

    /**
     * GET /api/assets/{id} - Get asset by ID
     */
    @GetMapping("/{id}")
    @Operation(summary = "Get asset by ID")
    public ResponseEntity<ApiResponse<TransformerAsset>> getAssetById(@PathVariable Long id) {
        Optional<TransformerAsset> asset = assetService.getAssetById(id);
        if (asset.isEmpty()) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(ApiResponse.error("Asset not found", "NOT_FOUND"));
        }
        return ResponseEntity.ok(ApiResponse.success(asset.get(), "Asset retrieved"));
    }

    /**
     * GET /api/assets/device/{deviceId} - Get asset by device ID
     */
    @GetMapping("/device/{deviceId}")
    @Operation(summary = "Get asset by device ID")
    public ResponseEntity<ApiResponse<TransformerAsset>> getAssetByDeviceId(@PathVariable String deviceId) {
        Optional<TransformerAsset> asset = assetService.getAssetByDeviceId(deviceId);
        if (asset.isEmpty()) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(ApiResponse.error("Device not found", "NOT_FOUND"));
        }
        return ResponseEntity.ok(ApiResponse.success(asset.get(), "Asset retrieved"));
    }

    /**
     * GET /api/assets/status/{status} - Get assets by status
     */
    @GetMapping("/status/{status}")
    @Operation(summary = "Get assets by operational status")
    public ResponseEntity<ApiResponse<List<TransformerAsset>>> getAssetsByStatus(@PathVariable String status) {
        try {
            TransformerAsset.OperationalStatus opStatus = TransformerAsset.OperationalStatus
                    .valueOf(status.toUpperCase());
            List<TransformerAsset> assets = assetService.getAssetsByStatus(opStatus);
            return ResponseEntity
                    .ok(ApiResponse.success(assets, "Retrieved " + assets.size() + " assets with status: " + status));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(ApiResponse.error("Invalid status value", "INVALID_STATUS"));
        }
    }

    /**
     * GET /api/assets/location/{location} - Get assets by location
     */
    @GetMapping("/location/{location}")
    @Operation(summary = "Get assets by location")
    public ResponseEntity<ApiResponse<List<TransformerAsset>>> getAssetsByLocation(@PathVariable String location) {
        List<TransformerAsset> assets = assetService.getAssetsByLocation(location);
        return ResponseEntity
                .ok(ApiResponse.success(assets, "Retrieved " + assets.size() + " assets at location: " + location));
    }

    /**
     * PUT /api/assets/{id} - Update asset
     */
    @PutMapping("/{id}")
    @Operation(summary = "Update transformer asset")
    public ResponseEntity<ApiResponse<TransformerAsset>> updateAsset(
            @PathVariable Long id,
            @RequestBody TransformerAsset assetDetails) {
        try {
            TransformerAsset updated = assetService.updateAsset(id, assetDetails);
            return ResponseEntity.ok(ApiResponse.success(updated, "Asset updated successfully"));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(ApiResponse.error(e.getMessage(), "NOT_FOUND"));
        }
    }

    /**
     * DELETE /api/assets/{id} - Delete asset
     */
    @DeleteMapping("/{id}")
    @Operation(summary = "Delete transformer asset")
    public ResponseEntity<ApiResponse<Void>> deleteAsset(@PathVariable Long id) {
        try {
            assetService.deleteAsset(id);
            return ResponseEntity.ok(ApiResponse.success(null, "Asset deleted successfully"));
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(ApiResponse.error("Asset not found", "NOT_FOUND"));
        }
    }
}
