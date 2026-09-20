# GridGuard Backend - Build Instructions

## Build with Maven

```bash
# Clean and build
mvn clean install

# Skip tests
mvn clean install -DskipTests

# Run application
mvn spring-boot:run
```

## Run JAR directly

```bash
java -jar target/gridguard-backend-1.0.0.jar
```

## Package for production

```bash
mvn clean package -DskipTests
```

## Database Setup

```bash
# Start MySQL + MongoDB
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f mysql
docker-compose logs -f mongodb
```

## Access Database Management UIs

- **MySQL (phpMyAdmin)**: http://localhost:8081
  - Username: `root`
  - Password: `root`

- **MongoDB (Mongo Express)**: http://localhost:8082
  - Username: `admin`
  - Password: `admin123`

## API Testing

```bash
# Health check
curl http://localhost:8080/api/telemetry/health

# Swagger UI
open http://localhost:8080/api/swagger-ui.html
```
