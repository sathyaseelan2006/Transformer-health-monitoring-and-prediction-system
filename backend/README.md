# GridGuard OS - Backend API

**Professional-grade Transformer Health Monitoring & Predictive Maintenance System**

Java Spring Boot backend with MySQL + MongoDB for the GridGuard OS dashboard.

---

## 🚀 Tech Stack

- **Java 17**
- **Spring Boot 3.2.0**
- **MySQL 8.0** - Transformer asset management
- **MongoDB** - Time-series telemetry data
- **Maven** - Build tool
- **Swagger/OpenAPI 3** - API documentation
- **jSerialComm** - ESP32 serial communication

---

## 📁 Project Structure

```
backend/
├── src/main/java/com/gridguard/
│   ├── api/                        # REST Controllers
│   │   ├── TelemetryController.java
│   │   ├── AnalyticsController.java
│   │   ├── TransformerAssetController.java
│   │   ├── dto/ApiResponse.java
│   │   └── TelemetryAnalyticsResponse.java
│   ├── model/                      # Domain models
│   │   ├── TelemetryFrame.java
│   │   ├── TransformerAsset.java
│   │   ├── StressIndicators.java
│   │   ├── EnvironmentalRisk.java
│   │   ├── EdgeProtectionStatus.java
│   │   └── RULPrediction.java
│   ├── service/                    # Business logic
│   │   ├── TelemetryService.java
│   │   ├── AnalyticsService.java
│   │   └── TransformerAssetService.java
│   ├── repository/                 # Data access layer
│   │   ├── TelemetryFrameRepository.java
│   │   └── TransformerAssetRepository.java
│   ├── config/                     # Configuration
│   │   ├── TransformerConfig.java
│   │   └── CorsConfig.java
│   └── GridGuardApplication.java   # Main application
├── src/main/resources/
│   └── application.yml             # Configuration
└── pom.xml                         # Maven dependencies
```

---

## 🛠️ Setup Instructions

### **Prerequisites**

1. **Java 17** installed ([Download](https://adoptium.net/))
2. **Maven 3.8+** installed ([Download](https://maven.apache.org/download.cgi))
3. **Docker Desktop** (for MySQL + MongoDB)

### **Step 1: Start Databases**

Navigate to the project root and run:

```bash
cd backend
docker-compose up -d
```

This will start:
- **MySQL** on port `3306` (database: `gridguard_db`)
- **MongoDB** on port `27017` (database: `gridguard_telemetry`)

### **Step 2: Build the Project**

```bash
mvn clean install
```

### **Step 3: Run the Application**

```bash
mvn spring-boot:run
```

Or run directly:

```bash
java -jar target/gridguard-backend-1.0.0.jar
```

The backend will start on **http://localhost:8080**

---

## 📡 API Endpoints

### **Base URL:** `http://localhost:8080/api`

### **Telemetry Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/telemetry/ingest` | Ingest telemetry from ESP32 |
| `GET` | `/telemetry/{deviceId}/latest` | Get latest telemetry frame |
| `GET` | `/telemetry/{deviceId}/count` | Get telemetry count |
| `GET` | `/telemetry/health` | Health check |

### **Analytics Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/analytics/compute-thi` | Compute THI from telemetry |
| `GET` | `/analytics/{deviceId}/rul` | Get RUL prediction |
| `GET` | `/analytics/{deviceId}/environmental-risk` | Get environmental risk |
| `GET` | `/analytics/{deviceId}/protection-status` | Get edge protection status |
| `GET` | `/analytics/{deviceId}/history` | Get telemetry history (paginated) |
| `GET` | `/analytics/{deviceId}/critical-events` | Get critical events |
| `GET` | `/analytics/{deviceId}/high-vibration` | Get high vibration events |
| `GET` | `/analytics/{deviceId}/high-temperature` | Get high temp events |

### **Transformer Asset Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/assets` | Register new transformer asset |
| `GET` | `/assets` | Get all assets |
| `GET` | `/assets/{id}` | Get asset by ID |
| `GET` | `/assets/device/{deviceId}` | Get asset by device ID |
| `GET` | `/assets/status/{status}` | Get assets by status |
| `GET` | `/assets/location/{location}` | Get assets by location |
| `PUT` | `/assets/{id}` | Update asset |
| `DELETE` | `/assets/{id}` | Delete asset |

---

## 📊 API Documentation (Swagger)

Once the server is running, access interactive API docs at:

**http://localhost:8080/api/swagger-ui.html**

OpenAPI 3 spec: **http://localhost:8080/api/v3/api-docs**

---

## 🔌 ESP32 Integration

### **Telemetry JSON Format**

Send POST requests to `/api/telemetry/ingest` with this JSON structure:

```json
{
  "deviceId": "STM32-TX01",
  "voltage": 230.5,
  "current": 10.2,
  "temperature": 34.5,
  "vibration": 0.08,
  "oilLevel": "NORMAL",
  "ambientTemp": 28.0,
  "relativeHumidity": 45.0,
  "windSpeed": 12.0
}
```

### **Response Format**

The backend returns computed analytics:

```json
{
  "success": true,
  "message": "Telemetry processed successfully",
  "data": {
    "telemetryId": "abc123",
    "deviceId": "STM32-TX01",
    "timestamp": "2026-09-18T08:54:50",
    "rawData": { ... },
    "stress": {
      "voltageStress": 0.1234,
      "currentStress": 0.0567,
      "thermalStress": 0.0890,
      "vibrationStress": 0.0234,
      "thi": 87.3,
      "healthStatus": "OPTIMAL / GOOD"
    },
    "environmental": {
      "fireWeatherIndex": 24.3,
      "riskLevel": "LOW"
    },
    "protection": {
      "isTripped": false,
      "relayState": "CLOSED (ENERGIZED)"
    },
    "rul": {
      "rulYears": 21.8,
      "projectedServiceDate": "2027-03-15"
    }
  }
}
```

---

## 🗄️ Database Configuration

### **MySQL (Asset Management)**

- **Host:** `localhost:3306`
- **Database:** `gridguard_db`
- **Username:** `root`
- **Password:** `root`

Tables:
- `transformer_assets` - Transformer equipment records

### **MongoDB (Telemetry Time-Series)**

- **Host:** `localhost:27017`
- **Database:** `gridguard_telemetry`

Collections:
- `telemetry_frames` - Real-time sensor data

---

## 📐 Mathematical Equations (Research Paper)

The analytics engine implements IEEE/IEC standards-based calculations:

### **Equation 1-3: Stress Indicators**
```
Sv = |V_real - V_nominal| / V_nominal
Si = |I_real - I_nominal| / I_nominal
St = (T_real - T_nominal) / (T_max - T_nominal)
Svib = (Vib_real - Vib_nominal) / (Vib_max - Vib_nominal)
```

### **Equation 4: Transformer Health Index (THI)**
```
THI = 100 - (W1·Sv + W2·Si + W3·St + W4·Svib) × 100
```
Weights: W1=0.25, W2=0.35, W3=0.25, W4=0.15

### **Equation 6: Remaining Useful Life (RUL)**
```
RUL = L_rated × (THI / 100)
```

### **Equation 7: Degradation Slope**
```
m = (THI_init - THI_current) / elapsed_days
```

---

## 🧪 Testing with cURL

### **Ingest Telemetry**
```bash
curl -X POST http://localhost:8080/api/telemetry/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "deviceId": "STM32-TX01",
    "voltage": 230.5,
    "current": 10.2,
    "temperature": 34.5,
    "vibration": 0.08,
    "oilLevel": "NORMAL",
    "ambientTemp": 28.0,
    "relativeHumidity": 45.0,
    "windSpeed": 12.0
  }'
```

### **Get Latest Telemetry**
```bash
curl http://localhost:8080/api/telemetry/STM32-TX01/latest
```

### **Get RUL Prediction**
```bash
curl http://localhost:8080/api/analytics/STM32-TX01/rul?currentTHI=87.3
```

---

## 🔧 Configuration

Edit `src/main/resources/application.yml`:

```yaml
gridguard:
  transformer:
    nominal-voltage: 230.0
    nominal-current: 10.0
    max-temperature: 80.0
    rated-design-life-years: 25.0
    warning-thi-threshold: 70.0
  
  thresholds:
    voltage-overvolt: 265.0
    current-overload: 15.0
    temperature-trip: 85.0
  
  esp32:
    serial-port: COM3
    baud-rate: 115200
```

---

## 📈 Monitoring & Health

- **Health Check:** `GET /api/telemetry/health`
- **Actuator:** `http://localhost:8080/api/actuator/health`
- **Metrics:** `http://localhost:8080/api/actuator/metrics`

---

## 🐳 Docker Commands

```bash
# Start databases
docker-compose up -d

# Stop databases
docker-compose down

# View logs
docker-compose logs -f

# Reset databases (CAREFUL!)
docker-compose down -v
```

---

## 🎯 Next Steps

1. **Connect Frontend**: Update `static/app.js` to call these APIs
2. **ESP32 Setup**: Configure ESP32 to POST telemetry to `/api/telemetry/ingest`
3. **Authentication**: Add Spring Security + JWT (optional)
4. **WebSocket**: Real-time telemetry streaming (optional)

---

## 📝 License

Proprietary - GridGuard OS © 2026

---

## 🤝 Support

For questions or issues, contact the development team.
